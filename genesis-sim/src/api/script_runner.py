"""Running the Python a user typed in the editor.

The script runs in its own process and drives the arm over HTTP with the same
`manito_api.ManitoArm` used against the real robot, so what works here works on
the hardware. Its output is buffered and the front end polls it by index.
"""

import importlib.util
import logging
import os
import subprocess
import sys
import threading

logger = logging.getLogger(__name__)

SCRIPT_NAME = "user_script.py"

CLIENT_MISSING = (
    "The 'manito-api' package is not installed, so user scripts cannot run. "
    "Install it with: uv sync --extra scripts"
)


def client_available() -> bool:
    """Whether `manito_api` can be imported by the interpreter we would spawn."""
    return importlib.util.find_spec("manito_api") is not None


class ScriptRunner:
    """Owns at most one running user script."""

    def __init__(self, script_dir, api_url: str):
        self.script_dir = script_dir
        self.api_url = api_url
        self._process = None
        self._output = []
        self._status = "idle"
        self._lock = threading.Lock()

    def run(self, source: str) -> None:
        if not client_available():
            raise RuntimeError(CLIENT_MISSING)

        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise RuntimeError("A script is already running.")
            self._output = []
            self._status = "running"

        self.script_dir.mkdir(parents=True, exist_ok=True)
        script_path = self.script_dir / SCRIPT_NAME
        script_path.write_text(source, encoding="utf-8")

        env = dict(os.environ)
        env["MANITO_URL"] = self.api_url
        env["PYTHONUNBUFFERED"] = "1"

        self._process = subprocess.Popen(
            [sys.executable, SCRIPT_NAME],
            cwd=str(self.script_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        threading.Thread(target=self._drain, args=(self._process,), daemon=True).start()

    def _drain(self, process) -> None:
        for line in process.stdout:
            with self._lock:
                self._output.append(line.rstrip("\n"))
        code = process.wait()

        with self._lock:
            if self._status == "stopped":
                return
            self._status = "finished" if code == 0 else "failed"
            if code != 0:
                self._output.append(f"[process exited with code {code}]")

    def stop(self) -> None:
        with self._lock:
            process = self._process
            if process is None or process.poll() is not None:
                return
            self._status = "stopped"

        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()

        with self._lock:
            self._output.append("[stopped by the user]")

    def poll(self, since: int = 0) -> dict:
        with self._lock:
            return {
                "status": self._status,
                "lines": self._output[since:],
                "next_index": len(self._output),
            }
