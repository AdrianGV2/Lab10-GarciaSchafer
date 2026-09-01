"""The simulator's own command and state endpoints, used by the front end."""

import logging
from queue import Full

from fastapi import APIRouter, HTTPException, Request, status

from src.api.models import CommandRequest, CommandResponse, SimulationState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["robot_control"])


@router.post(
    "/command", response_model=CommandResponse, status_code=status.HTTP_202_ACCEPTED
)
def submit_command(request: Request, command: CommandRequest):
    queue = request.app.state.command_queue
    tracker = request.app.state.tracker

    if command.action == "reload_scenario":
        tracker.update_from_worker(
            {"status": "loading", "robot_end_effectors": {}, "entities": {}}
        )

    try:
        queue.put_nowait(command.model_dump())
    except Full:
        raise HTTPException(status_code=429, detail="Command queue is full")

    return CommandResponse(
        status="accepted",
        message="Command queued",
        command_id=None,
        payload={"action": command.action},
    )


@router.get("/state", response_model=SimulationState)
def get_state(request: Request):
    data = request.app.state.tracker.poll_state()
    return SimulationState(
        running=True,
        status="active",
        active_robot=data.get("active_robot"),
        robot_end_effectors=data.get("robot_end_effectors"),
        entities=data.get("entities"),
    )
