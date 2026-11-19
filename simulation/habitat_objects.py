"""Stage 4: Versioned habitat object definitions and MuJoCo MjSpec scene builder.

Attaches enclosure walls and interactive habitat props directly onto the authoritative
`simulation/models/hamster/hamster.xml` (`hamster_mjcf_v1.0.0`) via `mujoco.MjSpec`
so there is a single source of truth for hamster morphology.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import mujoco

HAMSTER_XML = Path("simulation/models/hamster/hamster.xml")
HABITAT_VERSION = "habitat_mujoco_v1.0.0"

# Enclosure interior bounds (meters): 1.0 m x 0.6 m
ENCLOSURE_HALF_X = 0.50
ENCLOSURE_HALF_Y = 0.30
WALL_HEIGHT = 0.14


@dataclass
class HabitatObject:
    object_id: str
    kind: str
    pos: tuple[float, float, float]
    approach_radius_m: float
    affordances: tuple[str, ...]
    resource_level: float = 1.0
    rgba: tuple[float, float, float, float] = (0.6, 0.5, 0.4, 1.0)
    size: tuple[float, float, float] = (0.04, 0.04, 0.02)
    extra: dict = field(default_factory=dict)


def default_habitat_objects() -> dict[str, HabitatObject]:
    """Canonical habitat layout with clear navigation corridors around origin (0, 0)."""
    return {
        "prop_bowl_main": HabitatObject(
            object_id="prop_bowl_main",
            kind="food_bowl",
            pos=(0.28, -0.14, 0.015),
            approach_radius_m=0.11,
            affordances=("forage", "eat", "sniff"),
            resource_level=1.0,
            rgba=(0.82, 0.46, 0.32, 1.0),
            size=(0.042, 0.042, 0.015),
        ),
        "prop_bottle_main": HabitatObject(
            object_id="prop_bottle_main",
            kind="water_bottle",
            pos=(0.30, 0.16, 0.055),
            approach_radius_m=0.11,
            affordances=("drink", "sniff"),
            resource_level=1.0,
            rgba=(0.35, 0.68, 0.88, 0.85),
            size=(0.025, 0.025, 0.055),
        ),
        "prop_hideout_main": HabitatObject(
            object_id="prop_hideout_main",
            kind="hideout",
            pos=(-0.30, 0.14, 0.045),
            approach_radius_m=0.13,
            affordances=("hide", "rest", "sleep"),
            resource_level=1.0,
            rgba=(0.56, 0.39, 0.24, 1.0),
            size=(0.085, 0.075, 0.045),
        ),
        "prop_tunnel_main": HabitatObject(
            object_id="prop_tunnel_main",
            kind="tunnel",
            pos=(0.02, 0.16, 0.032),
            approach_radius_m=0.11,
            affordances=("enter_tunnel", "explore"),
            resource_level=1.0,
            rgba=(0.45, 0.36, 0.28, 0.9),
            size=(0.075, 0.038, 0.032),
        ),
        "prop_wheel_main": HabitatObject(
            object_id="prop_wheel_main",
            kind="wheel",
            pos=(-0.28, -0.17, 0.085),
            approach_radius_m=0.13,
            affordances=("exercise", "sniff"),
            resource_level=1.0,
            rgba=(0.74, 0.58, 0.38, 1.0),
            size=(0.020, 0.085, 0.085),
        ),
        "prop_treat_zone": HabitatObject(
            object_id="prop_treat_zone",
            kind="interaction_zone",
            pos=(0.24, 0.0, 0.008),
            approach_radius_m=0.10,
            affordances=("petting", "treat", "sniff"),
            resource_level=1.0,
            rgba=(0.30, 0.80, 0.55, 0.65),
            size=(0.035, 0.035, 0.006),
        ),
    }


def build_habitat_model(
    hamster_xml: str | Path = HAMSTER_XML,
    objects: dict[str, HabitatObject] | None = None,
) -> mujoco.MjModel:
    """Attach enclosure walls, overview camera, and habitat props onto hamster.xml via MjSpec."""
    objs = objects or default_habitat_objects()
    spec = mujoco.MjSpec.from_file(str(hamster_xml))

    wb = spec.worldbody

    # Fixed overhead/3-4 habitat overview camera for Stage 4 videos
    cam = wb.add_camera()
    cam.name = "habitat_overview"
    cam.pos = [0.02, -0.78, 0.56]
    cam.quat = [0.891, 0.454, 0.0, 0.0]

    # Enclosure walls (transparent acrylic-style visual + solid collision)
    wall_defs = [
        ("wall_north", [0.0, ENCLOSURE_HALF_Y + 0.01, WALL_HEIGHT / 2], [ENCLOSURE_HALF_X + 0.02, 0.01, WALL_HEIGHT / 2]),
        ("wall_south", [0.0, -ENCLOSURE_HALF_Y - 0.01, WALL_HEIGHT / 2], [ENCLOSURE_HALF_X + 0.02, 0.01, WALL_HEIGHT / 2]),
        ("wall_east", [ENCLOSURE_HALF_X + 0.01, 0.0, WALL_HEIGHT / 2], [0.01, ENCLOSURE_HALF_Y, WALL_HEIGHT / 2]),
        ("wall_west", [-ENCLOSURE_HALF_X - 0.01, 0.0, WALL_HEIGHT / 2], [0.01, ENCLOSURE_HALF_Y, WALL_HEIGHT / 2]),
    ]
    for wname, wpos, wsize in wall_defs:
        g = wb.add_geom()
        g.name = wname
        g.type = mujoco.mjtGeom.mjGEOM_BOX
        g.pos = wpos
        g.size = wsize
        g.rgba = [0.75, 0.82, 0.88, 0.22]
        g.group = 2
        g.contype = 1
        g.conaffinity = 1

    # Add habitat props (visual markers in group=2; non-blocking zones for smooth approach)
    for oid, obj in objs.items():
        g = wb.add_geom()
        g.name = f"geom_{oid}"
        g.pos = list(obj.pos)
        g.rgba = list(obj.rgba)
        g.group = 2
        if obj.kind == "food_bowl":
            g.type = mujoco.mjtGeom.mjGEOM_CYLINDER
            g.size = [obj.size[0], obj.size[2], 0.0]
            g.contype = 0
            g.conaffinity = 0
            # Inner seed fill visual
            seeds = wb.add_geom()
            seeds.name = f"geom_{oid}_seeds"
            seeds.type = mujoco.mjtGeom.mjGEOM_CYLINDER
            seeds.pos = [obj.pos[0], obj.pos[1], obj.pos[2] + 0.008]
            seeds.size = [obj.size[0] * 0.78, 0.004, 0.0]
            seeds.rgba = [0.42, 0.30, 0.16, 1.0]
            seeds.group = 2
            seeds.contype = 0
            seeds.conaffinity = 0
        elif obj.kind == "water_bottle":
            g.type = mujoco.mjtGeom.mjGEOM_CYLINDER
            g.size = [obj.size[0], obj.size[2], 0.0]
            g.contype = 0
            g.conaffinity = 0
        elif obj.kind == "tunnel":
            # Open-ended arch visual (non-colliding so hamster can walk right through)
            g.type = mujoco.mjtGeom.mjGEOM_BOX
            g.size = [obj.size[0], obj.size[1], 0.006]
            g.pos = [obj.pos[0], obj.pos[1], 0.068]
            g.contype = 0
            g.conaffinity = 0
            for side, dy in (("l", obj.size[1]), ("r", -obj.size[1])):
                pillar = wb.add_geom()
                pillar.name = f"geom_{oid}_{side}"
                pillar.type = mujoco.mjtGeom.mjGEOM_BOX
                pillar.pos = [obj.pos[0], obj.pos[1] + dy, 0.034]
                pillar.size = [obj.size[0], 0.006, 0.034]
                pillar.rgba = list(obj.rgba)
                pillar.group = 2
                pillar.contype = 0
                pillar.conaffinity = 0
        elif obj.kind == "hideout":
            g.type = mujoco.mjtGeom.mjGEOM_BOX
            g.size = [obj.size[0], obj.size[1], 0.006]
            g.pos = [obj.pos[0], obj.pos[1], 0.088]
            g.contype = 0
            g.conaffinity = 0
            for sname, dpos, dsz in (
                ("back", [-obj.size[0], 0.0, 0.044], [0.006, obj.size[1], 0.044]),
                ("left", [0.0, obj.size[1], 0.044], [obj.size[0], 0.006, 0.044]),
                ("right", [0.0, -obj.size[1], 0.044], [obj.size[0], 0.006, 0.044]),
            ):
                p = wb.add_geom()
                p.name = f"geom_{oid}_{sname}"
                p.type = mujoco.mjtGeom.mjGEOM_BOX
                p.pos = [obj.pos[0] + dpos[0], obj.pos[1] + dpos[1], dpos[2]]
                p.size = dsz
                p.rgba = list(obj.rgba)
                p.group = 2
                p.contype = 0
                p.conaffinity = 0
        elif obj.kind == "wheel":
            g.type = mujoco.mjtGeom.mjGEOM_CYLINDER
            g.size = [obj.size[1], obj.size[0], 0.0]
            g.quat = [0.7071, 0.7071, 0.0, 0.0]
            g.contype = 0
            g.conaffinity = 0
        else:  # interaction_zone
            g.type = mujoco.mjtGeom.mjGEOM_CYLINDER
            g.size = [obj.size[0], obj.size[2], 0.0]
            g.contype = 0
            g.conaffinity = 0

    return spec.compile()
