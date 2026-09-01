# Architecture

## The shape of it

Genesis runs in a **child process**, not a thread. The parent process serves the
API and holds the latest state; the child owns the physics and is the only place
Genesis is ever initialised.

```
Parent process  —  simctl serve
│
├── FastAPI + uvicorn (daemon thread)          port 8000
│     REST, WebSocket, MJPEG video, and the built front end
│
├── TelemetryTracker                           the latest state, cached
│
├── telemetry bridge thread   ← telemetry queue
├── frame bridge thread       ← frame queue      → VideoStream
│
└── Supervisor
      └── worker process  ← command queue
            Genesis: load scenario → scene.build() → physics loop
```

Three queues cross the process boundary: commands in, telemetry out, video
frames out.

## Why a process, not a thread

Genesis compiles kernels through Taichi and holds GPU context that cannot be
reliably torn down in-process. Swapping scenarios by restarting the worker
guarantees every scenario starts from a clean context, at the cost of a rebuild.
That rebuild is the pause you see when changing missions.

## Why two bridges

Telemetry dictionaries are small and frequent; JPEG frames are large. When they
shared a channel, frames delayed the state updates that clients poll to tell
whether a movement has finished — Python programs would hang waiting for a
movement that had already completed. Separate queues and separate threads keep
the small messages moving.

## The physics loop

`core/engine.py` steps the scene at 60 Hz and calls back after each step. The
callback, in `core/worker.py`, does four things between frames:

1. **Drain the command queue.** Camera moves, stops and scenario swaps take
   effect immediately; everything else buffers, so a program's steps play out
   one at a time instead of all at once.
2. **Advance the program.** When the arm is idle and its cooldown has elapsed,
   pop one buffered command and run it through the dispatch table in
   `core/commands.py`. `core/guardrails.py` decides whether it is allowed to.
3. **Publish.** `core/publishers.py` builds the telemetry dictionary and encodes
   the camera frame.
4. **Apply.** Feed the next waypoint to the arm's controller.

## Command flow

```
Browser or Python program
        │  POST /api/v1/command  or  POST /api/move_joints
        ▼
FastAPI  ──▶ command queue ──▶ worker: buffer or execute
                                    │
                                    ▼
                          RobotController: IK, trajectory
                                    │
                                    ▼
                       telemetry queue ──▶ tracker ──▶ WebSocket / REST
```

The API answers `202 Accepted` as soon as a command is queued; it never waits
for the physics. `429` means the queue is full.

## Two API surfaces

- **`/api/*`** is the real driver's contract (`manito-driver`). Implementing it
  is what lets one client drive both the simulator and the hardware.
  Endpoints the simulator cannot honestly implement answer `501`.
- **`/api/v1/*`** is the simulator's own: the block-level command queue,
  scenario catalog, video stream, script execution and telemetry WebSocket.
  The front end uses these.

## Scenario loading

`core/scenario.py` parses and validates YAML and imports no Genesis, so
`simctl validate` is fast and works without a GPU. `core/urdf_loader.py` takes
the validated result and registers entities with the engine.

Whether the native viewer opens is a property of the **command**
(`simctl viewer`), not of the scenario file.

## Run guardrails

A student program is a loop the simulator does not control, so the worker caps
each run at a number of commands and a wall-clock duration. Hitting either
clears the queue and records a reason, which reaches the UI through the
telemetry `lifecycle` field and the driver API's `last_error`. An aborted run
stays aborted until a new command arrives.
