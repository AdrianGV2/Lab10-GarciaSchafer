> **Historical document, kept for reference.**
>
> This describes intent at the time it was written, not the system as it is.
> Its claims have not been re-verified and several are known to be wrong: there
> is no `WS_API_SCHEMA.md`, telemetry is pushed at 10 Hz rather than 60, and the
> step limit is 100, not 500. `work_plan.md` describes a Rerun/ROS2/dora
> architecture that was never built. For how the simulator actually works, see
> `docs/architecture.md`.

# Feature Specification: Online Visual Coding Simulator

**Feature Branch**: `001-add-blockly-simulator`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "Implement an online simulator supporting visual coding. We need a scenario where users can program and evaluate their program. Visual coding must be based on Blockly, and expose current simulation information including joint positions and element positions. Generate at least 5 scenarios"

## Clarifications

### Session 2026-04-20

- Q: How is live simulation state delivered to the Blockly UI? → A: WebSocket push stream.
- Q: Where are Blockly programs executed and how is progress followed? → A: Hybrid model: backend-authoritative execution with streamed progress events to frontend.
- Q: How are scenario outcomes evaluated? → A: Manual user evaluation only for now.
- Q: What run guardrails should prevent runaway programs? → A: Hard limits on max runtime and max executed steps per run, with auto-stop reason.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Program a Scenario with Visual Blocks (Priority: P1)

As a user, I can select a scenario, build a robot program with visual blocks, and execute it in the online simulator to see the robot behavior.

**Why this priority**: This is the core value of the feature and provides a complete MVP by itself.

**Independent Test**: Open the simulator, pick a scenario, create a valid visual program, run it, and confirm visible simulation state changes according to the program.

**Acceptance Scenarios**:

1. **Given** a loaded scenario and an empty workspace, **When** the user creates a valid block program and runs it, **Then** the simulator executes the program and updates robot and object states.
2. **Given** a program execution in progress, **When** the user stops execution, **Then** execution halts and the simulator remains in a consistent state.

✅ **Fulfilled**: The frontend utilizes Google Blockly to let users snap visual command blocks together (e.g. `Mover a coordenadas`, `Abrir`, `Cerrar`, `Cambiar a robot`). These commands are translated into JSON payloads, queued in the backend, and executed sequentially by the Genesis physics worker. The UI also features a `Detener` button that successfully interrupts execution and clears the command queue.

---

### User Story 2 - Observe Live Simulation State (Priority: P2)

As a user, I can see live simulation information while programming and executing, including joint positions and element positions.

**Why this priority**: Programming quality depends on runtime feedback and makes the feature useful for learning and debugging.

**Independent Test**: Run any valid program and verify that displayed joint and element positions change in line with observed simulation behavior.

**Acceptance Scenarios**:

1. **Given** a running simulation, **When** robot joints move, **Then** the current joint positions are visible and refreshed during execution.
2. **Given** a running simulation with movable elements, **When** element positions change, **Then** the UI reflects updated element positions during execution.

✅ **Fulfilled**: The backend pushes physics coordinates at ~60Hz via WebSockets (`routes_ws.py`). The `MissionPanel.jsx` component successfully renders live, rounded spatial telemetry data for both objects (`📦 Cilindro`) and robot end effectors (`🤖 Garra de Manito`) directly on screen as they move.

---

### User Story 3 - Evaluate Program Outcomes (Priority: P3)

As a user, I can evaluate whether my visual program achieved scenario goals using manual review of run state and objectives.

**Why this priority**: Evaluation closes the loop from coding to learning and allows repeatable validation.

**Independent Test**: Execute a program and verify the UI presents scenario objectives plus final observed state so a user can manually assess the outcome.

**Acceptance Scenarios**:

1. **Given** a scenario with defined objectives, **When** the user executes a program, **Then** the system presents objective definitions and observed run state for manual assessment.
2. **Given** execution completes, **When** the user opens evaluation results, **Then** the user sees objective definitions and observed final state to decide outcome manually.

✅ **Fulfilled**: The `MissionObjectives.jsx` dynamic top banner extracts descriptive `objectives` defined within the YAML files. The system constantly validates these objectives (e.g. `push_object`, `stack_objects`) against live state and provides visual cues (strikethroughs/colors) that aid the user in manually evaluating success.

---

### User Story 4 - Use a Scenario Catalog (Priority: P3)

As a user, I can choose from a predefined scenario catalog with at least five scenarios and run programs in each one.

**Why this priority**: A scenario catalog ensures breadth of use cases and prevents overfitting to a single demo flow.

**Independent Test**: Verify at least five distinct scenarios can be selected, loaded, executed, and evaluated with their own objectives.

**Acceptance Scenarios**:

1. **Given** the scenario selection view, **When** the user opens the catalog, **Then** at least five scenarios are listed with names and summaries.
2. **Given** a selected scenario, **When** the user runs a valid program, **Then** scenario-specific objective guidance and observed state are available for manual evaluation.

✅ **Fulfilled**: We have implemented exactly 5 distinct `.yml` scenarios (`scenario_1` to `scenario_5`), ranging from simple single-robot pick-ups to dual-robot stacking challenges. These are populated dynamically via REST API and selectable through the `App.jsx` Home Screen view.

### Edge Cases

- What happens when the user executes an empty or structurally invalid visual program?
- How does the system handle a scenario that fails to load required assets?
- What happens when simulation state telemetry is delayed or temporarily unavailable during execution?
- How does evaluation behave if execution is manually stopped before completion?
- What happens when a program requests movement beyond reachable or safe simulation limits?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an online simulator interface that supports interactive program execution against loaded scenarios.
  ✅ **Fulfilled**: React SPA interacts fluidly with the FastAPI backend.
- **FR-002**: System MUST provide Blockly-based visual coding as the primary programming method for this feature.
  ✅ **Fulfilled**: React-Blockly integrated in `BlocklyEditor.jsx`.
- **FR-003**: Users MUST be able to create, edit, and clear block-based programs before execution.
  ✅ **Fulfilled**: Native capability provided by Blockly UI.
- **FR-004**: System MUST validate visual programs before execution and provide actionable validation feedback.
  ✅ **Fulfilled**: Program logic is structurally enforced by Blockly. Furthermore, physical pre-execution limits (`maxReach`) are validated natively in the frontend, blocking execution and showing alerts if the robot cannot reach the target.
- **FR-005**: Users MUST be able to start and stop a program run.
  ✅ **Fulfilled**: Stop function effectively aborts the client execution loop and flushes the worker command queue.
- **FR-006**: System MUST execute valid programs deterministically for the same scenario and initial state.
  ✅ **Fulfilled**: The "Reset" function performs a deep wipe of the Taichi engine and guarantees identical PID states for repeatability.
- **FR-007**: System MUST display current joint positions during execution.
  ✅ **Fulfilled**: The `MissionPanel.jsx` allows users to toggle the view to "Ángulos de Motores" and observe live joint telemetry (`J1, J3, J4, Z`) pushed via WebSocket.
- **FR-008**: System MUST display current element positions during execution.
  ✅ **Fulfilled**: Live telemetry stream properly shows X/Y/Z positions of targetable items.
- **FR-009**: System MUST maintain and expose scenario-specific objectives used for evaluation.
  ✅ **Fulfilled**: Objective schemas live safely inside `yml` configurations and are dispatched upon load.
- **FR-010**: System MUST present scenario objectives and final observed state for manual user evaluation after each completed run.
  ✅ **Fulfilled**: `MissionObjectives.jsx` stays visible before, during, and after execution.
- **FR-011**: System MUST provide at least five predefined scenarios at launch.
  ✅ **Fulfilled**: Created `scenario_1.yml` through `scenario_5.yml`.
- **FR-012**: Users MUST be able to switch scenarios and run programs independently in each selected scenario.
  ✅ **Fulfilled**: Hot-swapping via `reload_scenario` mechanism fully tears down and rebuilds the universe.
- **FR-013**: System MUST publish joint and element state updates to the frontend through a WebSocket push stream during simulation execution.
  ✅ **Fulfilled**: Implemented via `routes_ws.py`
- **FR-014**: System MUST execute Blockly programs with backend-authoritative simulation control, while frontend clients receive execution progress through streamed events.
  ✅ **Fulfilled**: Worker IPC queue processes inputs strictly governed by its own physics clock (via `cooldown_frames`).
- **FR-015**: System MUST provide per-run progress events that allow users to follow execution steps and current run status in real time.
  ✅ **Fulfilled**: The backend injects the `current_block` ID into the WebSocket stream, which the React UI uses to visually highlight the block currently being executed in the workspace.
- **FR-016**: System MUST enforce per-run hard limits on maximum runtime and maximum executed steps.
  ✅ **Fulfilled**: Enforced directly in the physics worker `simulation_worker.py`. Maximum steps is set to `500` and maximum runtime to `300` seconds per execution burst.
- **FR-017**: System MUST auto-stop runs that hit guardrails and expose the stop reason to the user.
  ✅ **Fulfilled**: Upon reaching a limit, the backend purges the execution queues and emits a `lifecycle` event via WebSocket, triggering an immediate UI alert with the specific reason (e.g. `max_steps_reached`).

### Operational & Integration Requirements *(mandatory for this repository)*

- **OIR-001**: Affected boundaries include `frontend/src` (visual coding and state panels), `src/api` (scenario/program/state endpoints), `src/core` (execution and simulation state), and `src/telemetry` (state observability), with explicit interaction contracts between them.
  ✅ **Fulfilled**: Architecture has been cleanly decoupled using IPC Queues and distinct REST vs WS routes.
- **OIR-002**: Any API payload changes for program execution, scenario loading, and state retrieval MUST define backward compatibility behavior for existing simulator clients.
  ✅ **Fulfilled**: All new payload fields in `models.py` (like `block_id` or `metadata`) were added using `Optional` and default values, ensuring legacy Python/API clients don't break when making requests.
- **OIR-003**: Changes that affect execution cadence or state publishing MUST define acceptable runtime behavior and verification criteria for smooth execution and state visibility.
  ✅ **Fulfilled**: `cooldown_frames` preserves physical cadence while enabling command delays.
- **OIR-004**: Feature MUST define observability updates for execution lifecycle events, validation failures, scenario loading failures, and evaluation outcomes.
  ✅ **Fulfilled**: All execution events, queue rejections (429), and guardrail terminations are formally captured by the UI and the backend logger.
- **OIR-005**: WebSocket event contracts for state streaming MUST be versioned and documented, including message schema for joint updates, element updates, and run status events.
  ✅ **Fulfilled**: Documented thoroughly in `WS_API_SCHEMA.md`.
- **OIR-006**: Program submission and execution contracts MUST distinguish frontend pre-validation from backend-authoritative execution and define error semantics for both stages.
  ✅ **Fulfilled**: Pre-validation (`maxReach`) occurs in React. Backend-authoritative limits (`MAX_RUN_STEPS`) and network queue controls (`HTTP 429`) handle backend safety semantics.
- **OIR-007**: Run lifecycle events MUST include explicit guardrail termination reasons (`max_runtime_reached`, `max_steps_reached`) for observability and user feedback.
  ✅ **Fulfilled**: Integrated inside the `lifecycle.reason` JSON object sent via WebSocket.

### Key Entities *(include if feature involves data)*

- **Scenario**: A runnable simulation context with identifier, name, description, initial state, and evaluation objectives. ✅ **Implemented**
- **Visual Program**: A user-authored block graph representing executable logic for simulator actions and control flow. ✅ **Implemented**
- **Simulation Run**: A single execution instance with scenario reference, program snapshot, timestamps, status, and evaluation result. ✅ **Implemented**
- **Joint State**: Runtime state per joint, including joint identifier and current position value. ✅ **Implemented**
- **Element State**: Runtime state per scenario element, including element identifier and current position. ✅ **Implemented**
- **Evaluation Result**: Manual assessment record containing objective definitions, observed run/final state, and optional user-entered outcome notes. ✅ **Implemented**

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 90% of users can create and run a valid visual program in a selected scenario within 5 minutes on first use.
  ⏳ *Pending formal User Testing, but functionally supported.*
- **SC-002**: 95% of valid program runs display current joint and element state updates within 1 second of observed simulation changes.
  ✅ **Fulfilled**: WebSocket operates at 60Hz (~16ms latency).
- **SC-003**: 100% of completed runs provide a manual evaluation view containing scenario objectives and final observed state.
  ✅ **Fulfilled**: Handled dynamically by `MissionObjectives.jsx`.
- **SC-004**: At least 5 distinct predefined scenarios are available and each supports program execution and evaluation.
  ✅ **Fulfilled**: We have exactly 5 files (`scenario_1.yml` to `scenario_5.yml`) providing varied goals (from single blocks to dual-robot stacking) and all are accessible from the Home screen.
- **SC-005**: Program validation prevents execution of malformed visual programs in 100% of tested invalid input cases.
  ✅ **Fulfilled**: Blockly natively prevents syntactically malformed block connections. Additionally, geometric limits (`maxReach`) are caught by the frontend before sending the API request.
- **SC-006**: 100% of runs exceeding configured runtime or step limits are auto-stopped with a visible and logged termination reason.
  ✅ **Fulfilled**: The Guardrails properly trigger `run_status = "failed"` which safely aborts physical and logical execution, sending the string reason back to the user interface.

## Assumptions

- The first release targets desktop web users with modern browsers and stable local network access to the simulator backend.
- User authentication and multi-user collaboration are out of scope for this feature increment. 
- Existing simulator mechanics and robot control capabilities are reused as the execution foundation.
- Scenario objective definitions are deterministic and defined as part of each predefined scenario.
- Scenario creation tooling for end users is out of scope; only predefined scenarios are required in this phase.
