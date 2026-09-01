"""Turning worker state into the payloads the parent process publishes.

Two channels leave the worker every frame: a telemetry dictionary that feeds
the tracker (and from there the WebSocket and the REST routes), and a JPEG
frame that feeds the MJPEG video stream. Both are built here so the worker loop
stays about physics.
"""

import logging

import cv2
import numpy as np

from src.telemetry.tracker import extract_pos_safe

logger = logging.getLogger(__name__)


def _joint_angles(controller) -> list:
    """Joint values in the units the UI and the firmware speak.

    Returns [J1 degrees, Z centimetres, J3 degrees, J4 degrees] for the SCARA
    arm, or raw values for anything with a different joint count.
    """
    from src.core.robot import _to_numpy

    qpos = _to_numpy(controller.robot.get_dofs_position())
    arm_qpos = qpos[controller.arm_dof]

    if len(arm_qpos) >= 4:
        return [
            round(np.rad2deg(arm_qpos[0])),
            round(arm_qpos[1] * 100),
            round(np.rad2deg(arm_qpos[2])),
            round(np.rad2deg(arm_qpos[3])),
        ]
    return [round(value, 2) for value in arm_qpos]


def build_telemetry(ctx) -> dict:
    """Snapshot the scene as the payload the parent process caches."""
    end_effectors = {}
    joints = {}
    for name, controller in ctx.controllers_registry.items():
        if controller.end_effector:
            end_effectors[name] = extract_pos_safe(controller.end_effector)
        try:
            joints[name] = _joint_angles(controller)
        except Exception:
            pass

    entities = {}
    for name, entity in ctx.entity_dict.items():
        if name in ctx.prop_names:
            continue  # static scenery never moves; no point streaming it
        try:
            entities[name] = extract_pos_safe(entity)
        except Exception:
            pass

    return {
        "status": "running",
        "scenario_path": ctx.scenario_path,
        "active_robot": ctx.active_robot_name,
        "robot_end_effectors": end_effectors,
        "robot_joints": joints,
        "entities": entities,
        "current_block": ctx.current_block,
        "busy": ctx.busy,
        "executed_total": ctx.executed_total,
        "gripper": ctx.robot.is_grasping,
        "is_homing": ctx.is_homing,
        "is_homed": ctx.is_homed,
        "lifecycle": ctx.guardrails.lifecycle,
    }


def encode_frame(cam, quality: int = 80):
    """Render the streaming camera to JPEG bytes, or None if it cannot render."""
    try:
        rgb_data = cam.render(rgb=True)
        image = rgb_data[0]

        if hasattr(image, "cpu"):
            image = image.detach().cpu().numpy()
        if image.dtype in (np.float32, np.float64):
            image = (np.clip(image, 0.0, 1.0) * 255).astype(np.uint8)

        conversion = cv2.COLOR_RGBA2BGR if image.shape[-1] == 4 else cv2.COLOR_RGB2BGR
        bgr = cv2.cvtColor(image, conversion)

        success, buffer = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buffer.tobytes() if success else None
    except Exception as error:
        logger.debug("Frame capture failed: %s", error)
        return None
