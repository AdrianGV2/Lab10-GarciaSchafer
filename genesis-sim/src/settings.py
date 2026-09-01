"""Runtime configuration for the simulator.

One place for every port, path and limit that used to be hardcoded across the
CLI, the API and the worker. Every field can be overridden by an environment
variable so Docker and CI can configure a run without editing code.
"""

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    """Everything the simulator needs to know that is not scene data."""

    # Network
    host: str = "0.0.0.0"
    port: int = 8000

    # Paths, all relative to the project root
    project_root: Path = PROJECT_ROOT
    scenarios_dir: Path = PROJECT_ROOT / "configs" / "scenarios"
    script_dir: Path = PROJECT_ROOT / "runs"

    # Physics backend: "auto" tries the GPU and falls back to CPU, "gpu" and
    # "cpu" force one. Forcing matters on a shared machine where the GPU may be
    # out of memory: the fallback cannot rescue an allocation that fails later,
    # during the scene build.
    backend: str = "auto"

    # Presentation
    show_viewer: bool = False
    jpeg_quality: int = 80

    # Run guardrails, enforced by the worker
    max_run_steps: int = 100
    max_runtime_sec: float = 300.0
    cooldown_frames: int = 30

    # Feature gates
    enable_script_api: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=_env_str("MANITO_SIM_HOST", cls.host),
            port=_env_int("MANITO_SIM_PORT", cls.port),
            scenarios_dir=Path(
                _env_str("MANITO_SIM_SCENARIOS_DIR", str(cls.scenarios_dir))
            ),
            script_dir=Path(_env_str("MANITO_SIM_SCRIPT_DIR", str(cls.script_dir))),
            backend=_env_str("MANITO_SIM_BACKEND", cls.backend),
            show_viewer=_env_bool("MANITO_SIM_SHOW_VIEWER", cls.show_viewer),
            jpeg_quality=_env_int("MANITO_SIM_JPEG_QUALITY", cls.jpeg_quality),
            max_run_steps=_env_int("MANITO_SIM_MAX_RUN_STEPS", cls.max_run_steps),
            max_runtime_sec=_env_float(
                "MANITO_SIM_MAX_RUNTIME_SEC", cls.max_runtime_sec
            ),
            cooldown_frames=_env_int(
                "MANITO_SIM_COOLDOWN_FRAMES", cls.cooldown_frames
            ),
            enable_script_api=_env_bool(
                "MANITO_SIM_ENABLE_SCRIPT_API", cls.enable_script_api
            ),
        )

    @property
    def api_url(self) -> str:
        """URL a client on this machine uses to reach the API."""
        return f"http://127.0.0.1:{self.port}"

    @property
    def binds_publicly(self) -> bool:
        return self.host not in ("127.0.0.1", "localhost", "::1")
