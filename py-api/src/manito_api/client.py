"""HTTP client for the Manito SCARA arm.

The same class drives two backends that speak the same REST contract:

* ``manito-driver`` -- the Rust driver that talks to the Arduino over serial,
  listening on port 8080 by default.
* the Genesis simulator, which implements the same routes so a program written
  for one runs unchanged on the other.

Pick the backend with the ``url`` argument or the ``MANITO_URL`` environment
variable; nothing else in a user program changes.
"""

import os
import time

import requests

DEFAULT_URL = "http://localhost:8080"

# Status values reported by the driver (manito_protocol::StatusCode).
STATUS_READY = "Ready"


class ManitoError(RuntimeError):
    """The robot reported an error while executing a command."""


class ManitoArm:
    """Blocking client for the Manito arm.

    Args:
        url: Base URL of the driver or simulator. Falls back to ``MANITO_URL``,
            then to ``http://localhost:8080``.
        wait: When true (the default) every motion call returns only once the
            arm reports itself idle again, so a script reads top to bottom.
        timeout: Seconds to wait for a single motion before giving up.
        poll_interval: Seconds between status polls while waiting.
        settle_timeout: How long to keep waiting for the arm to *start* moving
            before concluding the move was instantaneous. See `_wait_until_idle`.
    """

    def __init__(
        self,
        url=None,
        wait=True,
        timeout=120.0,
        poll_interval=0.25,
        settle_timeout=1.5,
    ):
        self.url = (url or os.environ.get("MANITO_URL", DEFAULT_URL)).rstrip("/")
        self.wait = wait
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.settle_timeout = settle_timeout
        # One reused connection: polling the status must not open a socket per
        # attempt nor flood the server with fresh handshakes.
        self._session = requests.Session()

    # -- state ------------------------------------------------------------

    def status(self):
        """Return the arm state as reported by ``GET /api/status``.

        Keys: ``theta1``, ``theta2``, ``phi``, ``z``, ``gripper``, ``status``,
        ``is_connected``, ``is_homed``, ``last_error``, ``homing_progress``.
        The simulator adds ``executed_total``.
        """
        response = self._session.get(f"{self.url}/api/status", timeout=10)
        response.raise_for_status()
        return response.json()

    # -- motion -----------------------------------------------------------

    def move_joints(self, j1, j3, j4, z, gripper=None):
        """Move every joint to an absolute pose.

        Args:
            j1: Shoulder angle, degrees.
            j3: Elbow angle, degrees.
            j4: Wrist angle, degrees.
            z: Height of the vertical axis, centimetres.
            gripper: Closed state. When omitted the current state is kept.

        The names j1/j3/j4 match the J1/J3/J4 labels on the Blockly blocks; j2
        is the vertical axis and is given as ``z``. On the wire they map to the
        firmware's theta1/theta2/phi.
        """
        before = self.status()
        if gripper is None:
            gripper = before.get("gripper", False)

        self._post(
            "/api/move_joints",
            {"theta1": j1, "theta2": j3, "phi": j4, "z": z, "gripper": gripper},
            before,
        )

    def gripper(self, close):
        """Close (``True``) or open (``False``) the gripper."""
        self._post("/api/gripper", {"close": bool(close)})

    def home(self):
        """Run the homing sequence and return the arm to its start pose."""
        self._post("/api/homing", None)

    def jog(self, joint_id, speed):
        """Drive a single joint continuously at ``speed``; 0 stops it."""
        self._post("/api/jog", {"joint_id": int(joint_id), "speed": float(speed)})

    def set_speed_accel(self, speed, accel):
        """Set one speed and acceleration for every joint."""
        self._post(
            "/api/set_speed_accel", {"speed": float(speed), "accel": float(accel)}
        )

    def set_joint_config(self, speeds, accels):
        """Set per-joint speeds and accelerations, four of each."""
        if len(speeds) != 4 or len(accels) != 4:
            raise ValueError("set_joint_config expects exactly 4 speeds and 4 accels")
        self._post(
            "/api/set_joint_config",
            {"speeds": [float(s) for s in speeds], "accels": [float(a) for a in accels]},
        )

    def estop(self):
        """Emergency stop: halt every joint immediately."""
        self._post("/api/estop", None, wait=False)

    # -- internals --------------------------------------------------------

    def _post(self, path, payload, before=None, wait=None):
        should_wait = self.wait if wait is None else wait
        if should_wait and before is None:
            before = self.status()

        response = self._session.post(f"{self.url}{path}", json=payload, timeout=10)
        response.raise_for_status()

        if should_wait:
            self._wait_until_idle(before)

    def _wait_until_idle(self, before):
        """Block until the arm finishes the command that was just issued.

        Two backends, two ways of telling that a command is done:

        * The simulator consumes commands one physics burst at a time and
          publishes ``executed_total``, so a move is complete once that counter
          has advanced and the arm is idle again. Exact, so it is preferred.
        * The driver has no such counter. There, a move is complete once the
          status has left ``Ready`` and come back. A move too short to be
          caught by a poll would hang that rule forever, so once
          ``settle_timeout`` passes with the status never having left ``Ready``
          the move is taken to be already finished.

        Either way an error that appears during the wait aborts it. The
        driver's ``last_error`` is sticky -- it holds the previous failure until
        a new one replaces it -- so only a *change* counts as this command's
        error, never whatever was already there.
        """
        previous_error = before.get("last_error")
        executed_before = before.get("executed_total")
        use_counter = executed_before is not None

        deadline = time.time() + self.timeout
        settle_deadline = time.time() + self.settle_timeout
        seen_busy = False

        while time.time() < deadline:
            state = self.status()

            error = state.get("last_error")
            if error and error != previous_error:
                raise ManitoError(str(error))

            is_idle = state.get("status", STATUS_READY) == STATUS_READY

            if use_counter:
                executed = state.get("executed_total", executed_before)
                if executed > executed_before and is_idle:
                    return
            elif not is_idle:
                seen_busy = True
            elif seen_busy or time.time() > settle_deadline:
                return

            time.sleep(self.poll_interval)

        raise TimeoutError(
            f"The arm did not finish the movement within {self.timeout:.0f}s."
        )
