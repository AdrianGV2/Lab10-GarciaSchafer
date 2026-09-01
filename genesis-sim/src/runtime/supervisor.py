"""Owns the simulation worker process and its lifecycle.

The parent process never touches Genesis. It spawns a worker for one scenario,
bridges its output, and — when the worker asks for a scenario swap — respawns
it. Restarting the process is what guarantees a clean GPU context per scenario.
"""

import logging
import multiprocessing as mp
import threading

from src.runtime.bridges import frame_bridge, telemetry_bridge

logger = logging.getLogger(__name__)

IDLE = "idle"


def _worker_entry(scenario_path, command_queue, telemetry_queue, frame_queue, settings, show_viewer, verbose):
    """Child-process entry point; imports Genesis only once we are in the child."""
    from src.core.worker import run_simulation_worker

    run_simulation_worker(
        scenario_path,
        command_queue,
        telemetry_queue,
        frame_queue,
        settings,
        show_viewer=show_viewer,
        verbose=verbose,
    )


class Supervisor:
    """Runs scenarios one at a time, restarting the worker on each swap."""

    def __init__(
        self,
        settings,
        tracker,
        command_queue,
        publish_frame,
        show_viewer=False,
        verbose=False,
    ):
        self.settings = settings
        self.tracker = tracker
        self.command_queue = command_queue
        # Where rendered frames go. The API's video stream when one is running,
        # a no-op when the simulator runs with no API at all.
        self.publish_frame = publish_frame
        self.show_viewer = show_viewer
        self.verbose = verbose

        self._stop = threading.Event()
        self._worker = None
        self.last_exitcode = 0

    def stop(self) -> None:
        """Ask the supervisor to shut down and kill the running worker."""
        self._stop.set()
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.terminate()

    def run(self, scenario_path: str) -> int:
        """Run scenarios until stopped. Returns the last worker exit code.

        `scenario_path` may be `"idle"`, in which case the API stays up and the
        supervisor waits for the front end to choose a scenario.
        """
        current = scenario_path

        while not self._stop.is_set():
            if current == IDLE:
                current = self._wait_for_scenario()
                if current is None:
                    break
                continue

            reload_to = self._run_once(current)
            if reload_to is None:
                break
            current = reload_to
            logger.info("[Supervisor] Hot-swap: loading %s", current)

        return self.last_exitcode

    def _wait_for_scenario(self):
        """Block in idle mode until a reload command names a scenario."""
        logger.info("[Supervisor] Idle: API is up, waiting for a scenario...")
        while not self._stop.is_set():
            try:
                command = self.command_queue.get(timeout=0.5)
            except Exception:
                continue
            if command.get("action") == "reload_scenario":
                scenario = command.get("scenario") or (
                    command.get("metadata") or {}
                ).get("scenario")
                if scenario:
                    logger.info("[Supervisor] Leaving idle for %s", scenario)
                    return scenario
        return None

    def _run_once(self, scenario_path: str):
        """Run one scenario to completion. Returns the next scenario, or None."""
        from src.core.worker import SIGNAL_RELOAD

        logger.info("[Supervisor] Spawning worker for %s", scenario_path)

        telemetry_queue = mp.Queue(maxsize=100)
        frame_queue = mp.Queue(maxsize=4)

        self._worker = mp.Process(
            target=_worker_entry,
            args=(
                scenario_path,
                self.command_queue,
                telemetry_queue,
                frame_queue,
                self.settings,
                self.show_viewer,
                self.verbose,
            ),
            daemon=True,
        )
        self._worker.start()

        bridge_stop = threading.Event()
        next_scenario = {"path": scenario_path}

        threads = [
            threading.Thread(
                target=telemetry_bridge,
                args=(
                    telemetry_queue,
                    self.tracker,
                    bridge_stop,
                    next_scenario,
                    SIGNAL_RELOAD,
                ),
                daemon=True,
            ),
            threading.Thread(
                target=frame_bridge,
                args=(frame_queue, bridge_stop, self.publish_frame),
                daemon=True,
            ),
        ]
        for thread in threads:
            thread.start()

        while self._worker.is_alive() and not self._stop.is_set():
            self._worker.join(timeout=0.5)

        if self._stop.is_set() and self._worker.is_alive():
            self._worker.terminate()
            self._worker.join(timeout=2.0)

        bridge_stop.set()
        for thread in threads:
            thread.join(timeout=2.0)

        reloading = next_scenario.get("reload", False)

        if self._stop.is_set():
            # We terminated the worker on purpose, so its exit code describes
            # our signal, not a failure.
            self.last_exitcode = 0
            return None

        self.last_exitcode = self._worker.exitcode or 0
        if self.last_exitcode != 0 and not reloading:
            logger.error("[Supervisor] Worker exited with code %s", self.last_exitcode)
            return None

        return next_scenario["path"] if reloading else None
