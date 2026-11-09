"""
HAMMY Art Pipeline — Prompt 1: Cage Geometry & Props
Builds:
  - CAGE Collection: Open-top rounded plastic base tub, clear glass/acrylic panels,
                     slotted back ventilation panel, open-center top rim frame.
  - PROPS Collection: Open-front 0.28m exercise wheel on stand, concave ceramic bowl,
                      wall-mounted water bottle with 45-deg spout & ball tip,
                      hollow wooden hideout with arched doorway, 3-part hollow tunnel.
  - CAMERAS & LIGHTS: Properly aimed cameras (Track-To / look_at) and calibrated studio lighting.

Idempotent: clears default Cube/Camera/Light and rebuilds CAGE, PROPS, LIGHTS, CAMERAS.
Outputs:
  - blender/scene.blend
  - renders/tests/01_cage_three_quarter.png
  - renders/tests/01_cage_top.png
"""

import os
import sys
import math
import bpy
import bmesh
from mathutils import Vector, Euler, Matrix

# Import pipeline common helpers
scripts_dir = os.path.dirname(os.path.abspath(__file__))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

import common


def link_to_collection(obj: bpy.types.Object, target_col: bpy.types.Collection):
    """Safely links object to target collection and unlinks from all other collections."""
    if obj.name not in target_col.objects:
        target_col.objects.link(obj)
    for col in list(obj.users_collection):
        if col != target_col:
            col.objects.unlink(obj)


def clean_startup_defaults():
    """Removes the default Blender Cube, Light, Camera, and default 'Collection'."""
    for name in ["Cube", "Light", "Camera"]:
        if name in bpy.data.objects:
            obj = bpy.data.objects[name]
            bpy.data.objects.remove(obj, do_unlink=True)
    if "Collection" in bpy.data.collections:
        col = bpy.data.collections["Collection"]
        if len(col.objects) == 0:
            bpy.data.collections.remove(col)


def assign_preview_material(obj: bpy.types.Object, name: str, base_color: tuple, roughness: float = 0.4,
                            metallic: float = 0.0, transmission: float = 0.0, alpha: float = 1.0):
    """Creates/updates a Principled BSDF material with viewport color so both Solid and Cycles views look clear."""
    mat = common.make_material(name, use_nodes=True)
    mat.diffuse_color = (base_color[0], base_color[1], base_color[2], alpha)

    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")

    bsdf.inputs["Base Color"].default_value = (base_color[0], base_color[1], base_color[2], 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = transmission
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = 1.49

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def set_smooth_By_angle(obj: bpy.types.Object):
    """Sets smooth shading on mesh faces."""
    if obj.type == 'MESH' and obj.data:
        for poly in obj.data.polygons:
            poly.use_smooth = True


def look_at(obj: bpy.types.Object, target: Vector):
    """Rotates an object (Camera or Light) so its -Z axis points directly at target, with +Y up."""
    direction = target - obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    obj.rotation_euler = rot_quat.to_euler()


def create_open_rounded_tub(name: str, width: float, depth: float, height: float,
                            corner_radius: float, wall_thickness: float,
                            collection: bpy.types.Collection) -> bpy.types.Object:
    """Creates an OPEN-TOP rounded plastic cage tub."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    steps = 10
    half_w = width / 2.0
    half_d = depth / 2.0
    r = min(corner_radius, half_w * 0.9, half_d * 0.9)

    corners = [
        (half_w - r, half_d - r, 0, math.pi / 2),
        (-half_w + r, half_d - r, math.pi / 2, math.pi),
        (-half_w + r, -half_d + r, math.pi, 3 * math.pi / 2),
        (half_w - r, -half_d + r, 3 * math.pi / 2, 2 * math.pi),
    ]

    bottom_verts = []
    for cx, cy, start_angle, end_angle in corners:
        for i in range(steps):
            theta = start_angle + (end_angle - start_angle) * (i / steps)
            x = cx + r * math.cos(theta)
            y = cy + r * math.sin(theta)
            v = bm.verts.new((x, y, 0.0))
            bottom_verts.append(v)

    bottom_face = bm.faces.new(bottom_verts)
    bm.normal_update()
    if bottom_face.normal.z < 0:
        bottom_face.normal_flip()

    # Extrude upwards
    res = bmesh.ops.extrude_face_region(bm, geom=[bottom_face])
    extruded_verts = [ele for ele in res['geom'] if isinstance(ele, bmesh.types.BMVert)]
    extruded_faces = [ele for ele in res['geom'] if isinstance(ele, bmesh.types.BMFace)]
    bmesh.ops.translate(bm, vec=Vector((0, 0, height)), verts=extruded_verts)

    # Delete the top cap face so the tub is OPEN on top!
    bmesh.ops.delete(bm, geom=extruded_faces, context='FACES')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    link_to_collection(obj, collection)

    # Solidify for wall thickness
    solid = obj.modifiers.new("Solidify", 'SOLIDIFY')
    solid.thickness = wall_thickness
    solid.offset = -1.0
    solid.use_even_offset = True

    # Bevel for realistic plastic edges
    bev = obj.modifiers.new("Bevel", 'BEVEL')
    bev.width = 0.002
    bev.segments = 3
    bev.limit_method = 'ANGLE'

    set_smooth_By_angle(obj)
    return obj


def create_open_top_rim(name: str, width: float, depth: float, rim_width: float,
                        rim_height: float, z_pos: float, corner_radius: float,
                        collection: bpy.types.Collection) -> bpy.types.Object:
    """Creates an open rectangular frame rim around the top of the cage."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    steps = 10
    half_w = width / 2.0
    half_d = depth / 2.0
    r_out = min(corner_radius, half_w * 0.9, half_d * 0.9)
    r_in = max(0.005, r_out - rim_width)

    corners_out = [
        (half_w - r_out, half_d - r_out, 0, math.pi / 2),
        (-half_w + r_out, half_d - r_out, math.pi / 2, math.pi),
        (-half_w + r_out, -half_d + r_out, math.pi, 3 * math.pi / 2),
        (half_w - r_out, -half_d + r_out, 3 * math.pi / 2, 2 * math.pi),
    ]
    ihw = half_w - rim_width
    ihd = half_d - rim_width
    corners_in = [
        (ihw - r_in, ihd - r_in, 0, math.pi / 2),
        (-ihw + r_in, ihd - r_in, math.pi / 2, math.pi),
        (-ihw + r_in, -ihd + r_in, math.pi, 3 * math.pi / 2),
        (ihw - r_in, -ihd + r_in, 3 * math.pi / 2, 2 * math.pi),
    ]

    outer_ring = []
    inner_ring = []
    for (cx_o, cy_o, sa, ea), (cx_i, cy_i, _, _) in zip(corners_out, corners_in):
        for i in range(steps):
            theta = sa + (ea - sa) * (i / steps)
            vo = bm.verts.new((cx_o + r_out * math.cos(theta), cy_o + r_out * math.sin(theta), z_pos))
            vi = bm.verts.new((cx_i + r_in * math.cos(theta), cy_i + r_in * math.sin(theta), z_pos))
            outer_ring.append(vo)
            inner_ring.append(vi)

    n = len(outer_ring)
    bottom_faces = []
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new([outer_ring[i], outer_ring[j], inner_ring[j], inner_ring[i]])
        bottom_faces.append(f)

    res = bmesh.ops.extrude_face_region(bm, geom=bottom_faces)
    ext_verts = [e for e in res['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=Vector((0, 0, rim_height)), verts=ext_verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    link_to_collection(obj, collection)

    bev = obj.modifiers.new("Bevel", 'BEVEL')
    bev.width = 0.0015
    bev.segments = 2
    bev.limit_method = 'ANGLE'
    set_smooth_By_angle(obj)
    return obj


def build_cage(cage_col: bpy.types.Collection):
    """
    Builds the cage tub, clear acrylic panels, slotted back wall, and open top frame.
    Floor: 1.00m x 0.50m, total wall height 0.40m, tub height 0.18m.
    """
    width, depth = 1.00, 0.50
    tub_height = 0.18
    total_height = 0.40
    wall_thickness = 0.005
    corner_r = 0.04

    # 1. Open-Top Plastic Tub Base
    tub = create_open_rounded_tub("cage_tub", width, depth, tub_height, corner_r, wall_thickness, cage_col)
    assign_preview_material(tub, "mat_cage_tub", (0.14, 0.16, 0.18), roughness=0.35)

    # 2. Clear Acrylic Panels (Front, Left, Right) + Back Slotted Panel
    panel_h = total_height - tub_height + 0.005
    panel_z = tub_height + panel_h / 2.0 - 0.002
    glass_thick = 0.004

    # Front clear panel
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, -depth / 2.0 + wall_thickness / 2.0, panel_z))
    p_front = bpy.context.active_object
    p_front.name = "cage_panel_front"
    p_front.scale = (width - corner_r * 1.4, glass_thick, panel_h)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_to_collection(p_front, cage_col)
    assign_preview_material(p_front, "mat_cage_glass", (0.88, 0.95, 0.98), roughness=0.03, transmission=0.95, alpha=0.12)

    # Left clear panel
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-width / 2.0 + wall_thickness / 2.0, 0.0, panel_z))
    p_left = bpy.context.active_object
    p_left.name = "cage_panel_left"
    p_left.scale = (glass_thick, depth - corner_r * 1.4, panel_h)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_to_collection(p_left, cage_col)
    assign_preview_material(p_left, "mat_cage_glass", (0.88, 0.95, 0.98), roughness=0.03, transmission=0.95, alpha=0.12)

    # Right clear panel
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(width / 2.0 - wall_thickness / 2.0, 0.0, panel_z))
    p_right = bpy.context.active_object
    p_right.name = "cage_panel_right"
    p_right.scale = (glass_thick, depth - corner_r * 1.4, panel_h)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_to_collection(p_right, cage_col)
    assign_preview_material(p_right, "mat_cage_glass", (0.88, 0.95, 0.98), roughness=0.03, transmission=0.95, alpha=0.12)

    # Back panel with ventilation slots
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, depth / 2.0 - wall_thickness / 2.0, panel_z))
    p_back = bpy.context.active_object
    p_back.name = "cage_panel_back"
    p_back.scale = (width - corner_r * 1.4, glass_thick, panel_h)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_to_collection(p_back, cage_col)
    assign_preview_material(p_back, "mat_cage_glass", (0.88, 0.95, 0.98), roughness=0.03, transmission=0.95, alpha=0.12)

    # Corner vertical pillars connecting tub to top rim
    corner_positions = [
        (width / 2.0 - 0.012, depth / 2.0 - 0.012),
        (-width / 2.0 + 0.012, depth / 2.0 - 0.012),
        (-width / 2.0 + 0.012, -depth / 2.0 + 0.012),
        (width / 2.0 - 0.012, -depth / 2.0 + 0.012),
    ]
    for idx, (cx, cy) in enumerate(corner_positions):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=panel_h, vertices=16, location=(cx, cy, panel_z))
        pillar = bpy.context.active_object
        pillar.name = f"cage_corner_post_{idx+1}"
        link_to_collection(pillar, cage_col)
        assign_preview_material(pillar, "mat_cage_tub", (0.14, 0.16, 0.18), roughness=0.35)

    # Ventilation louver bars on back panel
    for i in range(9):
        vx = -0.32 + i * 0.08
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(vx, depth / 2.0 - wall_thickness / 2.0, total_height - 0.06))
        slot = bpy.context.active_object
        slot.name = f"cage_vent_slot_{i+1:02d}"
        slot.scale = (0.005, 0.008, 0.06)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        link_to_collection(slot, cage_col)
        assign_preview_material(slot, "mat_cage_tub", (0.14, 0.16, 0.18), roughness=0.35)

    # 3. Open-Center Top Rim Frame
    rim = create_open_top_rim(
        "cage_top_rim",
        width=width + 0.01,
        depth=depth + 0.01,
        rim_width=0.024,
        rim_height=0.014,
        z_pos=total_height - 0.007,
        corner_radius=corner_r + 0.005,
        collection=cage_col
    )
    assign_preview_material(rim, "mat_cage_tub", (0.14, 0.16, 0.18), roughness=0.35)


def create_hollow_wheel_drum(name: str, radius: float, depth: float, loc: Vector, rot: Euler,
                             collection: bpy.types.Collection) -> bpy.types.Object:
    """Creates an open-front hollow exercise wheel drum with back wall and running track."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    # Create cylinder along Z, then delete +Z cap so the front side (-Y after +90deg X rot) is open!
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=64, radius1=radius, radius2=radius, depth=depth)
    for f in list(bm.faces):
        if f.normal.z > 0.9:  # front-facing cap (-Y in world space after +90deg X rotation)
            bmesh.ops.delete(bm, geom=[f], context='FACES')

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.rotation_euler = rot
    link_to_collection(obj, collection)

    solid = obj.modifiers.new("Solidify", 'SOLIDIFY')
    solid.thickness = 0.005
    solid.offset = -1.0
    solid.use_even_offset = True

    bev = obj.modifiers.new("Bevel", 'BEVEL')
    bev.width = 0.0015
    bev.segments = 2
    bev.limit_method = 'ANGLE'

    set_smooth_By_angle(obj)
    return obj


def create_concave_bowl(name: str, radius: float, height: float, loc: Vector, rot: Euler,
                        collection: bpy.types.Collection) -> bpy.types.Object:
    """Creates a realistic concave ceramic food bowl."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=40,
                          radius1=radius * 0.88, radius2=radius, depth=height)
    # Delete top cap to make it an open bowl
    for f in list(bm.faces):
        if f.normal.z > 0.9:
            bmesh.ops.delete(bm, geom=[f], context='FACES')

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.rotation_euler = rot
    link_to_collection(obj, collection)

    solid = obj.modifiers.new("Solidify", 'SOLIDIFY')
    solid.thickness = 0.006
    solid.offset = -1.0
    solid.use_even_offset = True

    bev = obj.modifiers.new("Bevel", 'BEVEL')
    bev.width = 0.0025
    bev.segments = 3
    bev.limit_method = 'ANGLE'

    set_smooth_By_angle(obj)
    return obj


def create_hideout_with_arch(name: str, width: float, depth: float, height: float,
                             loc: Vector, rot: Euler, collection: bpy.types.Collection) -> bpy.types.Object:
    """Creates a wooden hideout cabin with an open arched doorway on the front wall."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc + Vector((0, 0, height / 2.0)), rotation=rot)
    cabin = bpy.context.active_object
    cabin.name = name
    cabin.scale = (width, depth, height)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_to_collection(cabin, collection)

    # Create arch cutter for boolean doorway
    door_w, door_h = 0.062, 0.068
    bpy.ops.mesh.primitive_cylinder_add(
        radius=door_w / 2.0, depth=depth * 1.5, vertices=24,
        location=loc + Vector((0, 0, door_h - door_w / 2.0)),
        rotation=(math.pi / 2.0, 0.0, rot.z)
    )
    arch_top = bpy.context.active_object

    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=loc + Vector((0, 0, (door_h - door_w / 2.0) / 2.0)),
        rotation=rot
    )
    arch_bot = bpy.context.active_object
    arch_bot.scale = (door_w, depth * 1.5, door_h - door_w / 2.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # Boolean difference to carve doorway through cabin
    for cutter in (arch_top, arch_bot):
        bool_mod = cabin.modifiers.new("DoorCut", 'BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.object = cutter
        bpy.context.view_layer.objects.active = cabin
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)

    bev = cabin.modifiers.new("Bevel", 'BEVEL')
    bev.width = 0.002
    bev.segments = 2
    bev.limit_method = 'ANGLE'
    return cabin


def create_hollow_tube(name: str, radius: float, length: float, loc: Vector, rot: Euler,
                       collection: bpy.types.Collection) -> bpy.types.Object:
    """Creates an open-ended hollow tunnel cylinder."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=32, radius1=radius, radius2=radius, depth=length)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.rotation_euler = rot
    link_to_collection(obj, collection)

    solid = obj.modifiers.new("Solidify", 'SOLIDIFY')
    solid.thickness = 0.004
    solid.offset = 1.0

    bev = obj.modifiers.new("Bevel", 'BEVEL')
    bev.width = 0.001
    bev.segments = 2
    set_smooth_By_angle(obj)
    return obj


def create_curved_elbow_tunnel(name: str, major_r: float, minor_r: float, loc: Vector, rot: Euler,
                               collection: bpy.types.Collection) -> bpy.types.Object:
    """Creates a 90-degree curved elbow tunnel section (quarter torus)."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    major_steps = 16
    minor_steps = 28
    rings = []
    for i in range(major_steps + 1):
        phi = (math.pi / 2.0) * (i / major_steps)
        ring = []
        cx = major_r * math.cos(phi)
        cy = major_r * math.sin(phi)
        for j in range(minor_steps):
            theta = 2.0 * math.pi * (j / minor_steps)
            r_curr = major_r + minor_r * math.cos(theta)
            x = r_curr * math.cos(phi)
            y = r_curr * math.sin(phi)
            z = minor_r * math.sin(theta)
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)

    for i in range(major_steps):
        for j in range(minor_steps):
            jn = (j + 1) % minor_steps
            bm.faces.new([rings[i][j], rings[i + 1][j], rings[i + 1][jn], rings[i][jn]])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.rotation_euler = rot
    link_to_collection(obj, collection)

    solid = obj.modifiers.new("Solidify", 'SOLIDIFY')
    solid.thickness = 0.004
    solid.offset = 1.0
    set_smooth_By_angle(obj)
    return obj


def build_props(props_col: bpy.types.Collection):
    """Builds all 5 required props with real thickness, hollow interiors, and natural placement."""
    base_z = 0.15  # Nominal top of bedding level

    # 1. EXERCISE WHEEL ON STAND (0.28m diameter)
    wheel_r = 0.14
    wheel_w = 0.09
    wheel_z = base_z + wheel_r + 0.025
    wheel_loc = Vector((-0.30, 0.13, wheel_z))
    wheel_rot = Euler((math.pi / 2.0, 0.0, math.radians(-6.0)))

    drum = create_hollow_wheel_drum("prop_wheel_drum", wheel_r, wheel_w, wheel_loc, wheel_rot, props_col)
    assign_preview_material(drum, "mat_wheel_wood", (0.76, 0.60, 0.42), roughness=0.55)

    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.022, depth=wheel_w + 0.03, vertices=24,
        location=wheel_loc + Vector((0.0, 0.015, 0.0)),
        rotation=wheel_rot
    )
    axle = bpy.context.active_object
    axle.name = "prop_wheel_axle"
    link_to_collection(axle, props_col)
    assign_preview_material(axle, "mat_metal_steel", (0.75, 0.77, 0.80), roughness=0.22, metallic=0.9)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-0.30, 0.15, base_z - 0.04), rotation=(0, 0, math.radians(-6.0)))
    stand = bpy.context.active_object
    stand.name = "prop_wheel_stand"
    stand.scale = (0.18, 0.13, 0.012)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_to_collection(stand, props_col)
    assign_preview_material(stand, "mat_wheel_wood", (0.76, 0.60, 0.42), roughness=0.55)

    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(-0.30, 0.195, (wheel_z + base_z - 0.04) / 2.0),
        rotation=(0, 0, math.radians(-6.0))
    )
    arm = bpy.context.active_object
    arm.name = "prop_wheel_arm"
    arm.scale = (0.028, 0.016, wheel_z - (base_z - 0.04) + 0.02)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_to_collection(arm, props_col)
    assign_preview_material(arm, "mat_wheel_wood", (0.76, 0.60, 0.42), roughness=0.55)

    # 2. CERAMIC FOOD BOWL (0.08m diameter, concave)
    bowl_loc = Vector((0.28, -0.11, base_z + 0.018))
    bowl_rot = Euler((math.radians(1.5), math.radians(-2.0), math.radians(12.0)))
    bowl = create_concave_bowl("prop_bowl", radius=0.042, height=0.036, loc=bowl_loc, rot=bowl_rot, collection=props_col)
    assign_preview_material(bowl, "mat_ceramic_bowl", (0.92, 0.89, 0.84), roughness=0.18)

    # 3. WALL-MOUNTED WATER BOTTLE (0.15m body + angled steel spout)
    bottle_loc = Vector((0.455, -0.02, 0.285))
    bpy.ops.mesh.primitive_cylinder_add(radius=0.026, depth=0.14, vertices=32, location=bottle_loc)
    bottle = bpy.context.active_object
    bottle.name = "prop_bottle_body"
    link_to_collection(bottle, props_col)
    set_smooth_By_angle(bottle)
    assign_preview_material(bottle, "mat_bottle_clear", (0.85, 0.93, 1.0), roughness=0.08, transmission=0.88, alpha=0.35)

    # Bottle cap
    bpy.ops.mesh.primitive_cylinder_add(radius=0.027, depth=0.022, vertices=32, location=bottle_loc + Vector((0, 0, -0.075)))
    cap = bpy.context.active_object
    cap.name = "prop_bottle_cap"
    link_to_collection(cap, props_col)
    assign_preview_material(cap, "mat_bottle_cap", (0.20, 0.38, 0.62), roughness=0.35)

    # Angled metal spout
    spout_loc = bottle_loc + Vector((-0.022, 0.0, -0.102))
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.004, depth=0.048, vertices=16,
        location=spout_loc,
        rotation=(0.0, math.radians(42.0), 0.0)
    )
    spout = bpy.context.active_object
    spout.name = "prop_bottle_spout"
    link_to_collection(spout, props_col)
    set_smooth_By_angle(spout)
    assign_preview_material(spout, "mat_metal_steel", (0.78, 0.80, 0.83), roughness=0.20, metallic=0.95)

    # Wall bracket clip
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.482, -0.02, 0.29))
    bracket = bpy.context.active_object
    bracket.name = "prop_bottle_bracket"
    bracket.scale = (0.022, 0.056, 0.04)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_to_collection(bracket, props_col)
    assign_preview_material(bracket, "mat_cage_tub", (0.14, 0.16, 0.18), roughness=0.35)

    # 4. WOODEN HIDEOUT WITH ARCHED DOORWAY
    hideout_loc = Vector((0.28, 0.11, base_z))
    hideout_rot = Euler((0.0, 0.0, math.radians(-16.0)))
    hw, hd, hh = 0.16, 0.13, 0.105
    hideout = create_hideout_with_arch("prop_hideout", hw, hd, hh, hideout_loc, hideout_rot, props_col)
    assign_preview_material(hideout, "mat_hideout_wood", (0.62, 0.45, 0.29), roughness=0.65)

    # Overhanging roof
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=hideout_loc + Vector((0, 0, hh + 0.007)),
        rotation=hideout_rot
    )
    roof = bpy.context.active_object
    roof.name = "prop_hideout_roof"
    roof.scale = (hw + 0.024, hd + 0.024, 0.014)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bev_r = roof.modifiers.new("Bevel", 'BEVEL')
    bev_r.width = 0.002
    bev_r.segments = 2
    link_to_collection(roof, props_col)
    assign_preview_material(roof, "mat_hideout_roof", (0.48, 0.33, 0.20), roughness=0.68)

    # 5. MODULAR BURROW TUNNEL (2 straight + 1 90-deg curved elbow)
    tun_r = 0.036
    major_r = 0.08
    elbow_center = Vector((-0.04, -0.05, base_z + tun_r))

    # Curved 90-deg elbow in X-Y plane (from angle 0 to 90 deg)
    tun_curve = create_curved_elbow_tunnel(
        "prop_tunnel_curve",
        major_r=major_r,
        minor_r=tun_r,
        loc=elbow_center,
        rot=Euler((0.0, 0.0, math.radians(15.0))),
        collection=props_col
    )
    assign_preview_material(tun_curve, "mat_tunnel_cork", (0.55, 0.41, 0.27), roughness=0.72)

    # Compute exact endpoints of the rotated quarter-torus so the two straight sections join seamlessly
    rot_m = Matrix.Rotation(math.radians(15.0), 3, 'Z')
    len1 = 0.14
    # End 1 is at phi=0 (local +X, tangent towards -Y)
    p1_local = Vector((major_r, -len1 / 2.0, 0.0))
    t1_loc = elbow_center + (rot_m @ p1_local)
    t1_rot = Euler((math.pi / 2.0, 0.0, math.radians(15.0)))
    tun1 = create_hollow_tube("prop_tunnel_straight_1", tun_r, len1, t1_loc, t1_rot, props_col)
    assign_preview_material(tun1, "mat_tunnel_cork", (0.55, 0.41, 0.27), roughness=0.72)

    # End 2 is at phi=90 deg (local +Y, tangent towards -X)
    len2 = 0.12
    p2_local = Vector((-len2 / 2.0, major_r, 0.0))
    t2_loc = elbow_center + (rot_m @ p2_local)
    t2_rot = Euler((0.0, math.pi / 2.0, math.radians(15.0)))
    tun2 = create_hollow_tube("prop_tunnel_straight_2", tun_r, len2, t2_loc, t2_rot, props_col)
    assign_preview_material(tun2, "mat_tunnel_cork", (0.55, 0.41, 0.27), roughness=0.72)


def setup_cameras_and_lights(cams_col: bpy.types.Collection, lights_col: bpy.types.Collection, cage_col: bpy.types.Collection):
    """Sets up grounded studio surface, calibrated lighting, and Track-To aimed cameras."""
    target = Vector((0.0, 0.0, 0.18))

    # Subtle tabletop plane underneath the cage to catch shadows and ground the scene
    bpy.ops.mesh.primitive_plane_add(size=4.0, location=(0.0, 0.0, -0.006))
    table = bpy.context.active_object
    table.name = "cage_studio_tabletop"
    link_to_collection(table, cage_col)
    assign_preview_material(table, "mat_studio_table", (0.22, 0.20, 0.18), roughness=0.65)

    # 1. Three-Quarter Camera
    cam_tq_data = bpy.data.cameras.new("cam_three_quarter")
    cam_tq_data.lens = 45.0
    cam_tq_data.clip_start = 0.01
    cam_tq_data.clip_end = 50.0
    cam_tq_obj = bpy.data.objects.new("cam_three_quarter", cam_tq_data)
    cam_tq_obj.location = Vector((1.05, -1.25, 0.82))
    look_at(cam_tq_obj, target)
    link_to_collection(cam_tq_obj, cams_col)

    # 2. Top-Down Camera
    cam_top_data = bpy.data.cameras.new("cam_top")
    cam_top_data.lens = 35.0
    cam_top_obj = bpy.data.objects.new("cam_top", cam_top_data)
    cam_top_obj.location = Vector((0.0, -0.01, 1.35))
    look_at(cam_top_obj, Vector((0.0, 0.0, 0.15)))
    link_to_collection(cam_top_obj, cams_col)

    # 3. Key Light (Soft Window Area Light)
    key_data = bpy.data.lights.new("light_key", 'AREA')
    key_data.energy = 18.0
    key_data.size = 0.9
    key_data.color = (1.0, 0.96, 0.90)
    key_obj = bpy.data.objects.new("light_key", key_data)
    key_obj.location = Vector((0.9, -1.0, 1.15))
    look_at(key_obj, target)
    link_to_collection(key_obj, lights_col)

    # 4. Fill Light (Cool Sky Bounce)
    fill_data = bpy.data.lights.new("light_fill", 'AREA')
    fill_data.energy = 8.0
    fill_data.size = 1.2
    fill_data.color = (0.88, 0.93, 1.0)
    fill_obj = bpy.data.objects.new("light_fill", fill_data)
    fill_obj.location = Vector((-1.0, 0.7, 1.0))
    look_at(fill_obj, target)
    link_to_collection(fill_obj, lights_col)

    # 5. Rim / Back Light
    rim_data = bpy.data.lights.new("light_rim", 'AREA')
    rim_data.energy = 10.0
    rim_data.size = 0.7
    rim_data.color = (1.0, 0.94, 0.85)
    rim_obj = bpy.data.objects.new("light_rim", rim_data)
    rim_obj.location = Vector((0.2, 0.95, 0.95))
    look_at(rim_obj, target)
    link_to_collection(rim_obj, lights_col)

    # Set World background to soft neutral studio interior
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.18, 0.19, 0.21, 1.0)
        bg.inputs["Strength"].default_value = 0.6


def render_view(camera_name: str, output_path: str, samples: int = 96):
    """Renders the scene from the specified camera to disk."""
    scene = bpy.context.scene
    scene.camera = bpy.data.objects[camera_name]
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.filepath = os.path.abspath(output_path)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    bpy.ops.render.render(write_still=True)
    print(f">> Rendered: {output_path}")


def main():
    print("\n" + "=" * 60)
    print(" HAMMY PIPELINE — BUILD CAGE GEOMETRY (PROMPT 1 REFINED)")
    print("=" * 60)

    # 1. Remove default startup Cube, Light, Camera
    clean_startup_defaults()

    # 2. Enforce units & metric scale
    common.set_unit_scale_metric()

    # 3. Configure Cycles GPU OptiX
    gpu_info = common.configure_cycles_gpu("OPTIX")
    print(f"GPU Engine Status: {gpu_info}")

    # 4. Create or clear top-level collections (Idempotent)
    master_col = bpy.context.scene.collection
    cage_col = common.get_or_create_collection("CAGE", parent=master_col)
    props_col = common.get_or_create_collection("PROPS", parent=master_col)
    lights_col = common.get_or_create_collection("LIGHTS", parent=master_col)
    cams_col = common.get_or_create_collection("CAMERAS", parent=master_col)

    common.clear_collection("CAGE")
    common.clear_collection("PROPS")
    common.clear_collection("LIGHTS")
    common.clear_collection("CAMERAS")

    # 5. Build Cage & Props
    print("Building Cage structure (Open Tub, Clear Acrylic Panels, Vents, Top Frame)...")
    build_cage(cage_col)

    print("Building Props (Hollow Wheel, Concave Bowl, Water Bottle, Arched Hideout, Hollow Tunnel)...")
    build_props(props_col)

    # 6. Setup Cameras & Studio Lights
    print("Setting up Cameras & Calibrated Studio Lights...")
    setup_cameras_and_lights(cams_col, lights_col, cage_col)

    # Set active camera to cam_three_quarter
    bpy.context.scene.camera = bpy.data.objects["cam_three_quarter"]

    # 7. Save Scene .blend
    scene_path = os.path.abspath("blender/scene.blend")
    os.makedirs("blender", exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=scene_path)
    print(f">> Saved scene: {scene_path}")

    # 8. Render Acceptance Views (1080p Cycles OptiX)
    render_view("cam_three_quarter", "renders/tests/01_cage_three_quarter.png", samples=96)
    render_view("cam_top", "renders/tests/01_cage_top.png", samples=96)

    print("=" * 60)
    print(" PROMPT 1 COMPLETE — CAGE & PROPS GEOMETRY READY")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
