# Scenario format

A scenario is a YAML file in `configs/scenarios/`. Paths inside it are relative
to the project root.

Validate before running:

```bash
simctl validate configs/scenarios/my_scenario.yml
```

## Where assets live

```
assets/
  robots/manito/       manito.urdf and its meshes/
  props/               tables, ground planes and their textures
```

Asset filenames are lowercase `snake_case`, English, no spaces, lowercase
extensions. Directories say what a thing is (`robots/`, `props/`, `meshes/`);
filenames say which thing. A mesh and its texture share a stem, so
`grid_plane_1m.obj` is textured by `grid_plane_1m.png`.

The `name:` you give an entity is separate from its filename — it is what
appears in the interface, so write it for the student (`"Cubo Verde"`,
`"Mesa Tablero"`).

A robot's URDF refers to its own meshes with `package://meshes/link_1.stl`,
which resolves relative to the folder the URDF sits in. Keep a robot's meshes
beside it and the path stays that short.

## Sections

### `viewer`

Where the native Genesis window points when opened with `simctl viewer`.

```yaml
viewer:
  camera_pos: [1.5, 1.5, 1.5]
  camera_lookat: [0.0, 0.0, 0.40]
```

> `show_viewer` used to live here. It is ignored now — whether a window opens is
> decided by the command you run.

### `environment`

```yaml
environment:
  plane: true                  # add a ground plane
  gravity: [0.0, 0.0, -9.81]
```

### `robots`

Controllable arms. **Exactly one must set `is_main: true`.**

```yaml
robots:
  - name: "Manito"                          # shown in the interface
    urdf_path: "assets/robots/manito/manito.urdf"
    position: [0.0, 0.0, 0.7]
    euler: [0.0, 0.0, 0.0]                  # degrees, optional
    fixed: true
    is_main: true
    is_prop: false                          # true hides it from the robot list
```

### `props`

Static scenery — tables, fixtures, walls. Always fixed, and excluded from
telemetry since they never move.

```yaml
props:
  - name: "Mesa Tablero"
    urdf_path: "assets/props/table_top.urdf"
    position: [0.0, 0.0, -0.315]
    euler: [0.0, 0.0, 90.0]
    surface: "smooth"
    color: [0.5, 0.5, 0.5]
```

### `objects`

Things the arm manipulates. `type` is `box`, `cylinder` or `mesh`.

```yaml
objects:
  - type: "box"
    name: "Cubo Verde"
    size: [0.04, 0.04, 0.04]
    pos: [0.0, 0.20, 0.75]
    surface: "rough"
    color: [0.1, 0.8, 0.3]

  - type: "cylinder"
    name: "Cilindro"
    radius: 0.02
    height: 0.08
    pos: [0.1, 0.1, 0.75]
    color: [0.9, 0.5, 0.1]

  - type: "mesh"
    name: "Plano Cartesiano"
    file: "assets/props/grid_plane_1m.obj"
    scale: 1.0
    pos: [0.0, 0.0, 0.701]
    euler: [0.0, 0.0, 0.0]
    fixed: true
    convexify: false            # keep the true shape instead of a convex hull
    surface: "smooth"
    texture: "assets/props/grid_plane_1m.png"
```

### `stream_camera`

The camera the web interface watches.

```yaml
stream_camera:
  pos: [1.0, 1.0, 1.5]
  lookat: [0.0, 0.0, 0.40]
  fov: 40
  res: [640, 480]
```

### `objectives`

Shown in the mission banner. Evaluation is the student's own judgement.

```yaml
objectives:
  - id: "levantar_cubo"
    description: "Recoge el cubo verde y levántalo."
```

### `custom_blocks`

Optional extra Blockly blocks offered for this scenario.

## Materials

`surface` accepts `smooth`, `metal` or `rough` (the default). Give a `color` as
`[r, g, b]` in 0–1, or a `texture` path — a texture takes precedence over a
colour.

## What validation checks

- the file parses as YAML and is a mapping
- at least one robot, exactly one flagged `is_main`
- every robot and prop has a `urdf_path`
- every object has a known `type`, and meshes have a `file`
- **every referenced file exists** — URDFs, meshes and textures
