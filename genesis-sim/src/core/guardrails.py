"""Per-run limits that stop a runaway program.

A student program is a loop the simulator has no control over, so the worker
counts what it executes and how long it has been going, and aborts a run that
exceeds either. The reason is published so the UI can say *why* it stopped.
"""

import logging
import time

logger = logging.getLogger(__name__)

IDLE = "idle"
RUNNING = "running"
STOPPED = "stopped"
FAILED = "failed"


class RunGuardrails:
    """Tracks one run and decides whether the next command may execute."""

    def __init__(self, max_steps: int, max_runtime_sec: float):
        self.max_steps = max_steps
        self.max_runtime_sec = max_runtime_sec
        self.steps_executed = 0
        self.run_start_time = 0.0
        self.status = IDLE
        self.reason = None

    def allow_step(self) -> bool:
        """Claim one execution slot, starting the run clock on the first call.

        Returns False when a limit is hit, in which case the caller must drop
        whatever is queued; `status` and `reason` then describe the abort.

        An aborted run stays aborted: further calls keep returning False until
        `begin_run` clears it. Without that, the step after a failure would
        start a fresh run and wipe the reason before anyone had polled it.
        """
        if self.status in (FAILED, STOPPED):
            return False

        now = time.time()
        if self.steps_executed == 0:
            self.run_start_time = now
            self.status = RUNNING
            self.reason = None

        if self.steps_executed >= self.max_steps:
            self._fail("max_steps_reached", f"limit of {self.max_steps} steps exceeded")
            return False

        if now - self.run_start_time > self.max_runtime_sec:
            self._fail(
                "max_runtime_reached", f"time limit of {self.max_runtime_sec}s exceeded"
            )
            return False

        self.steps_executed += 1
        return True

    def finish_run(self) -> None:
        """Mark a run that drained its queue on its own as finished."""
        if self.steps_executed > 0 and self.status == RUNNING:
            self.status = IDLE
            self.reason = None
        self.steps_executed = 0

    def stop(self, reason: str = "user_stopped") -> None:
        """Abort the run at the user's request."""
        self.steps_executed = 0
        self.status = STOPPED
        self.reason = reason

    def begin_run(self) -> None:
        """Clear an abort so a newly submitted program can run.

        Called when a command arrives after a stop or a guardrail failure: the
        user has moved on, and the previous run's reason no longer applies.
        """
        if self.status in (FAILED, STOPPED):
            self.reset()

    def reset(self) -> None:
        """Clear all run state, as when the scene itself is reset."""
        self.steps_executed = 0
        self.status = IDLE
        self.reason = None

    def _fail(self, reason: str, message: str) -> None:
        self.steps_executed = 0
        self.status = FAILED
        self.reason = reason
        logger.warning("[Guardrail] Aborting: %s.", message)

    @property
    def lifecycle(self) -> dict:
        return {"status": self.status, "reason": self.reason}
