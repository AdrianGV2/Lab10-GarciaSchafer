> **Historical document, kept for reference.**
>
> This describes intent at the time it was written, not the system as it is.
> Its claims have not been re-verified and several are known to be wrong: there
> is no `WS_API_SCHEMA.md`, telemetry is pushed at 10 Hz rather than 60, and the
> step limit is 100, not 500. `work_plan.md` describes a Rerun/ROS2/dora
> architecture that was never built. For how the simulator actually works, see
> `docs/architecture.md`.

**TL;DR:** We are integrating `rerun-sdk` into the architecture to handle real-time 3D visualization and telemetry logging. This adds a dedicated module to stream robot poses, joint states, and simulated camera feeds to the Rerun viewer, providing a powerful debugging tool alongside your FastAPI server and Genesis engine.

Here is the updated architecture document, now including Rerun as a core component for telemetry and visualization. You can provide this complete specification to your LLM.

---

# System Specification: Genesis URDF Simulator with REST API & Rerun Telemetry

## 1. Project Overview

Build a modular, asynchronous robot simulator using the **Genesis** physics engine. The simulator must run a continuous physics loop in the background while exposing a **FastAPI REST API** for external management (spawning objects, moving the robot, resetting the environment) and a **Typer CLI** for local testing and server lifecycle management.

To ensure robust observability, the system will use **Rerun** to stream and visualize real-time 3D telemetry (transforms, bounding boxes, simulated camera feeds, and joint states). The project must be managed using `uv` for dependencies and structured to allow future integration with ROS2 and Dora-rs.

## 2. Tech Stack

* **Dependency Management:** `uv`
* **Physics Engine:** `genesis-world`
* **API Framework:** `fastapi`, `uvicorn`
* **CLI Framework:** `typer`
* **Config Management:** `pyyaml`
* **Telemetry & Visualization:** `rerun-sdk`
* **Language:** Python 3.10+

## 3. Directory Structure

Generate the project using the following strict directory structure:

```text
genesis_sim_project/
├── pyproject.toml             
├── configs/                   
│   ├── robots/                # URDF config parameters
│   └── scenarios/             # YAML files defining pick-and-place scenes
└── src/                       
    ├── cli.py                 # CLI entry points
    ├── api/                   
    │   ├── server.py          # FastAPI app and thread-safe queues
    │   ├── routes_sim.py      # /sim/* endpoints
    │   └── routes_robot.py    # /robot/* endpoints
    ├── core/                  
    │   ├── engine.py          # Genesis simulation loop and Async Bridge
    │   ├── urdf_loader.py     # URDF parsing and Genesis asset registration
    │   └── robot.py           # Kinematics and joint control wrappers
    ├── telemetry/             
    │   └── rerun_logger.py    # Rerun SDK integration for 3D state streaming
    └── middleware/            
        ├── ros2_node.py       # Placeholder for rclpy integration
        └── dora_node.py       # Placeholder for dora-rs integration

```

## 4. Module Responsibilities (Context for the LLM)

### A. `src/core/urdf_loader.py`

* **Role:** Strictly handles reading URDF files and registering them into a provided Genesis `gs.Scene`.
* **Methods:** `load_robot(urdf_path, position)` returns a `gs.Entity`.

### B. `src/core/engine.py` (The Async Bridge)

* **Role:** Manages the Genesis lifecycle (`gs.init()`, creating the scene, building the scene).
* **Concurrency:** Must contain a mechanism (like a background thread or `asyncio` task) to run the `scene.step()` loop continuously at a fixed timestep (e.g., 60Hz).
* **State Management:** Must read from a thread-safe `queue.Queue` or `asyncio.Queue` to receive commands from the FastAPI server without blocking the physics loop.
* **Telemetry Hook:** At the end of each `step()`, calls the Rerun logger to push the updated environment state.

### C. `src/telemetry/rerun_logger.py`

* **Role:** Manages the connection to the Rerun viewer (either spawning a local viewer or connecting to a remote one via TCP).
* **Functions Required:**
* `init_logger()`: Starts the Rerun process (`rr.init("genesis_sim", spawn=True)`).
* `log_robot_state(entity)`: Extracts 3D poses (TF trees) and joint angles from the Genesis entity and logs them using `rr.log()`.
* `log_scenario_objects(objects)`: Logs bounding boxes and positions of spawned pick-and-place items.



### D. `src/api/server.py` & Routes

* **Role:** Initializes the FastAPI application and the background Genesis engine.
* **Endpoints Required:**
* `GET /sim/state`: Returns physics engine status.
* `POST /sim/reset`: Resets the Genesis scene.
* `POST /sim/scenario/{name}`: Parses a YAML from `configs/scenarios/` and spawns the defined environment.
* `POST /robot/joints`: Accepts a JSON payload of joint angles and passes them to the engine queue.



### E. `src/cli.py`

* **Role:** The entry point for the user. Uses Typer.
* **Commands Required:**
* `simctl run-local <urdf_path>`: Instantiates the engine directly with the viewer open.
* `simctl server start --port 8000`: Launches the Uvicorn server and the background Genesis engine.
* `simctl server start --with-rerun`: Launches the server and explicitly initializes the Rerun viewer for telemetry debugging.



## 5. Implementation Phases (Instructions for LLM)

* **Phase 1: Foundation.** Write `pyproject.toml` using `uv` formatting. Implement `urdf_loader.py`, a basic blocking `engine.py`, and `cli.py` to prove the URDF renders in the Genesis viewer.
* **Phase 2: Telemetry Integration.** Implement `telemetry/rerun_logger.py`. Hook it into the engine's step loop so that when `simctl run-local` is executed, the robot's pose is simultaneously streamed to the Rerun viewer.
* **Phase 3: The Bridge.** Refactor `engine.py` to run the `step()` loop in a background thread. Implement `api/server.py` and connect it to `cli.py` so `simctl server start` runs the API, the physics loop, and the Rerun logger concurrently.
* **Phase 4: Routing.** Implement `routes_sim.py` and `routes_robot.py`. Ensure the POST requests successfully pass data through the queue to alter the running simulation.
* **Phase 5: Scenarios.** Add YAML parsing logic to read a simple pick-and-place configuration and spawn basic primitive shapes (cubes, spheres) around the robot, ensuring they are also logged to Rerun.

## 6. Coding Guidelines

* Use strict Python type hinting (`-> type`, `:`).
* Include Google-style docstrings for all classes and major functions.
* Ensure all Genesis imports and initializations fail gracefully with clear error messages if the GPU backend is unavailable.
* Keep functions small and strictly adhered to their module's responsibility.
