"""Agente PDDL para el brazo Manito.

Resuelve un problema PDDL contra un dominio con pyperplan, ancla cada accion
simbolica del plan a coordenadas reales usando scenes/<scene>.yml, y ejecuta
el plan contra genesis-sim.

Uso:
    uv run python agente.py <domain.pddl> <problem.pddl> <scene>

    uv run python agente.py dominio.pddl problems/problem_1.pddl scene_1

<scene> es el nombre de un archivo en scenes/ (sin extension). Ese archivo
indica que escena 3D cargar en genesis-sim y a que coordenadas del mundo
corresponde cada zona PDDL. Las posiciones iniciales de los cubos se leen
del propio :init del problema (predicados `at`), no se duplican aqui.
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
SCENES_DIR = PROJECT_ROOT / "scenes"
EVIDENCE_DIR = PROJECT_ROOT / "evidence"

APPROACH_HEIGHT = 0.05  # sobre el objetivo, antes de bajar
LIFT_HEIGHT = 0.10  # al retirarse tras tomar/soltar
POSITION_TOLERANCE = 0.03  # metros, para la validacion geometrica final


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


def execute_action(sim: SimClient, robot_origin, world: World, name: str, args):
    def to_robot_frame(point):
        return [point[i] - robot_origin[i] for i in range(3)]

    if name == "grip":
        cube, _zone = args
        target = to_robot_frame(world.pos_of(cube))
        sim.move_to(target[0], target[1], target[2] + APPROACH_HEIGHT)
        sim.move_to(*target)
        sim.gripper(True)
        sim.move_to(target[0], target[1], target[2] + LIFT_HEIGHT)

    elif name == "drop":
        cube, zone = args
        target = to_robot_frame(world.zones[zone])
        sim.move_to(target[0], target[1], target[2] + APPROACH_HEIGHT)
        sim.move_to(*target)
        sim.gripper(False)
        sim.move_to(target[0], target[1], target[2] + LIFT_HEIGHT)
        world.place_on_zone(cube, zone)

    elif name == "stack":
        cube, base_cube = args
        world.place_on_cube(cube, base_cube)
        target = to_robot_frame(world.pos_of(cube))
        sim.move_to(target[0], target[1], target[2] + APPROACH_HEIGHT)
        sim.move_to(*target)
        sim.gripper(False)
        sim.move_to(target[0], target[1], target[2] + LIFT_HEIGHT)

    elif name == "unstack":
        cube, _base_cube = args
        target = to_robot_frame(world.pos_of(cube))
        sim.move_to(target[0], target[1], target[2] + APPROACH_HEIGHT)
        sim.move_to(*target)
        sim.gripper(True)
        sim.move_to(target[0], target[1], target[2] + LIFT_HEIGHT)

    else:
        raise ValueError(f"Accion desconocida en el plan: {name}")


# -- validacion: compara el estado real del simulador contra la meta -------


def validate_goal(sim: SimClient, scene: dict, world: World, goal_literals):
    entities = sim.state().get("entities") or {}
    cube_entity = scene.get("cubes", {})
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
            zone_pos = scene["zones"].get(zone)
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
    parser.add_argument("scene", help="Nombre del archivo en scenes/ (sin extension), ej: scene_1")
    parser.add_argument("--url", default=None, help="URL de genesis-sim (por defecto MANITO_URL o http://localhost:8000)")
    args = parser.parse_args()

    scene_path = SCENES_DIR / f"{args.scene}.yml"
    scene = yaml.safe_load(scene_path.read_text(encoding="utf-8"))
    problem_text = args.problem.read_text(encoding="utf-8")
    sim_url = args.url or os.environ.get("MANITO_URL", "http://localhost:8000")
    sim = SimClient(sim_url)

    pipeline_start = time.perf_counter()

    print(f"[1/4] Planificando {args.problem.name} con pyperplan...")
    plan, plan_time = solve(args.domain, args.problem)
    print(f"      Plan de {len(plan)} accion(es) en {plan_time:.3f}s:")
    for name, plan_args in plan:
        print(f"        ({name} {' '.join(plan_args)})")

    print(f"[2/4] Cargando {scene['genesis_scenario']} en {sim_url}...")
    expected_entities = scene.get("cubes", {}).values()
    sim.reload_scenario(scene["genesis_scenario"], expected_entities)
    sim.home()

    cube_zone = read_initial_cube_zones(problem_text)
    world = World(scene["zones"], cube_zone, scene["cube_size"])
    robot_origin = sim.state()["entities"]["Manito"]

    print("[3/4] Ejecutando el plan en el simulador...")
    exec_start = time.perf_counter()
    for name, plan_args in plan:
        print(f"      -> ({name} {' '.join(plan_args)})")
        execute_action(sim, robot_origin, world, name, plan_args)
    exec_time = time.perf_counter() - exec_start

    print("[4/4] Validando la meta contra el estado real del simulador...")
    goal_literals = read_goal_literals(problem_text)
    checks = validate_goal(sim, scene, world, goal_literals)
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
                "scene": args.scene,
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
