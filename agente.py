"""Agente PDDL para el brazo Manito.

Resuelve un problema PDDL contra un dominio con pyperplan, ancla cada accion
simbolica del plan a coordenadas reales usando la seccion `pddl_bridge` del
escenario de genesis-sim, y ejecuta el plan contra el simulador.

Uso:
    uv run python agente.py <domain.pddl> <problem.pddl> <scenario>

    uv run python agente.py dominio.pddl problems/problem_1.pddl lab10_scene_1

<scenario> es el nombre de un archivo en genesis-sim/configs/scenarios/ (sin
extension). Esa misma escena 3D que carga genesis-sim trae una seccion
`pddl_bridge:` con las coordenadas de cada zona PDDL (el loader de escenas de
genesis-sim la ignora). Las posiciones iniciales de los cubos se leen del
propio :init del problema (predicados `at`), no se duplican aqui.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent
GENESIS_SCENARIOS_DIR = PROJECT_ROOT / "genesis-sim" / "configs" / "scenarios"
EVIDENCE_DIR = PROJECT_ROOT / "evidence"

SAFE_TRAVEL_Z = 0.15  # altura de traslado por defecto (relativa al origen del robot)
POSITION_TOLERANCE = 0.03  # metros, para la validacion geometrica final

# La cinematica inversa apunta a Link_5 (la muneca), pero los dedos de la
# garra cuelgan ~5.2cm mas abajo (offset del Joint_5/Joint_6 en el URDF). Sin
# esto Link_5 se posiciona a la altura del cubo y los dedos terminan bajo la
# mesa en vez de rodearlo.
FINGER_REACH = 0.052

# Al soltar un cubo (drop/stack), bajar hasta la altura EXACTA donde deberia
# quedar el centro del cubo asume que la garra sujeta el cubo con un offset
# perfectamente rigido y constante -- no lo es (agarre por friccion, con
# margen de error). Si el cubo ya viene un poco mas abajo de lo asumido, la
# muneca lo termina empujando contra la superficie de destino en vez de solo
# depositarlo, y el motor de fisica responde con un impulso que lo dispara.
# Frenar unos centimetros antes y soltar ahi evita empujar: el cubo cae esa
# distancia corta por gravedad, sin colision forzada.
DROP_CLEARANCE = 0.02


# -- lectura de PDDL (solo lo que el agente necesita: :init y :goal) -------


def _extract_block(text: str, keyword: str) -> str:
    """Contenido entre los parentesis balanceados de (:keyword ...)."""
    idx = text.index(f"(:{keyword}")
    depth = 0
    start = None
    for i in range(idx, len(text)):
        if text[i] == "(":
            if start is None:
                start = i
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    raise ValueError(f"Bloque :{keyword} sin cerrar en el problema.")


_LITERAL_RE = re.compile(r"\(([\w-]+)((?:\s+[\w?-]+)*)\s*\)")


def _extract_literals(block_text: str):
    literals = []
    for match in _LITERAL_RE.finditer(block_text):
        name = match.group(1)
        if name in ("and", "not"):
            continue
        literals.append((name, match.group(2).split()))
    return literals


def read_initial_cube_zones(problem_text: str) -> dict:
    """{cubo: zona} a partir de los hechos (at cubo zona) en :init."""
    init_literals = _extract_literals(_extract_block(problem_text, "init"))
    return {args[0]: args[1] for name, args in init_literals if name == "at"}


def read_goal_literals(problem_text: str):
    return _extract_literals(_extract_block(problem_text, "goal"))


# -- planificacion (pyperplan como subproceso) ------------------------------

_ACTION_RE = re.compile(r"\(([\w-]+)\s*((?:[\w-]+\s*)*)\)")


def _parse_plan(soln_path: Path):
    plan = []
    for line in soln_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        match = _ACTION_RE.match(line)
        if match:
            plan.append((match.group(1), match.group(2).split()))
    return plan


def solve(domain: Path, problem: Path):
    """Corre pyperplan. Devuelve (plan, tiempo_de_planificacion_segundos)."""
    soln_path = problem.with_name(problem.name + ".soln")
    soln_path.unlink(missing_ok=True)

    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "pyperplan", str(domain), str(problem)],
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - start

    if not soln_path.exists():
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"pyperplan no encontro un plan para {problem.name}.")

    return _parse_plan(soln_path), elapsed


# -- cliente HTTP de genesis-sim ---------------------------------------------


class SimClient:
    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self.session = requests.Session()

    def state(self) -> dict:
        response = self.session.get(f"{self.url}/api/v1/state", timeout=10)
        response.raise_for_status()
        return response.json()

    def status(self) -> dict:
        response = self.session.get(f"{self.url}/api/status", timeout=10)
        response.raise_for_status()
        return response.json()

    def command(self, action: str, **fields) -> None:
        before = self.status()["executed_total"]
        payload = {"action": action, **fields}
        response = self.session.post(
            f"{self.url}/api/v1/command", json=payload, timeout=10
        )
        response.raise_for_status()
        self._wait_ready(before)

    def _wait_ready(self, executed_before: int, timeout: float = 60.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            state = self.status()
            if state["status"] == "Ready" and state["executed_total"] > executed_before:
                return
            if state.get("last_error"):
                raise RuntimeError(f"El simulador reporto un error: {state['last_error']}")
            time.sleep(0.1)
        raise TimeoutError("El brazo no termino el movimiento a tiempo.")

    def reload_scenario(self, scenario_path: str, expected_entities, timeout: float = 180.0) -> None:
        response = self.session.post(
            f"{self.url}/api/v1/command",
            json={"action": "reload_scenario", "scenario": scenario_path},
            timeout=10,
        )
        response.raise_for_status()

        deadline = time.time() + timeout
        while time.time() < deadline:
            entities = self.state().get("entities") or {}
            if all(name in entities for name in expected_entities):
                return
            time.sleep(0.3)
        raise TimeoutError(f"La escena {scenario_path} no termino de cargar a tiempo.")

    def move_to(self, x: float, y: float, z: float) -> None:
        self.command("move_to", x=x, y=y, z=z)

    def gripper(self, close: bool) -> None:
        self.command("cierra" if close else "abre")

    def home(self) -> None:
        self.command("home")


# -- modelo del mundo: donde esta cada cubo mientras avanza el plan --------


class World:
    def __init__(self, zones: dict, cube_zone: dict, cube_size: float):
        self.zones = zones
        self.cube_size = cube_size
        self.positions = {cube: list(zones[zone]) for cube, zone in cube_zone.items()}

    def pos_of(self, cube: str):
        return self.positions[cube]

    def place_on_zone(self, cube: str, zone: str) -> None:
        self.positions[cube] = list(self.zones[zone])

    def place_on_cube(self, cube: str, base_cube: str) -> None:
        base = self.positions[base_cube]
        self.positions[cube] = [base[0], base[1], base[2] + self.cube_size]


def _go_and_act(sim: SimClient, robot_origin, safe_z: float, target_world, act_fn, descend_margin: float = 0.0):
    """Sube derecho donde este el brazo, viaja en plano a altura segura, y
    recien ahi baja derecho sobre el objetivo.

    Ir directo (x,y,z simultaneo) desde la posicion anterior hasta encima del
    objetivo interpola las juntas en linea recta *en el espacio articular*, no
    en cartesiano: el brazo puede pasar a baja altura durante la traslacion y
    arrastrar cualquier cubo que este en el camino. Subir-trasladar-bajar evita
    esa colision.

    `descend_margin` frena la bajada esa distancia antes del objetivo (ver
    DROP_CLEARANCE) -- usarlo al soltar un cubo, nunca al tomarlo.
    """
    ee_world = sim.state()["robot_end_effectors"]["Manito"]
    ee = [ee_world[i] - robot_origin[i] for i in range(3)]
    target = [target_world[i] - robot_origin[i] for i in range(3)]
    grip_z = target[2] + FINGER_REACH + descend_margin

    sim.move_to(ee[0], ee[1], safe_z)  # subir derecho donde esta
    sim.move_to(target[0], target[1], safe_z)  # trasladar en plano, arriba

    # Bajar en un par de tramos en vez de un solo salto grande: cada move_to
    # tiene un piso minimo de pasos de interpolacion, asi que dividir la
    # bajada en tramos mas cortos reparte esos pasos en mas tiempo real y se
    # ve (y es) mas controlado que un solo tramo largo.
    midpoint_z = safe_z + (grip_z - safe_z) / 2
    sim.move_to(target[0], target[1], midpoint_z)
    sim.move_to(target[0], target[1], grip_z)  # bajar hasta que LOS DEDOS lleguen al objetivo

    act_fn()
    sim.move_to(target[0], target[1], safe_z)  # retirarse derecho hacia arriba


def execute_action(sim: SimClient, robot_origin, safe_z: float, world: World, name: str, args):
    if name == "grip":
        cube, _zone = args
        _go_and_act(sim, robot_origin, safe_z, world.pos_of(cube), lambda: sim.gripper(True))

    elif name == "drop":
        cube, zone = args
        _go_and_act(
            sim, robot_origin, safe_z, world.zones[zone], lambda: sim.gripper(False),
            descend_margin=DROP_CLEARANCE,
        )
        world.place_on_zone(cube, zone)

    elif name == "stack":
        cube, base_cube = args
        world.place_on_cube(cube, base_cube)
        _go_and_act(
            sim, robot_origin, safe_z, world.pos_of(cube), lambda: sim.gripper(False),
            descend_margin=DROP_CLEARANCE,
        )

    elif name == "unstack":
        cube, _base_cube = args
        _go_and_act(sim, robot_origin, safe_z, world.pos_of(cube), lambda: sim.gripper(True))

    else:
        raise ValueError(f"Accion desconocida en el plan: {name}")


# -- validacion: compara el estado real del simulador contra la meta -------


def validate_goal(sim: SimClient, bridge: dict, world: World, goal_literals):
    entities = sim.state().get("entities") or {}
    cube_entity = bridge.get("cubes", {})
    checks = []

    for name, args in goal_literals:
        if name == "on":
            cube, base_cube = args
            cube_pos = entities.get(cube_entity.get(cube))
            base_pos = entities.get(cube_entity.get(base_cube))
            ok = (
                cube_pos is not None
                and base_pos is not None
                and abs(cube_pos[2] - (base_pos[2] + world.cube_size)) < POSITION_TOLERANCE
                and abs(cube_pos[0] - base_pos[0]) < POSITION_TOLERANCE
                and abs(cube_pos[1] - base_pos[1]) < POSITION_TOLERANCE
            )
            checks.append((f"(on {cube} {base_cube})", ok))

        elif name == "at":
            cube, zone = args
            cube_pos = entities.get(cube_entity.get(cube))
            zone_pos = bridge["zones"].get(zone)
            ok = (
                cube_pos is not None
                and zone_pos is not None
                and all(abs(cube_pos[i] - zone_pos[i]) < POSITION_TOLERANCE for i in range(3))
            )
            checks.append((f"(at {cube} {zone})", ok))

        elif name == "holding":
            (cube,) = args
            ok = bool(sim.status().get("gripper"))
            checks.append((f"(holding {cube})", ok))

        else:
            checks.append((f"({name} {' '.join(args)})", None))  # no verificable geometricamente

    return checks


# -- orquestacion -------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("domain", type=Path)
    parser.add_argument("problem", type=Path)
    parser.add_argument("scenario", help="Nombre del archivo en genesis-sim/configs/scenarios/ (sin extension), ej: lab10_scene_1")
    parser.add_argument("--url", default=None, help="URL de genesis-sim (por defecto MANITO_URL o http://localhost:8000)")
    args = parser.parse_args()

    scenario_path = GENESIS_SCENARIOS_DIR / f"{args.scenario}.yml"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    bridge = scenario["pddl_bridge"]
    genesis_scenario = f"configs/scenarios/{args.scenario}.yml"
    problem_text = args.problem.read_text(encoding="utf-8")
    sim_url = args.url or os.environ.get("MANITO_URL", "http://localhost:8000")
    sim = SimClient(sim_url)

    pipeline_start = time.perf_counter()

    print(f"[1/4] Planificando {args.problem.name} con pyperplan...")
    plan, plan_time = solve(args.domain, args.problem)
    print(f"      Plan de {len(plan)} accion(es) en {plan_time:.3f}s:")
    for name, plan_args in plan:
        print(f"        ({name} {' '.join(plan_args)})")

    print(f"[2/4] Cargando {genesis_scenario} en {sim_url}...")
    expected_entities = bridge.get("cubes", {}).values()
    sim.reload_scenario(genesis_scenario, expected_entities)
    sim.home()

    cube_zone = read_initial_cube_zones(problem_text)
    world = World(bridge["zones"], cube_zone, bridge["cube_size"])
    robot_origin = sim.state()["entities"]["Manito"]
    safe_z = bridge.get("safe_travel_z", SAFE_TRAVEL_Z)

    print("[3/4] Ejecutando el plan en el simulador...")
    exec_start = time.perf_counter()
    for name, plan_args in plan:
        print(f"      -> ({name} {' '.join(plan_args)})")
        execute_action(sim, robot_origin, safe_z, world, name, plan_args)
    exec_time = time.perf_counter() - exec_start

    print("[4/4] Validando la meta contra el estado real del simulador...")
    goal_literals = read_goal_literals(problem_text)
    checks = validate_goal(sim, bridge, world, goal_literals)
    all_ok = True
    for label, ok in checks:
        if ok is None:
            print(f"      ?  {label} (no verificable geometricamente)")
        else:
            print(f"      {'OK' if ok else 'FALLO'}  {label}")
            all_ok = all_ok and ok

    pipeline_time = time.perf_counter() - pipeline_start
    print(
        f"\nTiempos: planificacion={plan_time:.3f}s  ejecucion={exec_time:.3f}s  "
        f"total={pipeline_time:.3f}s"
    )
    print("Resultado:", "EXITO" if all_ok else "FALLO")

    EVIDENCE_DIR.mkdir(exist_ok=True)
    evidence_path = EVIDENCE_DIR / f"{args.problem.stem}_{int(time.time())}.json"
    evidence_path.write_text(
        json.dumps(
            {
                "problem": str(args.problem),
                "scenario": args.scenario,
                "plan": [f"({n} {' '.join(a)})" for n, a in plan],
                "plan_time_sec": plan_time,
                "exec_time_sec": exec_time,
                "total_time_sec": pipeline_time,
                "goal_checks": {label: ok for label, ok in checks},
                "success": all_ok,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Evidencia guardada en {evidence_path.relative_to(PROJECT_ROOT)}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
