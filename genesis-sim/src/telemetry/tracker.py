"""Cache of the latest simulation state, fed by the worker process."""

import numpy as np


def extract_pos_safe(entity_or_tensor):
    """Extract an XYZ position as plain Python floats, whatever the source type."""
    if hasattr(entity_or_tensor, "get_pos"):
        try:
            tensor_data = entity_or_tensor.get_pos()
        except Exception:
            return [0.0, 0.0, 0.0]
    else:
        tensor_data = entity_or_tensor

    if isinstance(tensor_data, np.ndarray):
        return tensor_data.tolist()
    if hasattr(tensor_data, "detach"):
        return tensor_data.detach().cpu().numpy().tolist()
    if hasattr(tensor_data, "cpu"):
        return tensor_data.cpu().numpy().tolist()
    if hasattr(tensor_data, "numpy"):
        return tensor_data.numpy().tolist()
    if hasattr(tensor_data, "to_numpy"):
        return tensor_data.to_numpy().tolist()
    if isinstance(tensor_data, (list, tuple)):
        return list(tensor_data)

    return [0.0, 0.0, 0.0]


EMPTY_STATE = {
    "status": "idle",
    "scenario_path": None,
    "active_robot": None,
    "robot_end_effectors": {},
    "robot_joints": {},
    "entities": {},
}


class TelemetryTracker:
    """Holds the most recent state published by the simulation worker.

    Lives in the parent process. The worker sends a fresh dictionary every
    frame over a multiprocessing queue; a bridge thread drops it in here and
    the API reads it from the WebSocket and REST handlers.
    """

    def __init__(self):
        self._last_state = dict(EMPTY_STATE)

    def update_from_worker(self, state: dict) -> None:
        """Replace the cached state with a frame published by the worker.

        No lock on purpose: the worker publishes a brand new dictionary each
        frame and never mutates the previous one, and rebinding or reading a
        reference is atomic in CPython. Avoiding the lock keeps the
        high-frequency WebSocket from starving this writer through contention,
        which used to freeze the state and leave Python clients waiting forever
        for a movement that had already finished.
        """
        self._last_state = state

    def poll_state(self) -> dict:
        """Return the most recent state as a copy."""
        return dict(self._last_state)
