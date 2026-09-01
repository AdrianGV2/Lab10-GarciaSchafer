"""Threads that carry data from the worker process into the parent.

State and video travel on separate queues and separate threads on purpose: a
JPEG frame is orders of magnitude larger than a telemetry dictionary, and when
they shared a channel the frames delayed the state updates that clients poll to
tell whether a movement has finished.
"""

import logging
import queue
import threading

logger = logging.getLogger(__name__)


class MPQueueAdapter:
    """Expose a `queue.Queue` interface over a `multiprocessing.Queue`.

    The API layer is written against the standard queue interface but its
    commands have to cross into the worker process, so the real queue underneath
    is a multiprocessing one.
    """

    def __init__(self, mp_queue):
        self._queue = mp_queue

    def put_nowait(self, item):
        try:
            self._queue.put_nowait(item)
        except Exception:
            raise queue.Full

    def get_nowait(self):
        try:
            return self._queue.get_nowait()
        except Exception:
            raise queue.Empty

    def empty(self):
        return self._queue.empty()

    def get(self, block=True, timeout=None):
        return self._queue.get(block=block, timeout=timeout)

    def put(self, item, block=True, timeout=None):
        return self._queue.put(item, block=block, timeout=timeout)


def telemetry_bridge(telemetry_queue, tracker, stop_event, next_scenario, reload_signal):
    """Feed worker telemetry into the tracker until asked to stop.

    A reload signal on this queue is not telemetry: it records the scenario to
    load next and ends the bridge so the supervisor can respawn the worker.
    """
    while not stop_event.is_set():
        try:
            data = telemetry_queue.get(timeout=0.5)
        except Exception:
            continue  # timed out, or the queue is gone

        if not isinstance(data, dict):
            continue

        if data.get("__signal__") == reload_signal:
            next_scenario["reload"] = True
            next_scenario["path"] = data["scenario"]
            logger.info("[Bridge] Reload requested: %s", data["scenario"])
            return

        tracker.update_from_worker(data)


def frame_bridge(frame_queue, stop_event, publish_frame):
    """Feed rendered frames into the MJPEG stream until asked to stop."""
    while not stop_event.is_set():
        try:
            frame = frame_queue.get(timeout=0.5)
        except Exception:
            continue
        publish_frame(frame)
