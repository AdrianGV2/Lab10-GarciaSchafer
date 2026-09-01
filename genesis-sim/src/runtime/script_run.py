"""Batch mode: run one scenario with one user script, then exit.

Used by `simctl run`. The supervisor has to own the main thread, so the script
runs on a background thread that shuts the supervisor down when it finishes.
The script's exit code becomes the command's exit code, which is what makes
this usable for grading and regression checks.
"""

import logging
import os
import subprocess
import sys
import threading
import time

logger = logging.getLogger(__name__)


def _wait_until_loaded(tracker, timeout: float) -> bool:
    """Block until the worker reports a built scene, or the timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if tracker.poll_state().get("status") == "running":
            return True
        time.sleep(0.2)
    return False


def run_script_against(supervisor, tracker, script_path, api_url, load_timeout=180.0):
    """Run `script_path` once the scene is up. Returns its exit code."""
    result = {"code": 1}

    def worker():
        try:
            if not _wait_until_loaded(tracker, load_timeout):
                logger.error("Scene did not finish loading within %ss.", load_timeout)
                result["code"] = 1
                return

            env = dict(os.environ)
            env["MANITO_URL"] = api_url
            env["PYTHONUNBUFFERED"] = "1"

            logger.info("Running %s", script_path)
            completed = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(script_path.parent),
                env=env,
            )
            result["code"] = completed.returncode
        finally:
            supervisor.stop()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return result
