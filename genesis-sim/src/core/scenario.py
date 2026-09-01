"""Parsing and validation of scenario YAML files.

Deliberately free of any Genesis import: this module is what `simctl validate`
runs, so checking a scenario stays fast and works on a machine with no GPU.
`urdf_loader` turns the result of parsing into an actual Genesis scene.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml

from src.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

MESH_TYPES = ("mesh", "box", "cylinder")


class ScenarioError(Exception):
    """A scenario file is missing, unreadable or structurally invalid."""


@dataclass
class ScenarioConfig:
    """A parsed scenario file.

    Sections stay as plain dictionaries -- the YAML keys are the contract with
    whoever writes scenarios, and mirroring them into typed fields would mean
    editing this module every time a Genesis morph option is exposed.
    """

    path: Path
    camera_pos: List[float] = field(default_factory=lambda: [1.5, 1.5, 1.5])
    camera_lookat: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    gravity: List[float] = field(default_factory=lambda: [0.0, 0.0, -9.81])
    plane: bool = True
    robots: List[Dict[str, Any]] = field(default_factory=list)
    props: List[Dict[str, Any]] = field(default_factory=list)
    objects: List[Dict[str, Any]] = field(default_factory=list)
    stream_camera: Dict[str, Any] = field(default_factory=dict)
    objectives: List[Dict[str, Any]] = field(default_factory=list)
    custom_blocks: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def controllable_robots(self) -> List[Dict[str, Any]]:
        """Robots a user can drive, excluding scenery flagged with `is_prop`."""
        return [r for r in self.robots if not r.get("is_prop", False)]

    def asset_paths(self) -> List[str]:
        """Every file this scenario refers to, as written in the YAML."""
        paths = []
        for entry in list(self.robots) + list(self.props):
            if entry.get("urdf_path"):
                paths.append(entry["urdf_path"])
        for entry in self.objects:
            for key in ("file", "texture"):
                if entry.get(key):
                    paths.append(entry[key])
        return paths


def load_scenario(path) -> ScenarioConfig:
    """Read a scenario YAML file into a ScenarioConfig.

    Raises:
        ScenarioError: If the file is missing, is not valid YAML, or does not
            describe a scene the loader could build.
    """
    scenario_path = Path(path)
    if not scenario_path.is_absolute():
        scenario_path = PROJECT_ROOT / scenario_path

    if not scenario_path.exists():
        raise ScenarioError(f"Scenario file not found: {scenario_path}")

    try:
        with open(scenario_path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except yaml.YAMLError as error:
        raise ScenarioError(f"{scenario_path}: invalid YAML: {error}") from error

    if not isinstance(raw, dict):
        raise ScenarioError(f"{scenario_path}: expected a mapping at the top level")

    viewer = raw.get("viewer") or {}
    environment = raw.get("environment") or {}

    # `show_viewer` used to live here, which put a launch-mode decision inside
    # scene data. It is now chosen by the command (`simctl viewer` vs `serve`).
    if "show_viewer" in viewer:
        logger.warning(
            "%s: 'viewer.show_viewer' is ignored -- use `simctl viewer` to open "
            "the Genesis window.",
            scenario_path.name,
        )

    config = ScenarioConfig(
        path=scenario_path,
        camera_pos=viewer.get("camera_pos", [1.5, 1.5, 1.5]),
        camera_lookat=viewer.get("camera_lookat", [0.0, 0.0, 0.0]),
        gravity=environment.get("gravity", [0.0, 0.0, -9.81]),
        plane=environment.get("plane", True),
        robots=raw.get("robots") or [],
        props=raw.get("props") or [],
        objects=raw.get("objects") or [],
        stream_camera=raw.get("stream_camera") or {},
        objectives=raw.get("objectives") or [],
        custom_blocks=raw.get("custom_blocks") or [],
    )

    problems = validate(config)
    if problems:
        raise ScenarioError(
            f"{scenario_path.name} is not loadable:\n  - " + "\n  - ".join(problems)
        )
    return config


def validate(config: ScenarioConfig) -> List[str]:
    """Return every reason this scenario would fail to build, as plain messages.

    Returns an empty list when the scenario is sound.
    """
    problems: List[str] = []

    if not config.robots:
        problems.append("no robots defined")
    elif not any(r.get("is_main", False) for r in config.robots):
        problems.append("no robot is marked 'is_main: true'")

    for index, robot in enumerate(config.robots):
        if not robot.get("urdf_path"):
            problems.append(f"robots[{index}] has no 'urdf_path'")

    for index, prop in enumerate(config.props):
        if not prop.get("urdf_path"):
            problems.append(f"props[{index}] has no 'urdf_path'")

    for index, obj in enumerate(config.objects):
        obj_type = str(obj.get("type", "")).lower()
        if obj_type not in MESH_TYPES:
            problems.append(
                f"objects[{index}] has type {obj.get('type')!r}; "
                f"expected one of {', '.join(MESH_TYPES)}"
            )
        elif obj_type == "mesh" and not obj.get("file"):
            problems.append(f"objects[{index}] is a mesh but has no 'file'")

    for asset in config.asset_paths():
        if not (PROJECT_ROOT / asset).exists():
            problems.append(f"missing asset: {asset}")

    return problems


def discover_scenarios(scenarios_dir) -> List[Path]:
    """Every scenario file in a directory, sorted by name."""
    directory = Path(scenarios_dir)
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.yml"))
