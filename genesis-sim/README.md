# Manito Genesis Simulator

A simulator for the **Manito** SCARA robot arm, built on the
[Genesis](https://github.com/Genesis-Embodied-AI/Genesis) physics engine. It
runs GPU-accelerated physics, exposes the same HTTP API as the real robot's
driver, and ships a web interface where students program the arm with Blockly
blocks.

Because the simulator speaks the driver's protocol, anything written against
the simulator drives the real arm without a single change.

---

## Quick start

### With Docker

```bash
git clone ssh://git@gitea.liria.cl:5001/manito/genesis-sim.git
cd genesis-sim
docker compose up --build
```

Then open **http://localhost:8000/**.

The container is configured to use an NVIDIA GPU when the drivers and
`nvidia-container-toolkit` are present, and falls back to CPU otherwise.

> The Docker image has not been verified on a GPU host in its current form. If
> it fails, the local installation below is the supported path.

### Locally (Ubuntu)

Requires Python 3.12 and the OpenGL libraries Genesis renders with:

```bash
sudo apt-get install libgl1 libglib2.0-0 libglfw3 libegl1
pip install uv
make install        # Python deps, Node inside the venv, front-end deps
make frontend       # build the UI so the API can serve it
make serve          # http://localhost:8000
```

For front-end development with hot reload, run the backend and Vite separately:

```bash
uv run simctl serve          # terminal 1
cd frontend && pnpm run dev  # terminal 2 -> http://localhost:5173
```

---

## The four ways to run it

The simulator does one thing per command, chosen on the command line rather
than buried in a config file.

| Command | What it does |
| --- | --- |
| `simctl serve [scenario]` | Headless, with the HTTP API and the web UI. **The normal mode.** Without a scenario it waits for the front end to pick one. |
| `simctl viewer <scenario>` | Opens the native Genesis window on a scenario. For inspecting a scene or debugging a URDF. Add `--api` to serve the API too. |
| `simctl run <scenario> <script.py>` | Runs one script against one scenario with no UI and exits with the script's status code. For grading and regression checks. Needs `uv sync --extra scripts`. |
| `simctl validate [scenario…]` | Parses scenarios and checks every asset path, without starting physics. Fast, and needs no GPU. |

Useful options:

```bash
simctl serve --host 0.0.0.0 --port 8000   # where to listen
simctl serve --no-scripts                 # disable the script-execution endpoint
simctl serve --backend cpu                # auto (default), gpu, or cpu
simctl viewer configs/scenarios/scenario_1.yml
simctl validate
```

Every setting also reads an environment variable (`MANITO_SIM_PORT`,
`MANITO_SIM_BACKEND`, `MANITO_SIM_MAX_RUN_STEPS`, …); see `src/settings.py`.

> **On `--backend`:** `auto` tries the GPU and falls back to CPU if Genesis
> cannot initialise it. That fallback cannot rescue a GPU that runs out of
> memory *later*, while the scene is being built — on a shared machine, use
> `--backend cpu`.

---

## The HTTP API

Everything the simulator does is reachable over HTTP on port 8000.

`/api/*` is the REST contract of `manito-driver`, the Rust service that drives
the real arm. Implementing it here is what makes a program portable between the
simulator and the hardware — point it at a different host and it just works.
Endpoints the simulator cannot honestly implement answer **501** rather than
accepting a command they would silently ignore.

| Method | Endpoint | Body | Notes |
| --- | --- | --- | --- |
| GET | `/api/status` | — | Pose, gripper, motion state, errors |
| POST | `/api/move_joints` | `{theta1, theta2, phi, z, gripper}` | Angles in degrees, `z` in centimetres |
| POST | `/api/homing` | — | Run the homing sequence |
| POST | `/api/gripper` | `{close}` | |
| POST | `/api/estop` | — | Drops the running program immediately |
| POST | `/api/jog` | — | **501** — no motor dynamics |
| POST | `/api/set_speed_accel` | — | **501** |
| POST | `/api/set_joint_config` | — | **501** |

`/api/v1/*` is the simulator's own surface, used by the web interface:

| Method | Endpoint | Notes |
| --- | --- | --- |
| POST | `/api/v1/command` | Queue one action. `202` when accepted, `429` when the queue is full |
| GET | `/api/v1/state` | Active robot, end-effector and entity positions |
| GET | `/api/v1/scenarios` | Catalog with objectives and robot names |
| GET | `/api/v1/video_feed` | MJPEG stream of the scene camera |
| POST | `/api/v1/script/run` | Run a Python script server-side (see [Security](#security)) |
| POST | `/api/v1/script/stop` | Stop it |
| GET | `/api/v1/script/output?since=N` | Buffered output from index `N` |
| WS | `/api/v1/ws/state` | Telemetry pushed at 10 Hz: joints, entities, current block, run lifecycle |

### Driving the arm

```bash
curl localhost:8000/api/status
curl -X POST localhost:8000/api/homing
curl -X POST localhost:8000/api/move_joints -H 'Content-Type: application/json' \
     -d '{"theta1": 15, "theta2": 40, "phi": 0, "z": 6, "gripper": false}'
```

`GET /api/status` answers with the driver's state:

```json
{"theta1": 15, "theta2": 40, "phi": 0, "z": 6,
 "gripper": false, "status": "Ready",
 "is_connected": true, "is_homed": true,
 "last_error": null, "homing_progress": null,
 "executed_total": 2}
```

`status` is `Ready`, `Moving` or `Homing`. Commands are queued and executed one
at a time, so poll until it returns to `Ready` to know a movement finished.
`executed_total` is a simulator-only extra: a monotonic count of completed
commands, which detects completion exactly rather than by polling for motion.

### `/api/v1/command`

The block-level queue the front end uses. The body takes an `action` plus
whichever fields that action needs:

```bash
curl -X POST localhost:8000/api/v1/command -H 'Content-Type: application/json' \
     -d '{"action": "move_joints", "metadata": {"j1": 0, "j3": 90, "j4": 0, "z": 8}}'
```

| Action | Fields |
| --- | --- |
| `move_to` | `x`, `y`, `z` — cartesian, solved with inverse kinematics |
| `move_joints` | `metadata: {j1, j3, j4, z}` — degrees, `z` in centimetres. Also accepted as `move_joints_fk` |
| `cierra` / `abre` | — close / open the gripper |
| `home` | — |
| `reset` | — rebuild the scene's initial state |
| `switch_robot` | `robot_name` — for scenarios with more than one arm |
| `stop_program` / `estop` | — clear the queue and stop |
| `reload_scenario` | `scenario` — path to a YAML file; restarts the physics worker |
| `camera_zoom` / `camera_lift` / `camera_lateral` | `zoom` / `z` / `y` |

Camera moves, stops and scenario swaps take effect on the frame they arrive.
Everything else is buffered and executed one command at a time, so a program's
steps stay legible on screen. Add `block_id` to any command and it comes back
on the telemetry socket as `current_block`, which is how the UI highlights the
block currently running.

### What the simulator enforces

**Joint limits are clamped, not rejected.** The vertical axis travels ±10 cm
and the rotations are bounded by the URDF, so a target outside those bounds is
silently brought inside them. Ask for `z=20` and the arm goes to 10.

**Runs are capped** at 100 commands and 300 seconds. Hitting either clears the
queue and stops the program; the reason appears as `last_error` on
`/api/status` (`failed: max_steps_reached`, `failed: max_runtime_reached`) and
in the `lifecycle` field on the telemetry socket. Change the caps with
`MANITO_SIM_MAX_RUN_STEPS` and `MANITO_SIM_MAX_RUNTIME_SEC`.

---

## Scenarios

A scenario is a YAML file describing one scene: which arms are in it, the
props and objects around them, where the camera looks and what the student is
asked to do. They all live in **`configs/scenarios/`**, and five ship with the
project:

| File | Arms | Mission |
| --- | --- | --- |
| [`configs/scenarios/scenario_1.yml`](configs/scenarios/scenario_1.yml) | 1 | Pick up the green cube and lift it. On a table, over a cartesian grid |
| [`configs/scenarios/scenario_2.yml`](configs/scenarios/scenario_2.yml) | 1 | Stack the green cube on top of the orange cylinder |
| [`configs/scenarios/scenario_3.yml`](configs/scenarios/scenario_3.yml) | 1 | Stack three cubes in order: green, blue, red |
| [`configs/scenarios/scenario_4.yml`](configs/scenarios/scenario_4.yml) | 2 | Each arm lifts its own cube — red, then yellow |
| [`configs/scenarios/scenario_5.yml`](configs/scenarios/scenario_5.yml) | 2 | One arm hands the cylinder to the other, which lifts it |

Any command that takes a scenario takes the path to one of these files, or to
your own:

```bash
simctl viewer configs/scenarios/scenario_3.yml
simctl serve configs/scenarios/scenario_1.yml
```

The web interface lists them all at `GET /api/v1/scenarios` and lets the
student switch between them without restarting the server.

Writing your own is a matter of copying one and editing it —
**[docs/scenarios.md](docs/scenarios.md)** documents every section, the asset
layout and the naming rules. Check it before running it:

```bash
simctl validate configs/scenarios/my_scenario.yml
simctl validate                                    # all of them
```

---

## Security

`POST /api/v1/script/run` executes the code it is given **unsandboxed and
unauthenticated**, as the user running the server. That is what the endpoint is
for, but it means anyone who can reach the port can run code on that machine.

Run it on a trusted network. When binding beyond localhost the server logs a
warning, and `--no-scripts` removes the endpoint entirely:

```bash
simctl serve --host 0.0.0.0 --no-scripts
```

---

## Layout

```
src/
  cli.py         the four commands
  settings.py    ports, paths and limits, all env-overridable
  runtime/       supervisor and bridges: owns the worker process
  core/          scenario parsing, Genesis scene building, physics, kinematics
  api/           FastAPI routes
  telemetry/     the state cache the API reads
assets/
  robots/        robot models: URDF plus its meshes
  props/         scenery: tables, ground planes, textures
configs/
  scenarios/     scene definitions: scenario_1.yml … scenario_5.yml
frontend/        React + Blockly interface
docs/            architecture and scenario reference
```

See **[docs/architecture.md](docs/architecture.md)** for how the pieces fit
together at runtime.
