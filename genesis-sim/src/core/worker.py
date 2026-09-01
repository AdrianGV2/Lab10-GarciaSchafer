"""The simulation worker process.

The only place Genesis is ever initialised. Runs one scenario to completion in
its own process, so a scenario swap is a process restart and every run starts
from a clean GPU context. Talks to the parent over three queues: commands in,
telemetry out, video frames out.
"""

import logging
import queue

from src.core import commands as command_module
from src.core.commands import IMMEDIATE_ACTIONS, CommandContext
from src.core.guardrails import RunGuardrails
from src.core.publishers import build_telemetry, encode_frame

logger = logging.getLogger(__name__)

# Sent on the telemetry queue to tell the parent to respawn us on a new scene.
SIGNAL_RELOAD = "__RELOAD__"


def run_simulation_worker(
    scenario_path: str,
    command_queue,
    telemetry_queue,
    frame_queue,
    settings,
    show_viewer: bool = False,
    verbose: bool = False,
):
    """Load a scenario and run its physics loop until told to stop or reload."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Imported here rather than at module scope: these pull in Genesis, which
    # must only ever be loaded inside this process.
    from src.core import engine, urdf_loader
    from src.core.camera import CameraController
    from src.core.robot import RobotController
    from src.core.scenario import load_scenario

    try:
        logger.info("[Worker] Initialising Genesis for %s", scenario_path)
        config = load_scenario(scenario_path)
        urdf_loader.initialize_genesis(settings.backend)

        scene, robot_entity, cam, entity_dict, prop_names = urdf_loader.build_scene(
            config, show_viewer=show_viewer
        )
        logger.info("[Worker] Building scene (compiling physics)...")
        scene.build()

        controllers = {}
        for name, entity in entity_dict.items():
            if name.lower().startswith(("manito", "robot")):
                controllers[name] = RobotController(entity)
                if entity is not robot_entity:
                    controllers[name].hibernate()

        active_name = next(
            name for name, entity in entity_dict.items() if entity is robot_entity
        )

        ctx = CommandContext(
            scene=scene,
            cam=cam,
            cam_controller=CameraController(cam),
            controllers_registry=controllers,
            entity_dict=entity_dict,
            prop_names=prop_names,
            active_robot_name=active_name,
            scenario_path=scenario_path,
            guardrails=RunGuardrails(settings.max_run_steps, settings.max_runtime_sec),
            cooldown_frames=settings.cooldown_frames,
        )

        def step_handler(step_count: int, scene) -> None:
            _consume_commands(ctx, command_queue, telemetry_queue)
            _advance_program(ctx)

            try:
                telemetry_queue.put_nowait(build_telemetry(ctx))
            except Exception:
                pass  # a full queue means the parent is behind; drop this frame

            frame = encode_frame(cam, settings.jpeg_quality)
            if frame is not None:
                try:
                    frame_queue.put_nowait(frame)
                except Exception:
                    pass

            next_qpos = ctx.active_path.pop(0) if ctx.active_path else None
            ctx.robot.update_hardware_state(next_qpos)

        logger.info("[Worker] Starting simulation loop...")
        engine.run(scene, step_callback=step_handler, cam=cam)

    except engine.ReloadScenarioException as error:
        logger.info("[Worker] Clean exit for scenario reload: %s", error)
    except Exception as error:
        logger.error("[Worker] Fatal error: %s", error, exc_info=True)
        raise


def _consume_commands(ctx: CommandContext, command_queue, telemetry_queue) -> None:
    """Drain the queue, running immediate commands and buffering the rest."""
    from src.core.engine import ReloadScenarioException

    while True:
        try:
            command = command_queue.get_nowait()
        except queue.Empty:
            return
        except Exception:
            return

        action = str(command.get("action", "")).lower()

        if action in IMMEDIATE_ACTIONS:
            if action in ("stop_program", "estop"):
                command_module.drain(command_queue)

            reload_target = command_module.execute(ctx, command)
            if reload_target is not None:
                telemetry_queue.put(
                    {"__signal__": SIGNAL_RELOAD, "scenario": reload_target}
                )
                raise ReloadScenarioException(reload_target)
        else:
            # A command arriving after an abort is a new program, not a
            # continuation of the one that was stopped.
            ctx.guardrails.begin_run()
            ctx.pending_commands.append(command)


def _advance_program(ctx: CommandContext) -> None:
    """Start the next buffered command once the arm is free."""
    if ctx.active_path:
        return

    if ctx.cooldown_frames > 0:
        ctx.cooldown_frames -= 1
        return

    if not ctx.pending_commands:
        if ctx.is_homing:
            ctx.is_homing = False
            ctx.is_homed = True
        ctx.guardrails.finish_run()
        ctx.current_block = None
        return

    if not ctx.guardrails.allow_step():
        ctx.clear_program()
        return

    ctx.executed_total += 1
    command_module.execute(ctx, ctx.pending_commands.pop(0))
    # Pause between commands so a program's steps stay legible on screen.
    ctx.cooldown_frames = ctx.cooldown_setting
