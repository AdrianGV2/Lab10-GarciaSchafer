"""WebSocket push of simulation state to the front end."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ws", tags=["websocket_telemetry"])

# 10 Hz: enough for telemetry and block highlighting without saturating the
# event loop or starving the bridge thread that writes the state.
PUSH_INTERVAL = 0.1


@router.websocket("/state")
async def websocket_state_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected for state streaming.")

    tracker = websocket.app.state.tracker
    try:
        while True:
            state = tracker.poll_state()
            await websocket.send_json(
                {
                    "running": True,
                    "status": state.get("status", "active"),
                    "scenario_path": state.get("scenario_path"),
                    "active_robot": state.get("active_robot"),
                    "robot_end_effectors": state.get("robot_end_effectors", {}),
                    "robot_joints": state.get("robot_joints", {}),
                    "entities": state.get("entities", {}),
                    "current_block": state.get("current_block"),
                    "lifecycle": state.get("lifecycle"),
                }
            )
            await asyncio.sleep(PUSH_INTERVAL)
    except WebSocketDisconnect:
        logger.info("WebSocket closed by client.")
    except Exception as error:
        logger.error("WebSocket error: %s", error)
        try:
            await websocket.close()
        except Exception:
            pass
