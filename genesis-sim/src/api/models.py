"""Pydantic models for API requests and responses.

This module defines the data structures for communication between the REST API
and the Genesis simulation engine.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    """Request model for simulation commands.

    Represents a command to be sent to the simulation engine. Supports basic
    movement and control commands with optional parameters.

    Attributes:
        action: Type of command to execute (e.g., "move_robot", "reset", "step").
        x: Optional X coordinate or parameter value.
        y: Optional Y coordinate or parameter value.
        z: Optional Z coordinate or parameter value.
        metadata: Optional dictionary for additional command parameters.

    Example:
        >>> cmd = CommandRequest(action="move_robot", x=1.0, y=2.0, z=0.5)
        >>> cmd.model_dump()
        {'action': 'move_robot', 'x': 1.0, 'y': 2.0, 'z': 0.5, 'metadata': None}
    """

    action: str = Field(..., description="Command action type")
    x: Optional[float] = Field(None, description="X coordinate or parameter")
    y: Optional[float] = Field(None, description="Y coordinate or parameter")
    z: Optional[float] = Field(None, description="Z coordinate or parameter")
    zoom: Optional[float] = Field(None, description="Zoom parameter for camera")
    scenario: Optional[str] = Field(None, description="Path to scenario YML file for hot-swapping")
    robot_name: Optional[str] = Field(None, description="Name of the robot to switch to")
    block_id: Optional[str] = Field(None, description="Blockly block ID associated with this command")
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata or parameters for the command",
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "action": "move_robot",
                "x": 1.0,
                "y": 2.0,
                "z": 0.5,
                "metadata": {"joint": "arm_1"},
            }
        }


class CommandResponse(BaseModel):
    """Response model for command execution.

    Indicates the status of command processing by the simulation engine.

    Attributes:
        status: Status of command processing ("accepted", "rejected", "error").
        message: Human-readable status message.
        command_id: Optional identifier for the processed command.
        payload: Optional response data from the simulation.

    Example:
        >>> resp = CommandResponse(status="accepted", message="Command queued")
        >>> resp.model_dump()
        {'status': 'accepted', 'message': 'Command queued', ...}
    """

    status: str = Field(
        ...,
        description="Command processing status",
    )
    message: str = Field(..., description="Status message")
    command_id: Optional[str] = Field(None, description="Command identifier")
    payload: Optional[Dict[str, Any]] = Field(
        None,
        description="Response payload from simulation",
    )


class SimulationState(BaseModel):
    """Model representing the current simulation state.

    Used for status endpoints and state monitoring.

    Attributes:
        running: Whether the simulation is currently running.
        step_count: Current simulation step number.
        fps: Current frames per second or physics step rate.
        status: Human-readable status string.
    """

    running: bool = Field(..., description="Simulation running status")
    step_count: int = Field(default=0, description="Current simulation step")
    fps: Optional[float] = Field(None, description="Current simulation FPS")
    status: str = Field(default="idle", description="Current system status")
    active_robot: Optional[str] = Field(None, description="Name of the currently active robot")
    robot_end_effectors: Optional[Dict[str, list[float]]] = Field(None, description="Dictionary mapping robot names to their end effector XYZ coordinates")
    entities: Optional[Dict[str, list[float]]] = Field(None, description="Dictionary mapping entity names to their XYZ coordinates")
