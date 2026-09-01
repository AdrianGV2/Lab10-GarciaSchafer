"""Turning a parsed scenario into a Genesis scene.

Parsing and validation live in `src.core.scenario`, which imports no Genesis;
this module takes the result and registers entities with the physics engine.
It only ever runs inside the simulation worker process.
"""

import logging
from typing import Any, Dict, Set, Tuple

import genesis as gs

from src.core.scenario import ScenarioConfig

logger = logging.getLogger(__name__)


def initialize_genesis(backend: str = "auto") -> str:
    """Start the Genesis engine on the requested backend.

    "auto" tries the GPU and falls back to CPU if it cannot be initialised.
    That fallback only covers initialisation: on a machine whose GPU is short
    on memory, the allocation can still fail later while the scene is built, so
    "cpu" is there to take the GPU out of the picture entirely.

    Returns the backend actually initialised.
    """
    choice = (backend or "auto").lower()

    if choice == "cpu":
        gs.init(backend=gs.cpu, logging_level="warning")
        logger.info("Genesis initialized with CPU backend (forced)")
        return "cpu"

    if choice == "gpu":
        gs.init(backend=gs.gpu, logging_level="warning")
        logger.info("Genesis initialized with GPU backend (forced)")
        return "gpu"

    try:
        gs.init(backend=gs.gpu, logging_level="warning")
        logger.info("Genesis initialized with GPU backend")
        return "gpu"
    except Exception as error:
        logger.warning("GPU initialization failed: %s. Falling back to CPU.", error)
        gs.init(backend=gs.cpu, logging_level="warning")
        logger.info("Genesis initialized with CPU backend")
        return "cpu"


def _build_surface(entry: dict):
    """Build a gs.surfaces.* from an entry's 'surface', 'texture' and 'color'.

    Returns None when the entry specifies no material at all.
    """
    surf_type = str(entry.get("surface", "")).lower()
    texture_path = entry.get("texture")
    color = tuple(entry.get("color", [1.0, 1.0, 1.0]))

    if not surf_type and not texture_path:
        return None

    surf_kwargs = {}
    if texture_path:
        surf_kwargs["diffuse_texture"] = gs.textures.ImageTexture(
            image_path=texture_path, encoding="srgb"
        )
    else:
        surf_kwargs["color"] = color

    if surf_type == "smooth":
        return gs.surfaces.Smooth(**surf_kwargs)
    if surf_type == "metal":
        return gs.surfaces.Metal(**surf_kwargs)
    return gs.surfaces.Rough(**surf_kwargs)


def _add_urdf(scene, entry: dict, fixed_default: bool):
    surface = _build_surface(entry)
    add_kwargs = {"surface": surface} if surface is not None else {}
    return scene.add_entity(
        gs.morphs.URDF(
            file=entry.get("urdf_path"),
            pos=entry.get("position", (0, 0, 0)),
            euler=entry.get("euler", (0, 0, 0)),
            fixed=entry.get("fixed", fixed_default),
        ),
        **add_kwargs,
    )


def _add_object(scene, entry: dict):
    surface = _build_surface(entry)
    if surface is None:
        surface = gs.surfaces.Rough(color=tuple(entry.get("color", [0.5, 0.5, 0.5])))

    obj_type = str(entry.get("type", "")).lower()
    if obj_type == "cylinder":
        return scene.add_entity(
            gs.morphs.Cylinder(
                radius=entry.get("radius", 0.1),
                height=entry.get("height", 0.1),
                pos=tuple(entry.get("pos", (0, 0, 0))),
            ),
            surface=surface,
        )
    if obj_type == "box":
        return scene.add_entity(
            gs.morphs.Box(
                size=tuple(entry.get("size", (0.1, 0.1, 0.1))),
                pos=tuple(entry.get("pos", (0, 0, 0))),
            ),
            surface=surface,
        )
    if obj_type == "mesh":
        return scene.add_entity(
            gs.morphs.Mesh(
                file=entry.get("file"),
                scale=entry.get("scale", 1.0),
                pos=tuple(entry.get("pos", (0, 0, 0))),
                euler=tuple(entry.get("euler", (0, 0, 0))),
                fixed=entry.get("fixed", True),
                convexify=entry.get("convexify", True),
            ),
            surface=surface,
        )
    return None


def build_scene(
    config: ScenarioConfig, show_viewer: bool = False
) -> Tuple[Any, Any, Any, Dict[str, Any], Set[str]]:
    """Build a Genesis scene from a validated scenario.

    Args:
        config: A ScenarioConfig from `scenario.load_scenario`.
        show_viewer: Open the native Genesis window. Chosen by the launch mode,
            never by the scenario file.

    Returns:
        The scene, the main robot entity, the streaming camera, every named
        entity, and the names that are static scenery.
    """
    scene = gs.Scene(
        viewer_options=gs.options.ViewerOptions(
            camera_pos=config.camera_pos,
            camera_lookat=config.camera_lookat,
            res=(1280, 960),
        ),
        sim_options=gs.options.SimOptions(
            dt=1 / 60.0,
            substeps=5,
            gravity=config.gravity,
        ),
        show_viewer=show_viewer,
    )

    if config.plane:
        scene.add_entity(gs.morphs.Plane())

    main_robot = None
    entity_dict: Dict[str, Any] = {}

    for index, robot in enumerate(config.robots):
        name = robot.get("name", f"robot_{index}")
        entity_dict[name] = _add_urdf(scene, robot, fixed_default=True)
        if robot.get("is_main", False):
            main_robot = entity_dict[name]

    prop_names: Set[str] = set()
    for index, prop in enumerate(config.props):
        name = prop.get("name", f"prop_{index}")
        entity_dict[name] = _add_urdf(scene, prop, fixed_default=True)
        prop_names.add(name)

    for index, obj in enumerate(config.objects):
        entity = _add_object(scene, obj)
        if entity is not None:
            entity_dict[obj.get("name", f"object_{index}")] = entity

    cam = scene.add_camera(
        pos=config.stream_camera.get("pos", (1.0, 1.0, 0.8)),
        lookat=config.stream_camera.get("lookat", (0.0, 0.0, 0.2)),
        fov=config.stream_camera.get("fov", 40),
        res=config.stream_camera.get("res", [640, 480]),
    )

    # `load_scenario` already rejects a scenario without a main robot; this
    # guards the path where a caller builds a ScenarioConfig by hand.
    if main_robot is None:
        raise RuntimeError(f"{config.name} defines no robot with 'is_main: true'")

    return scene, main_robot, cam, entity_dict, prop_names
