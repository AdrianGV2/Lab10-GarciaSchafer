"""Command dispatch for the simulation worker.

Every action the API can queue has one handler here, registered in `HANDLERS`.
A handler mutates the `CommandContext` and returns None, except
`reload_scenario`, which returns the path of the scenario to switch to so the
worker can exit cleanly and let the supervisor respawn it.
"""

import logging
import queue
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.core.guardrails import RunGuardrails
from src.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

# Actions that must take effect on the frame they arrive rather than queue up
# behind the program: camera moves, aborts, and scenario swaps.
IMMEDIATE_ACTIONS = frozenset(
    {
        "camera_zoom",
        "camera_lift",
        "camera_lateral",
        "stop_program",
        "estop",
        "reload_scenario",
    }
)


class CommandContext:
    """Everything a handler may touch, in one place.

    Replaces the closure the worker used to be: handlers used to reach for
    `nonlocal` bindings, which made the execution state impossible to inspect
    or test on its own.
    """

    def __init__(
        self,
        scene,
        cam,
        cam_controller,
        controllers_registry: Dict[str, Any],
        entity_dict: Dict[str, Any],
        prop_names,
        active_robot_name: str,
        scenario_path: str,
        guardrails: RunGuardrails,
        cooldown_frames: int,
    ):
        self.scene = scene
        self.cam = cam
        self.cam_controller = cam_controller
        self.controllers_registry = controllers_registry
        self.entity_dict = entity_dict
        self.prop_names = prop_names
        self.scenario_path = scenario_path
        self.guardrails = guardrails

        self.initial_robot_name = active_robot_name
        self.active_robot_name = active_robot_name
        self.robot = controllers_registry[active_robot_name]

        # Execution state
        self.active_path: List[Any] = []
        self.pending_commands: List[dict] = []
        self.cooldown_setting = cooldown_frames
        self.cooldown_frames = 0
        self.current_block: Optional[str] = None
        self.executed_total = 0
        self.is_homing = False
        self.is_homed = False

    @property
    def busy(self) -> bool:
        return bool(self.active_path or self.pending_commands or self.cooldown_frames)

    def clear_program(self) -> None:
        """Drop everything queued, leaving the arm where it stands."""
        self.active_path.clear()
        self.pending_commands.clear()
        self.current_block = None
        self.is_homing = False


# -- handlers -------------------------------------------------------------


def _move_to(ctx: CommandContext, command: dict):
    ctx.active_path.extend(
        ctx.robot.move_to(command.get("x"), command.get("y"), command.get("z"))
    )


def _move_joints(ctx: CommandContext, command: dict):
    ctx.active_path.extend(ctx.robot.handle_fk_action(command))


def _grasp(ctx: CommandContext, command: dict):
    ctx.robot.grasp()


def _release(ctx: CommandContext, command: dict):
    ctx.robot.release()


def _home(ctx: CommandContext, command: dict):
    ctx.is_homing = True
    ctx.active_path.extend(ctx.robot.home())


def _reset(ctx: CommandContext, command: dict):
    from src.core.robot import global_scene_reset

    ctx.controllers_registry, ctx.robot = global_scene_reset(
        ctx.scene, ctx.controllers_registry, ctx.initial_robot_name
    )
    ctx.active_robot_name = ctx.initial_robot_name
    ctx.clear_program()
    ctx.is_homed = False
    ctx.guardrails.reset()


def _camera_zoom(ctx: CommandContext, command: dict):
    value = command.get("zoom")
    if value is None:
        value = command.get("x", 0.0)
    ctx.cam_controller.zoom(float(value))


def _camera_lift(ctx: CommandContext, command: dict):
    ctx.cam_controller.elevate(float(command.get("z", 0.0)))


def _camera_lateral(ctx: CommandContext, command: dict):
    ctx.cam_controller.pan(float(command.get("y", 0.0)))


def _switch_robot(ctx: CommandContext, command: dict):
    from src.core.robot import switch_active_robot

    new_name, new_robot, ok = switch_active_robot(
        command, ctx.controllers_registry, ctx.robot
    )
    if ok:
        ctx.active_robot_name = new_name
        ctx.robot = new_robot
        ctx.active_path.clear()


def _stop_program(ctx: CommandContext, command: dict):
    ctx.clear_program()
    ctx.guardrails.stop("user_stopped")


def _reload_scenario(ctx: CommandContext, command: dict) -> Optional[str]:
    metadata = command.get("metadata") or {}
    new_path = (
        metadata.get("scenario") or command.get("scenario") or ctx.scenario_path
    )

    if (PROJECT_ROOT / new_path).exists() or Path(new_path).exists():
        return new_path

    fallback = Path("configs/scenarios") / new_path
    if (PROJECT_ROOT / fallback).exists():
        return str(fallback)

    logger.error("[Worker] Scenario file not found: %s", new_path)
    return None


HANDLERS: Dict[str, Callable[[CommandContext, dict], Optional[str]]] = {
    "move_to": _move_to,
    "move_joints": _move_joints,
    "move_joints_fk": _move_joints,
    "cierra": _grasp,
    "abre": _release,
    "home": _home,
    "reset": _reset,
    "camera_zoom": _camera_zoom,
    "camera_lift": _camera_lift,
    "camera_lateral": _camera_lateral,
    "switch_robot": _switch_robot,
    "stop_program": _stop_program,
    "estop": _stop_program,
    "reload_scenario": _reload_scenario,
}


def execute(ctx: CommandContext, command: dict) -> Optional[str]:
    """Run one command. Returns a scenario path when a reload was requested."""
    action = str(command.get("action", "")).lower()
    handler = HANDLERS.get(action)
    if handler is None:
        logger.warning("[Worker] Unknown action %r, ignored.", action)
        return None

    ctx.current_block = command.get("block_id")
    try:
        return handler(ctx, command)
    except Exception as error:
        logger.error("[Worker] Error handling %r: %s", action, error, exc_info=True)
        return None


def drain(command_queue) -> None:
    """Discard everything waiting in the queue."""
    while True:
        try:
            command_queue.get_nowait()
        except queue.Empty:
            return
        except Exception:
            return
