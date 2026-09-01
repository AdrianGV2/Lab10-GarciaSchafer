"""The Manito driver's REST contract, served by the simulator.

`manito-driver` (the Rust service that talks to the Arduino) exposes these
routes on port 8080. Implementing the same ones here is what lets a program
written with `manito_api.ManitoArm` run against the simulator and the real arm
without a single change.

Where the simulator genuinely cannot do something the hardware can, the route
answers 501 rather than accepting a command it will silently ignore.
"""

import logging
from queue import Full

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["driver_contract"])

READY = "Ready"
MOVING = "Moving"
HOMING = "Homing"

NOT_SIMULATED = (
    "The simulator does not model {feature}. This endpoint exists on the real "
    "driver only."
)


class MoveJointsBody(BaseModel):
    theta1: float
    theta2: float
    phi: float
    z: float
    gripper: bool = False


class GripperBody(BaseModel):
    close: bool


def _enqueue(request: Request, command: dict) -> None:
    try:
        request.app.state.command_queue.put_nowait(command)
    except Full:
        raise HTTPException(status_code=429, detail="Command queue is full")


def _state(request: Request) -> dict:
    return request.app.state.tracker.poll_state()


def _last_error(lifecycle: dict):
    """Render an aborted run the way the driver renders a fault: one string.

    The driver keeps its last error until a new one replaces it, so clients
    compare against the value they saw before a command rather than treating
    any non-null value as fresh.
    """
    status = (lifecycle or {}).get("status")
    if status in ("failed", "stopped"):
        return f"{status}: {lifecycle.get('reason')}"
    return None


@router.get("/api/status")
def status(request: Request):
    """Arm state in the driver's shape (`SharedState` in manito-driver)."""
    data = _state(request)

    joints = (data.get("robot_joints") or {}).get(data.get("active_robot"))
    if not joints or len(joints) < 4:
        joints = [0, 0, 0, 0]
    # The worker publishes [J1 deg, Z cm, J3 deg, J4 deg]; the firmware calls
    # those theta1, z, theta2 and phi.
    theta1, z, theta2, phi = joints[0], joints[1], joints[2], joints[3]

    if data.get("is_homing"):
        motion = HOMING
    elif data.get("busy"):
        motion = MOVING
    else:
        motion = READY

    return {
        "theta1": theta1,
        "theta2": theta2,
        "phi": phi,
        "z": z,
        "gripper": data.get("gripper", False),
        "status": motion,
        "is_connected": True,
        "is_homed": data.get("is_homed", False),
        "last_error": _last_error(data.get("lifecycle")),
        "homing_progress": None,
        # Simulator-only: the worker executes one command per physics burst and
        # counts them, which lets a client detect completion exactly.
        "executed_total": data.get("executed_total", 0),
    }


@router.post("/api/move_joints")
def move_joints(request: Request, body: MoveJointsBody):
    _enqueue(
        request,
        {
            "action": "move_joints",
            "metadata": {
                "j1": body.theta1,
                "j3": body.theta2,
                "j4": body.phi,
                "z": body.z,
            },
        },
    )

    # On the firmware the gripper state rides along inside the movement; here it
    # is a separate command, so it is only sent when it actually changes.
    if body.gripper != _state(request).get("gripper", False):
        _enqueue(request, {"action": "cierra" if body.gripper else "abre"})

    return {"status": "accepted"}


@router.post("/api/gripper")
def gripper(request: Request, body: GripperBody):
    _enqueue(request, {"action": "cierra" if body.close else "abre"})
    return {"status": "accepted"}


@router.post("/api/homing")
def homing(request: Request):
    _enqueue(request, {"action": "home"})
    return {"status": "accepted"}


@router.post("/api/estop")
def estop(request: Request):
    """Emergency stop: drop the program and leave the arm where it stands."""
    _enqueue(request, {"action": "estop"})
    return {"status": "accepted"}


@router.post("/api/jog")
def jog():
    raise HTTPException(
        status_code=501, detail=NOT_SIMULATED.format(feature="continuous jogging")
    )


@router.post("/api/set_speed_accel")
def set_speed_accel():
    raise HTTPException(
        status_code=501,
        detail=NOT_SIMULATED.format(feature="motor speed and acceleration limits"),
    )


@router.post("/api/set_joint_config")
def set_joint_config():
    raise HTTPException(
        status_code=501,
        detail=NOT_SIMULATED.format(feature="per-joint speed and acceleration limits"),
    )
