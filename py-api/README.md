# manito-api

Python client for the **Manito** SCARA robot arm.

One class, `ManitoArm`, drives two backends that speak the same REST contract:

| Backend | What it is | Default port |
| --- | --- | --- |
| `manito-driver` | Rust driver talking to the Arduino over serial (`manito/arduino_firmware` → `driver/`) | 8080 |
| `genesis-sim` | Genesis physics simulator (`manito/genesis-sim`) | 8000 |

A program written against one runs unchanged on the other. That is the point of
this package: it replaces the two copies of `manito_api.py` that had drifted
apart inside the simulator and firmware repositories.

## Install

```bash
uv add "manito-api @ git+ssh://git@gitea.liria.cl:5001/manito/py-api.git"
# or
pip install "manito-api @ git+ssh://git@gitea.liria.cl:5001/manito/py-api.git"
```

## Use

```python
from manito_api import ManitoArm

arm = ManitoArm()               # or ManitoArm("http://192.168.1.50:8080")
arm.home()
arm.move_joints(0, 90, 0, 20)   # j1, j3, j4 in degrees; z in centimetres
arm.gripper(True)
```

Choose the backend without touching the code:

```bash
MANITO_URL=http://localhost:8000 python my_program.py   # simulator
MANITO_URL=http://raspberrypi.local:8080 python my_program.py   # real arm
```

Every call blocks until the arm finishes moving, so a script reads top to
bottom. Pass `ManitoArm(wait=False)` to fire and forget.

## Examples

`examples/pick_cube.py` picks up a cube three times over. It takes the backend
as command-line options instead of an environment variable:

```bash
uv add "manito-api[examples] @ git+ssh://git@gitea.liria.cl:5001/manito/py-api.git"

python examples/pick_cube.py                                  # localhost:8080
python examples/pick_cube.py --host raspberrypi.local         # real arm
python examples/pick_cube.py --host localhost --port 8000     # simulator
```

## Methods

| Method | Description |
| --- | --- |
| `move_joints(j1, j3, j4, z, gripper=None)` | Absolute pose. Omitting `gripper` keeps its current state. |
| `gripper(close)` | `True` closes, `False` opens. |
| `home()` | Run the homing sequence. |
| `status()` | Current state as a dict. |
| `jog(joint_id, speed)` | Drive one joint continuously; `0` stops it. |
| `set_speed_accel(speed, accel)` | One speed/acceleration for all joints. |
| `set_joint_config(speeds, accels)` | Per-joint speeds and accelerations, four of each. |
| `estop()` | Emergency stop; never waits. |

`j1`, `j3`, `j4` match the J1/J3/J4 labels on the Blockly blocks. There is no
`j2` because the second axis is the vertical one, given as `z` in centimetres.
On the wire these become the firmware's `theta1`, `theta2` and `phi`.

The simulator does not implement `jog`, `set_speed_accel` or
`set_joint_config`; it answers those with HTTP 501 rather than pretending to
move.

## Status

`status()` returns the driver's state:

```python
{"theta1": 0.0, "theta2": 0.0, "phi": 0.0, "z": 0.0,
 "gripper": False, "status": "Ready",        # Ready | Moving | Homing
 "is_connected": True, "is_homed": False,
 "last_error": None, "homing_progress": None}
```

The simulator adds `executed_total`, a monotonic count of completed commands.

## Errors

`ManitoError` is raised when the arm reports a failure during a movement — a
guardrail abort in the simulator, a protocol error on the real arm.
`TimeoutError` is raised if a movement does not finish within `timeout`
seconds (120 by default).

`last_error` is sticky on the driver: it holds the last failure until a new one
replaces it. The client therefore only raises when the value *changes* during a
command, never on whatever was already there when the program started.
