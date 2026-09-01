"""Prueba de comunicacion con genesis-sim, sin PDDL de por medio.

Verifica que este proyecto puede: leer el estado del brazo, hacer homing,
mover el efector a una posicion cartesiana derivada de la posicion real
del cubo en el escenario activo, y accionar la garra.

Requiere que genesis-sim ya este corriendo (localhost:8000 por defecto)
con un escenario que tenga un robot "Manito" y un objeto "Cubo Verde"
(scenario_1).
"""

import time

import requests
from manito_api import ManitoArm

BASE_URL = "http://localhost:8000"


def _status():
    response = requests.get(f"{BASE_URL}/api/status", timeout=5)
    response.raise_for_status()
    return response.json()


def _wait_ready(executed_before, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = _status()
        if state["status"] == "Ready" and state["executed_total"] > executed_before:
            return state
        time.sleep(0.1)
    raise TimeoutError("El brazo no termino el movimiento a tiempo.")


def _command(action, **fields):
    before = _status()["executed_total"]
    payload = {"action": action, **fields}
    response = requests.post(f"{BASE_URL}/api/v1/command", json=payload, timeout=5)
    response.raise_for_status()
    return _wait_ready(before)


def move_to(x, y, z):
    return _command("move_to", x=x, y=y, z=z)


def gripper(close):
    return _command("cierra" if close else "abre")


def main():
    arm = ManitoArm(BASE_URL)
    print("Estado inicial:", arm.status())

    arm.home()
    print("Homed:", arm.status())

    state = requests.get(f"{BASE_URL}/api/v1/state", timeout=5).json()
    robot_pos = state["entities"]["Manito"]
    cube_pos = state["entities"]["Cubo Verde"]
    target = [cube_pos[i] - robot_pos[i] for i in range(3)]
    print("Cubo Verde, posicion relativa al robot:", target)

    print("Aproximando por encima del cubo...")
    move_to(target[0], target[1], target[2] + 0.05)

    print("Bajando al cubo...")
    move_to(target[0], target[1], target[2])

    print("Cerrando garra...")
    gripper(True)

    print("Levantando...")
    move_to(target[0], target[1], target[2] + 0.10)

    final_state = requests.get(f"{BASE_URL}/api/v1/state", timeout=5).json()
    print("Cubo Verde, posicion final:", final_state["entities"]["Cubo Verde"])
    print("Estado final del brazo:", arm.status())


if __name__ == "__main__":
    main()
