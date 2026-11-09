"""
HAMMY Art Pipeline — Prompt 2: Bedding, Seeds, and Clutter
Reads rules.md first.
Builds:
  - BEDDING Collection:
      * bedding_surface: Uneven 0.15-0.20m deep volumetric bedding mesh with layered noise
        (large mounds + medium undulations + fine ripples), a nest depression, and a
        compressed running trail along the front wall.
      * Instanced curled wood shavings & crinkled paper strips via Geometry Nodes + prototype meshes.
  - PROPS Collection (Clutter additions):
      * Seeds (sunflower husks, golden millet, extruded pellets) inside the ceramic bowl,
        in a back-corner hoard, and loose strays along the trail.
      * Applewood chew twigs and gnawed wooden chew blocks.
      * Procedural chewed/gnawed edges on the wooden hideout doorway and tunnel rim.

Idempotent: clears and rebuilds BEDDING and clutter-prefixed objects in PROPS.
Outputs:
  - blender/scene.blend
  - renders/tests/02_clutter_closeup.png
  - renders/tests/02_clutter_wide.png
"""

import os
import sys
import math
import random
import bpy
import bmesh
from mathutils import Vector, Euler, Matrix, noise

# Reproducible layout seed (Rule 5 / Prompt 2 requirement)
RANDOM_SEED = 42

scripts_dir = os.path.dirname(os.path.abspath(__file__))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

import common


def link_to_collection(obj: bpy.types.Object, target_col: bpy.types.Collection):
    if obj.name not in target_col.objects:
        target_col.objects.link(obj)
    for col in list(obj.users_collection):
        if col != target_col:
            col.objects.unlink(obj)


def look_at(obj: bpy.types.Object, target: Vector):
    direction = target - obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    obj.rotation_euler = rot_quat.to_euler()


def assign_material(obj: bpy.types.Object, name: str, base_color: tuple,
                    roughness: float = 0.6, subsurface: float = 0.0):
    mat = common.make_material(name, use_nodes=True)
    mat.diffuse_color = (base_color[0], base_color[1], base_color[2], 1.0)
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (base_color[0], base_color[1], base_color[2], 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if subsurface > 0.0 and "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = subsurface
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return mat


def evaluate_bedding_height(x: float, y: float, seed_offset: float = 0.0) -> float:
    """
    Computes the realistic bedding height z(x, y) in meters (range ~0.135m to 0.205m):
      - Base depth: 0.165m
      - Large mounds near back-right corner (hideout/hoard) and back-left corner
      - Compressed running trail along the front wall (y ~ -0.16)
      - Cozy nest depression near front-right / hideout entrance (x ~ 0.24, y ~ 0.04)
      - Layered multi-octave Perlin noise (mounds + ripples)
    """
    base_z = 0.162

    # 1. Large organic mounds (low-frequency noise)
    p_low = Vector((x * 2.8 + seed_offset, y * 2.8 + seed_offset, 1.3))
    mound_noise = noise.fractal(p_low, 0.8, 2.0, 3) * 0.022

    # 2. Corner piling effect (hamsters push bedding into back corners)
    back_pile = max(0.0, (y + 0.10) / 0.34) * 0.024
    right_back_mound = 0.028 * math.exp(-((x - 0.36) ** 2 / 0.035 + (y - 0.15) ** 2 / 0.025))
    left_back_mound = 0.020 * math.exp(-((x + 0.35) ** 2 / 0.040 + (y - 0.14) ** 2 / 0.025))

    # 3. Shallow Nest Depression near hideout doorway (x=0.25, y=0.03)
    nest_dist_sq = ((x - 0.25) / 0.085) ** 2 + ((y - 0.02) / 0.075) ** 2
    nest_depression = -0.026 * math.exp(-nest_dist_sq)
    # Slight raised rim around the nest
    nest_rim = 0.010 * math.exp(-((nest_dist_sq - 1.2) ** 2) / 0.6)

    # 4. Compressed Running Trail along the front wall (y = -0.15, from x = -0.32 to x = +0.35)
    trail_y = -0.15 + 0.02 * math.sin(x * 5.0)
    trail_factor_x = 1.0 / (1.0 + math.exp(-15.0 * (x + 0.38))) * (1.0 / (1.0 + math.exp(15.0 * (x - 0.38))))
    trail_depression = -0.019 * trail_factor_x * math.exp(-((y - trail_y) / 0.048) ** 2)

    # 5. Medium & fine surface ripples
    p_med = Vector((x * 11.0 - seed_offset, y * 11.0 + seed_offset, 4.7))
    ripples = noise.fractal(p_med, 0.7, 2.1, 3) * 0.0065

    p_fine = Vector((x * 32.0 + seed_offset, y * 32.0, 9.1))
    fine_grain = noise.noise(p_fine) * 0.0025

    z = (
        base_z
        + mound_noise
        + back_pile
        + right_back_mound
        + left_back_mound
        + nest_depression
        + nest_rim
        + trail_depression
        + ripples
        + fine_grain
    )
    return max(0.125, min(0.205, z))


def build_bedding_surface(bedding_col: bpy.types.Collection, seed_val: int) -> bpy.types.Object:
    """
    Builds a displaced volumetric bedding mesh fitting inside the rounded cage tub
    with a vertex group 'TopSurface' for scattering shavings.
    """
    width = 0.982
    depth = 0.482
    corner_r = 0.036
    nx, ny = 96, 48
    seed_offset = (seed_val % 100) * 0.37

    mesh = bpy.data.meshes.new("bedding_surface")
    bm = bmesh.new()

    half_w = width / 2.0
    half_d = depth / 2.0

    # Create grid of top and bottom vertices, clamping to rounded rectangle footprint
    top_grid = []
    bot_grid = []

    for iy in range(ny + 1):
        v_frac = iy / ny
        y = -half_d + depth * v_frac
        row_top = []
        row_bot = []
        for ix in range(nx + 1):
            u_frac = ix / nx
            x = -half_w + width * u_frac

            # Clamp (x, y) inside the rounded corner rectangle
            cx = max(-half_w + corner_r, min(half_w - corner_r, x))
            cy = max(-half_d + corner_r, min(half_d - corner_r, y))
            dx, dy = x - cx, y - cy
            dist = math.hypot(dx, dy)
            if dist > corner_r:
                x = cx + (dx / dist) * corner_r
                y = cy + (dy / dist) * corner_r

            z_top = evaluate_bedding_height(x, y, seed_offset)
            vt = bm.verts.new((x, y, z_top))
            vb = bm.verts.new((x, y, 0.006))
            row_top.append(vt)
            row_bot.append(vb)
        top_grid.append(row_top)
        bot_grid.append(row_bot)

    # Top and bottom faces
    for iy in range(ny):
        for ix in range(nx):
            # Top quad
            bm.faces.new([
                top_grid[iy][ix],
                top_grid[iy][ix + 1],
                top_grid[iy + 1][ix + 1],
                top_grid[iy + 1][ix],
            ])
            # Bottom quad
            bm.faces.new([
                bot_grid[iy][ix],
                bot_grid[iy + 1][ix],
                bot_grid[iy + 1][ix + 1],
                bot_grid[iy][ix + 1],
            ])

    # Perimeter side walls so the bedding volume looks thick through the clear tub/walls
    for ix in range(nx):
        bm.faces.new([bot_grid[0][ix], top_grid[0][ix], top_grid[0][ix + 1], bot_grid[0][ix + 1]])
        bm.faces.new([bot_grid[ny][ix + 1], top_grid[ny][ix + 1], top_grid[ny][ix], bot_grid[ny][ix]])
    for iy in range(ny):
        bm.faces.new([bot_grid[iy + 1][0], top_grid[iy + 1][0], top_grid[iy][0], bot_grid[iy][0]])
        bm.faces.new([bot_grid[iy][nx], top_grid[iy][nx], top_grid[iy + 1][nx], bot_grid[iy + 1][nx]])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()

    for poly in mesh.polygons:
        poly.use_smooth = True

    obj = bpy.data.objects.new("bedding_surface", mesh)
    link_to_collection(obj, bedding_col)
    assign_material(obj, "mat_bedding_base", (0.86, 0.79, 0.66), roughness=0.88, subsurface=0.15)
    return obj


def build_shaving_scatter(bedding_col: bpy.types.Collection, seed_val: int):
    """
    Creates 3 batched mesh layers of curled aspen shavings & crinkled paper strips
    scattered across the uneven bedding surface with density variation, random curl,
    and scale variation, keeping total triangle count fast and light (~14k tris).
    """
    rng = random.Random(seed_val)
    seed_offset = (seed_val % 100) * 0.37

    shaving_variants = [
        ("bedding_shavings_aspen", (0.89, 0.81, 0.65), 0.82, 0.20, 1100, 0.013, 0.005),
        ("bedding_strips_paper_white", (0.95, 0.94, 0.91), 0.88, 0.35, 750, 0.016, 0.006),
        ("bedding_flakes_natural", (0.80, 0.70, 0.54), 0.85, 0.15, 700, 0.011, 0.0045),
    ]

    for mesh_name, col_rgb, rough, sss, count, base_len, base_w in shaving_variants:
        mesh = bpy.data.meshes.new(mesh_name)
        bm = bmesh.new()

        placed = 0
        attempts = 0
        while placed < count and attempts < count * 4:
            attempts += 1
            x = rng.uniform(-0.465, 0.465)
            y = rng.uniform(-0.220, 0.220)

            # Higher density around nest & mounds, slightly lower along compressed trail
            if abs(y - (-0.15)) < 0.035 and rng.random() < 0.35:
                continue

            z_surf = evaluate_bedding_height(x, y, seed_offset)
            s_len = base_len * rng.uniform(0.65, 1.45)
            s_wid = base_w * rng.uniform(0.65, 1.35)
            curl_h = rng.uniform(0.0012, 0.0038)

            yaw = rng.uniform(0.0, math.tau)
            pitch = rng.uniform(-0.32, 0.32)
            roll = rng.uniform(-0.35, 0.35)
            rot_mat = Euler((pitch, roll, yaw), 'XYZ').to_matrix()
            center = Vector((x, y, z_surf + 0.0008))

            # Build a 3-segment curved ribbon (6 verts, 2 quads = 4 triangles per shaving)
            v_list = []
            for seg in range(3):
                t = (seg / 2.0) - 0.5  # -0.5, 0.0, +0.5
                lx = t * s_len
                lz = (1.0 - (2.0 * t) ** 2) * curl_h
                for side in (-0.5, 0.5):
                    ly = side * s_wid * (0.85 if seg != 1 else 1.0)
                    p = center + (rot_mat @ Vector((lx, ly, lz)))
                    v_list.append(bm.verts.new(p))

            bm.faces.new([v_list[0], v_list[2], v_list[3], v_list[1]])
            bm.faces.new([v_list[2], v_list[4], v_list[5], v_list[3]])
            placed += 1

        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(mesh)
        bm.free()

        for poly in mesh.polygons:
            poly.use_smooth = True

        obj = bpy.data.objects.new(mesh_name, mesh)
        link_to_collection(obj, bedding_col)
        assign_material(obj, f"mat_{mesh_name}", col_rgb, roughness=rough, subsurface=sss)


def sync_props_to_bedding(props_col: bpy.types.Collection, seed_val: int):
    """
    Adjusts the vertical heights and slight pitch/roll of the cage props in PROPS
    so they sit naturally embedded in the uneven displaced bedding surface!
    """
    seed_offset = (seed_val % 100) * 0.37

    # 1. Ceramic Bowl at (0.28, -0.11) settled slightly into bedding
    if "prop_bowl" in bpy.data.objects:
        bowl = bpy.data.objects["prop_bowl"]
        bz = evaluate_bedding_height(bowl.location.x, bowl.location.y, seed_offset)
        bowl.location.z = bz + 0.012

    # 2. Wooden Hideout at (0.28, 0.11) nestled into bedding (origin is at center Z = base + hh/2)
    if "prop_hideout" in bpy.data.objects:
        hideout = bpy.data.objects["prop_hideout"]
        hh = 0.105
        hz_base = evaluate_bedding_height(hideout.location.x, hideout.location.y, seed_offset) - 0.008
        hideout.location.z = hz_base + (hh / 2.0)
        if "prop_hideout_roof" in bpy.data.objects:
            roof = bpy.data.objects["prop_hideout_roof"]
            roof.location.z = hz_base + hh + 0.007

    # 3. Burrow Tunnel partially nestled in bedding
    for tname in ("prop_tunnel_curve", "prop_tunnel_straight_1", "prop_tunnel_straight_2"):
        if tname in bpy.data.objects:
            tobj = bpy.data.objects[tname]
            tz = evaluate_bedding_height(tobj.location.x, tobj.location.y, seed_offset)
            tobj.location.z = tz + 0.022


def build_seeds_and_hoard(props_col: bpy.types.Collection, seed_val: int):
    """
    Scatters seeds, extruded pellets, and corn flakes in three natural zones:
      1. Inside the ceramic food bowl (mounded mix + a few spilled seeds outside)
      2. A corner hoard tucked near the back-right wall (x ~ 0.41, y ~ 0.19)
      3. Loose strays along the compressed foraging trail
    Batched by material type for fast rendering and low object overhead.
    """
    rng = random.Random(seed_val + 101)
    seed_offset = (seed_val % 100) * 0.37

    bowl_x, bowl_y = 0.28, -0.11
    bowl_z = evaluate_bedding_height(bowl_x, bowl_y, seed_offset) + 0.008

    # Also add a rounded food mound base inside the bowl
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=24, ring_count=12, radius=0.035,
        location=(bowl_x, bowl_y, bowl_z)
    )
    mound = bpy.context.active_object
    mound.name = "prop_food_bowl_fill"
    mound.scale = (1.0, 1.0, 0.35)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_to_collection(mound, props_col)
    assign_material(mound, "mat_seed_mix_base", (0.58, 0.46, 0.30), roughness=0.80)

    def get_scatter_positions(n_bowl: int, n_hoard: int, n_stray: int):
        positions = []
        # Zone 1: Inside food bowl
        for _ in range(n_bowl):
            r = 0.032 * math.sqrt(rng.random())
            theta = rng.uniform(0, math.tau)
            px = bowl_x + r * math.cos(theta)
            py = bowl_y + r * math.sin(theta)
            pz = bowl_z + 0.011 * (1.0 - (r / 0.035) ** 2) + rng.uniform(-0.001, 0.002)
            positions.append((px, py, pz))

        # Zone 2: Corner hoard (tucked at back-right corner x=0.41, y=0.18)
        hoard_cx, hoard_cy = 0.41, 0.18
        for _ in range(n_hoard):
            r = abs(rng.gauss(0.0, 0.024))
            theta = rng.uniform(0, math.tau)
            px = max(-0.46, min(0.46, hoard_cx + r * math.cos(theta)))
            py = max(-0.21, min(0.21, hoard_cy + r * math.sin(theta)))
            pz = evaluate_bedding_height(px, py, seed_offset) + rng.uniform(0.001, 0.004)
            positions.append((px, py, pz))

        # Zone 3: Loose strays & clusters near bowl & along trail
        for _ in range(n_stray):
            if rng.random() < 0.55:
                # Near bowl spill
                r = rng.uniform(0.048, 0.12)
                theta = rng.uniform(0, math.tau)
                px = bowl_x + r * math.cos(theta)
                py = bowl_y + r * math.sin(theta)
            else:
                # Along foraging trail
                px = rng.uniform(-0.28, 0.35)
                py = rng.gauss(-0.14, 0.045)
            px = max(-0.45, min(0.45, px))
            py = max(-0.21, min(0.21, py))
            pz = evaluate_bedding_height(px, py, seed_offset) + 0.0015
            positions.append((px, py, pz))
        return positions

    # 1. Sunflower Seeds (dark charcoal husks, teardrop shape)
    sf_mesh = bpy.data.meshes.new("prop_seeds_sunflower")
    bm_sf = bmesh.new()
    for px, py, pz in get_scatter_positions(n_bowl=45, n_hoard=55, n_stray=35):
        bmesh.ops.create_icosphere(bm_sf, subdivisions=1, radius=1.0)
        new_verts = bm_sf.verts[-12:]
        rot = Euler((rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(0, math.tau))).to_matrix()
        for v in new_verts:
            # Teardrop taper along X
            taper = 0.65 if v.co.x > 0 else 1.0
            local_p = Vector((v.co.x * 0.0055, v.co.y * 0.0026 * taper, v.co.z * 0.0018))
            v.co = Vector((px, py, pz)) + (rot @ local_p)
    bmesh.ops.recalc_face_normals(bm_sf, faces=bm_sf.faces[:])
    bm_sf.to_mesh(sf_mesh)
    bm_sf.free()
    sf_obj = bpy.data.objects.new("prop_seeds_sunflower", sf_mesh)
    link_to_collection(sf_obj, props_col)
    assign_material(sf_obj, "mat_seed_sunflower", (0.16, 0.15, 0.14), roughness=0.45)

    # 2. Extruded Kibble Pellets (olive-brown mini cylinders)
    pl_mesh = bpy.data.meshes.new("prop_pellets_kibble")
    bm_pl = bmesh.new()
    for px, py, pz in get_scatter_positions(n_bowl=35, n_hoard=40, n_stray=25):
        res = bmesh.ops.create_cone(bm_pl, cap_ends=True, segments=8, radius1=0.0022, radius2=0.0022, depth=0.0075)
        new_verts = res["verts"]
        rot = Euler((math.pi / 2.0 + rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), rng.uniform(0, math.tau))).to_matrix()
        for v in new_verts:
            v.co = Vector((px, py, pz + 0.001)) + (rot @ v.co)
    bmesh.ops.recalc_face_normals(bm_pl, faces=bm_pl.faces[:])
    bm_pl.to_mesh(pl_mesh)
    bm_pl.free()
    pl_obj = bpy.data.objects.new("prop_pellets_kibble", pl_mesh)
    link_to_collection(pl_obj, props_col)
    assign_material(pl_obj, "mat_pellet_kibble", (0.36, 0.31, 0.19), roughness=0.78)

    # 3. Golden Millet & Corn Flakes
    ml_mesh = bpy.data.meshes.new("prop_seeds_millet_corn")
    bm_ml = bmesh.new()
    for px, py, pz in get_scatter_positions(n_bowl=60, n_hoard=65, n_stray=45):
        bmesh.ops.create_icosphere(bm_ml, subdivisions=1, radius=1.0)
        new_verts = bm_ml.verts[-12:]
        rot = Euler((rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), rng.uniform(0, math.tau))).to_matrix()
        scale_vec = Vector((0.0032, 0.0026, 0.0016)) if rng.random() < 0.4 else Vector((0.0016, 0.0015, 0.0014))
        for v in new_verts:
            local_p = Vector((v.co.x * scale_vec.x, v.co.y * scale_vec.y, v.co.z * scale_vec.z))
            v.co = Vector((px, py, pz)) + (rot @ local_p)
    bmesh.ops.recalc_face_normals(bm_ml, faces=bm_ml.faces[:])
    bm_ml.to_mesh(ml_mesh)
    bm_ml.free()
    ml_obj = bpy.data.objects.new("prop_seeds_millet_corn", ml_mesh)
    link_to_collection(ml_obj, props_col)
    assign_material(ml_obj, "mat_seed_golden", (0.85, 0.66, 0.22), roughness=0.55)


def build_chew_sticks_and_wear(props_col: bpy.types.Collection, seed_val: int):
    """
    Adds wooden chew sticks / gnawed blocks and applies realistic chewed edge notches
    to the wooden hideout doorway and burrow tunnel entrance.
    """
    rng = random.Random(seed_val + 202)
    seed_offset = (seed_val % 100) * 0.37

    # 1. Applewood Chew Twigs (3 scattered natural bark sticks with gnawed paler notches)
    twig_configs = [
        ("prop_chew_stick_1", (0.14, -0.15), 0.085, 0.0065, 38.0),
        ("prop_chew_stick_2", (-0.20, -0.13), 0.075, 0.0055, -24.0),
        ("prop_chew_stick_3", (0.37, 0.01), 0.068, 0.0060, 72.0),
    ]
    for name, (tx, ty), length, radius, angle_deg in twig_configs:
        tz = evaluate_bedding_height(tx, ty, seed_offset) + radius * 0.75
        mesh = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=radius, radius2=radius * 0.88, depth=length)
        # Subdivide along length so we can indent chewed middle section
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=4, use_grid_fill=True)
        for v in bm.verts:
            if abs(v.co.z) < length * 0.22:
                # Gnawed notch around middle
                v.co.x *= 0.76 + 0.08 * math.sin(v.co.z * 180.0)
                v.co.y *= 0.76 + 0.08 * math.cos(v.co.z * 180.0)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(mesh)
        bm.free()

        twig = bpy.data.objects.new(name, mesh)
        twig.location = (tx, ty, tz)
        twig.rotation_euler = (math.pi / 2.0, rng.uniform(-0.08, 0.08), math.radians(angle_deg))
        link_to_collection(twig, props_col)
        assign_material(twig, "mat_chew_bark", (0.42, 0.30, 0.19), roughness=0.82)

    # 2. Gnawed Wooden Chew Block near hideout/bowl
    bx, by = 0.17, -0.05
    bz = evaluate_bedding_height(bx, by, seed_offset) + 0.014
    bpy.ops.mesh.primitive_cube_add(size=0.028, location=(bx, by, bz), rotation=(0.12, -0.08, math.radians(29.0)))
    block = bpy.context.active_object
    block.name = "prop_chew_block"
    link_to_collection(block, props_col)
    bev = block.modifiers.new("Bevel", 'BEVEL')
    bev.width = 0.003
    bev.segments = 2
    assign_material(block, "mat_chew_wood_light", (0.78, 0.63, 0.44), roughness=0.70)

    # 3. Add chewed edge notches to prop_hideout doorway & corner using boolean tooth-mark cutters
    if "prop_hideout" in bpy.data.objects:
        hideout = bpy.data.objects["prop_hideout"]
        # Temporarily remove Bevel modifier so Boolean applies first cleanly
        for m in list(hideout.modifiers):
            if m.type == 'BEVEL':
                hideout.modifiers.remove(m)

        h_loc = hideout.location.copy()
        h_base_z = h_loc.z - (0.105 / 2.0)
        h_rot = hideout.rotation_euler.z
        rot_m = Matrix.Rotation(h_rot, 3, 'Z')

        # Positions along the doorway arch rim in local hideout space (relative to bottom of hideout)
        notch_locals = [
            Vector((-0.031, -0.065, 0.025)),
            Vector((-0.030, -0.065, 0.042)),
            Vector((0.031, -0.065, 0.030)),
            Vector((0.018, -0.065, 0.064)),
            Vector((-0.078, -0.064, 0.048)),
        ]
        for idx, n_loc in enumerate(notch_locals):
            world_p = Vector((h_loc.x, h_loc.y, h_base_z)) + (rot_m @ n_loc)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.0055, location=world_p)
            cutter = bpy.context.active_object
            cutter.scale = (1.3, 0.8, 0.6)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

            bool_mod = hideout.modifiers.new(f"ChewNotch_{idx}", 'BOOLEAN')
            bool_mod.operation = 'DIFFERENCE'
            bool_mod.object = cutter
            bpy.context.view_layer.objects.active = hideout
            bpy.ops.object.modifier_apply(modifier=bool_mod.name)
            bpy.data.objects.remove(cutter, do_unlink=True)

        bev = hideout.modifiers.new("Bevel", 'BEVEL')
        bev.width = 0.002
        bev.segments = 2
        bev.limit_method = 'ANGLE'


def setup_clutter_cameras(cams_col: bpy.types.Collection, seed_val: int):
    """Adds a macro close-up camera focused on the right corner (bowl, spilled seeds, hideout, hoard)."""
    seed_offset = (seed_val % 100) * 0.37
    target_z = evaluate_bedding_height(0.27, -0.02, seed_offset)
    focus_target = Vector((0.27, -0.01, target_z + 0.025))

    if "cam_closeup_corner" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["cam_closeup_corner"], do_unlink=True)

    cam_data = bpy.data.cameras.new("cam_closeup_corner")
    cam_data.lens = 55.0  # Macro portrait focal length
    cam_data.clip_start = 0.01
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = 8.0

    cam_obj = bpy.data.objects.new("cam_closeup_corner", cam_data)
    cam_obj.location = Vector((-0.02, -0.52, 0.42))
    look_at(cam_obj, focus_target)
    cam_data.dof.focus_distance = (cam_obj.location - focus_target).length
    link_to_collection(cam_obj, cams_col)


def render_view(camera_name: str, output_path: str, samples: int = 96):
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


def clear_clutter_objects(props_col: bpy.types.Collection):
    """Removes only the clutter objects added by 20_clutter.py so re-running is idempotent."""
    clutter_prefixes = ("prop_seeds_", "prop_pellets_", "prop_food_", "prop_chew_")
    for obj in list(props_col.objects):
        if obj.name.startswith(clutter_prefixes):
            props_col.objects.unlink(obj)
            bpy.data.objects.remove(obj, do_unlink=True)


def main():
    print("\n" + "=" * 60)
    print(f" HAMMY PIPELINE — BUILD BEDDING & CLUTTER (PROMPT 2 | SEED={RANDOM_SEED})")
    print("=" * 60)

    # Load scene.blend if running standalone in fresh Blender
    scene_path = os.path.abspath("blender/scene.blend")
    if os.path.exists(scene_path) and "cage_tub" not in bpy.data.objects:
        bpy.ops.wm.open_mainfile(filepath=scene_path)

    common.set_unit_scale_metric()
    common.configure_cycles_gpu("OPTIX")

    master_col = bpy.context.scene.collection
    bedding_col = common.get_or_create_collection("BEDDING", parent=master_col)
    props_col = common.get_or_create_collection("PROPS", parent=master_col)
    cams_col = common.get_or_create_collection("CAMERAS", parent=master_col)

    # Idempotent clear of BEDDING and clutter items in PROPS
    common.clear_collection("BEDDING")
    clear_clutter_objects(props_col)

    print("1. Generating uneven displaced bedding surface (0.15-0.20m deep)...")
    build_bedding_surface(bedding_col, RANDOM_SEED)

    print("2. Scattering instanced aspen shavings & crinkled paper strips...")
    build_shaving_scatter(bedding_col, RANDOM_SEED)

    print("3. Settling cage props into bedding contours...")
    sync_props_to_bedding(props_col, RANDOM_SEED)

    print("4. Scattering sunflower seeds, millet, pellets, and corner hoard...")
    build_seeds_and_hoard(props_col, RANDOM_SEED)

    print("5. Adding chew twigs, chew block, and gnawed hideout doorway notches...")
    build_chew_sticks_and_wear(props_col, RANDOM_SEED)

    print("6. Setting up macro close-up camera & saving scene...")
    setup_clutter_cameras(cams_col, RANDOM_SEED)

    bpy.ops.wm.save_as_mainfile(filepath=scene_path)
    print(f">> Saved scene: {scene_path}")

    # Render Prompt 2 validation shots
    render_view("cam_closeup_corner", "renders/tests/02_clutter_closeup.png", samples=96)
    render_view("cam_three_quarter", "renders/tests/02_clutter_wide.png", samples=96)

    print("=" * 60)
    print(" PROMPT 2 COMPLETE — BEDDING, SEEDS & CLUTTER READY")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

