"""
HAMMY Pipeline — Step 3 & Step 4:
Generate all missing assets and adapt/convert approved CC0 assets in Blender 5.2 LTS.

Run headless:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P scripts/step3_step4_build_and_optimize_assets.py

Requirements satisfied:
- Real-world Syrian hamster scale (~15 cm body length):
  - Foods: 0.010 m - 0.025 m, origin at paw pickup pivot (`pickup_pivot` empty included).
  - Costumes: 0.026 m - 0.046 m, origin at attachment point, includes named empty socket
    (`head_slot`, `neck_slot`, or `back_slot`) matching HamsterRig bones (`head`, `neck`, `spine_2`).
  - Water bottle (`water_bottle`) & Small water bowl (`water_bowl`): separate mesh named
    `water_liquid` with origin at the bottom of the liquid column so scaling Y (in Three.js Y-up)
    or Z (in Blender Z-up) scales the visible water level cleanly from 0.0 to 1.0.
  - Props & Decor: base-center pivot (`Z = 0` at bottom resting plane), under 5k tris per prop
    (under 2k tris for small items).
- Saves every `.blend` in `assets/source/<id>.blend`.
- Exports optimized `.glb` (Y-up for Three.js, applied scale, merged materials, textures <= 1024 / <= 512)
  to BOTH `assets/web/<id>.glb` and `web/public/assets/items/<id>.glb`.
- Renders a 256x256 studio thumbnail PNG for every asset to BOTH `assets/thumbnails/<id>.png`
  and `web/public/assets/thumbnails/<id>.png` (and copies existing Kenney CC0 previews where available).
- Writes `assets/manifest.json` and mirrors it to `web/public/assets/manifest.json`.
"""

import json
import math
import os
import random
import shutil
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "assets" / "raw"
SOURCE_DIR = ROOT_DIR / "assets" / "source"
WEB_ASSETS_DIR = ROOT_DIR / "assets" / "web"
THUMBS_DIR = ROOT_DIR / "assets" / "thumbnails"
PUBLIC_ITEMS_DIR = ROOT_DIR / "web" / "public" / "assets" / "items"
PUBLIC_THUMBS_DIR = ROOT_DIR / "web" / "public" / "assets" / "thumbnails"
PUBLIC_MANIFEST = ROOT_DIR / "web" / "public" / "assets" / "manifest.json"
MANIFEST_PATH = ROOT_DIR / "assets" / "manifest.json"
RESIZED_TEX_DIR = ROOT_DIR / "assets" / "source" / "textures_512"

for d in (SOURCE_DIR, WEB_ASSETS_DIR, THUMBS_DIR, PUBLIC_ITEMS_DIR, PUBLIC_THUMBS_DIR, RESIZED_TEX_DIR):
    d.mkdir(parents=True, exist_ok=True)


def reset_scene():
    """Clear all objects, meshes, materials, and images for a clean single-asset build."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"


def make_pbr_mat(
    name: str,
    base_color: tuple[float, float, float, float],
    roughness: float = 0.5,
    metallic: float = 0.0,
    transmission: float = 0.0,
    alpha: float = 1.0,
    subsurface: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.diffuse_color = base_color
    if alpha < 0.999 or transmission > 0.01:
        if hasattr(mat, "blend_method"):
            mat.blend_method = "BLEND"
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = alpha
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = transmission
    if subsurface > 0.0 and "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = subsurface
    return mat


def assign_mat(obj: bpy.types.Object, mat: bpy.types.Material):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def smooth_mesh(obj: bpy.types.Object):
    if obj.type == "MESH" and obj.data:
        for p in obj.data.polygons:
            p.use_smooth = True


def uv_unwrap_smart(obj: bpy.types.Object):
    """Ensure clean UVs exist on generated meshes."""
    if obj.type != "MESH" or not obj.data:
        return
    if len(obj.data.uv_layers) == 0:
        obj.data.uv_layers.new(name="UVMap")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
    obj.select_set(False)


def add_socket_empty(name: str, loc: tuple[float, float, float] = (0.0, 0.0, 0.0), parent: bpy.types.Object | None = None):
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = 0.01
    empty.location = loc
    bpy.context.scene.collection.objects.link(empty)
    if parent:
        empty.parent = parent
    return empty


def count_scene_geometry() -> tuple[int, int, int, list[float]]:
    verts = 0
    polys = 0
    tris = 0
    min_v = [1e9, 1e9, 1e9]
    max_v = [-1e9, -1e9, -1e9]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and not obj.name.startswith("thumb_"):
            eval_obj = obj.evaluated_get(depsgraph)
            me = eval_obj.to_mesh()
            me.calc_loop_triangles()
            verts += len(me.vertices)
            polys += len(me.polygons)
            tris += len(me.loop_triangles)
            for v in me.vertices:
                wv = obj.matrix_world @ v.co
                for i in range(3):
                    min_v[i] = min(min_v[i], wv[i])
                    max_v[i] = max(max_v[i], wv[i])
            eval_obj.to_mesh_clear()
    dims = [round(max(0.0, max_v[i] - min_v[i]), 4) for i in range(3)] if verts > 0 else [0.0, 0.0, 0.0]
    return verts, polys, tris, dims


def resize_packaged_images(max_res: int = 512):
    """Ensure all images referenced in the current Blender scene are <= max_res."""
    for img in list(bpy.data.images):
        if img.name in ("Render Result", "Viewer Node"):
            continue
        try:
            w, h = img.size[0], img.size[1]
            if w > max_res or h > max_res:
                scale = max_res / max(w, h)
                nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                img.scale(nw, nh)
                out_p = RESIZED_TEX_DIR / f"{Path(img.name).stem}_{nw}.png"
                img.filepath_raw = str(out_p)
                img.file_format = "PNG"
                img.save()
        except Exception as e:
            print(f"Image resize warning for {img.name}: {e}")


def render_asset_thumbnail(asset_id: str, dims: list[float]):
    """Render a clean 256x256 studio thumbnail of the current asset using Workbench/EEVEE or Cycles."""
    scene = bpy.context.scene
    # Calculate bounding center
    min_v = [1e9, 1e9, 1e9]
    max_v = [-1e9, -1e9, -1e9]
    for obj in scene.objects:
        if obj.type == "MESH":
            for corner in obj.bound_box:
                wc = obj.matrix_world @ Vector(corner)
                for i in range(3):
                    min_v[i] = min(min_v[i], wc[i])
                    max_v[i] = max(max_v[i], wc[i])
    center = Vector(((min_v[0] + max_v[0]) * 0.5, (min_v[1] + max_v[1]) * 0.5, (min_v[2] + max_v[2]) * 0.5))
    span = max(max_v[0] - min_v[0], max_v[1] - min_v[1], max_v[2] - min_v[2], 0.012)
    dist = span * 2.15

    cam_data = bpy.data.cameras.new("thumb_cam")
    cam_data.lens = 50.0
    cam_data.clip_start = 0.001
    cam_data.clip_end = 10.0
    cam_obj = bpy.data.objects.new("thumb_cam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = center + Vector((dist * 0.72, -dist * 0.86, dist * 0.58))
    direction = center - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    # Add key and fill lights
    l1_data = bpy.data.lights.new("thumb_key", "AREA")
    l1_data.energy = max(0.5, (dist ** 2) * 35.0)
    l1_data.size = span * 2.0
    l1_data.color = (1.0, 0.97, 0.92)
    l1_obj = bpy.data.objects.new("thumb_key", l1_data)
    scene.collection.objects.link(l1_obj)
    l1_obj.location = center + Vector((dist * 1.1, -dist * 1.0, dist * 1.4))
    l1_obj.rotation_euler = (center - l1_obj.location).to_track_quat("-Z", "Y").to_euler()

    l2_data = bpy.data.lights.new("thumb_fill", "AREA")
    l2_data.energy = max(0.25, (dist ** 2) * 18.0)
    l2_data.size = span * 2.5
    l2_data.color = (0.85, 0.92, 1.0)
    l2_obj = bpy.data.objects.new("thumb_fill", l2_data)
    scene.collection.objects.link(l2_obj)
    l2_obj.location = center + Vector((-dist * 1.2, dist * 0.6, dist * 0.9))
    l2_obj.rotation_euler = (center - l2_obj.location).to_track_quat("-Z", "Y").to_euler()

    world = scene.world or bpy.data.worlds.new("ThumbWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.14, 0.16, 0.20, 1.0)
        bg.inputs["Strength"].default_value = 1.1

    scene.render.engine = "CYCLES"
    cpref = bpy.context.preferences.addons.get("cycles")
    if cpref:
        cpref.preferences.get_devices()
        for dev in cpref.preferences.devices:
            if dev.type in ("OPTIX", "CUDA"):
                dev.use = True
        scene.cycles.device = "GPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.film_transparent = True
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100

    thumb_path = THUMBS_DIR / f"{asset_id}.png"
    scene.render.filepath = str(thumb_path)
    bpy.ops.render.render(write_still=True)
    shutil.copy2(thumb_path, PUBLIC_THUMBS_DIR / f"{asset_id}.png")

    # Remove temporary camera and lights before saving/exporting
    for tmp in (cam_obj, l1_obj, l2_obj):
        bpy.data.objects.remove(tmp, do_unlink=True)


def save_and_export_asset(spec: dict) -> dict:
    """
    1. Resizes textures (<= 512 for small items, <= 1024 for props).
    2. Counts vertices, polygons, triangles, and dimensions.
    3. Saves .blend to assets/source/<id>.blend.
    4. Exports Y-up .glb to assets/web/<id>.glb and web/public/assets/items/<id>.glb.
    5. Renders 256x256 thumbnail to assets/thumbnails/<id>.png and web/public/assets/thumbnails/<id>.png.
    """
    asset_id = spec["id"]
    max_tex = 512 if spec["category"] in ("food", "costume", "water") else 1024
    resize_packaged_images(max_res=max_tex)

    verts, polys, tris, dims = count_scene_geometry()

    blend_path = SOURCE_DIR / f"{asset_id}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    glb_path = WEB_ASSETS_DIR / f"{asset_id}.glb"
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_materials="EXPORT",
    )
    shutil.copy2(glb_path, PUBLIC_ITEMS_DIR / f"{asset_id}.glb")

    # Render thumbnail
    render_asset_thumbnail(asset_id, dims)

    entry = {
        "id": asset_id,
        "name": spec["name"],
        "category": spec["category"],
        "file_path": f"assets/web/{asset_id}.glb",
        "web_url": f"/assets/items/{asset_id}.glb",
        "source_blend": f"assets/source/{asset_id}.blend",
        "thumbnail": f"assets/thumbnails/{asset_id}.png",
        "thumbnail_url": f"/assets/thumbnails/{asset_id}.png",
        "scale": [1.0, 1.0, 1.0],
        "dimensions_m": dims,
        "collision_radius_m": spec.get("collision_radius_m", round(max(dims[0], dims[1]) * 0.5, 4)),
        "pivot": spec["pivot"],
        "attachment_slot": spec.get("attachment_slot"),
        "hamster_safe": spec.get("hamster_safe"),
        "safety_note": spec.get("safety_note"),
        "licence": spec["licence"],
        "author": spec["author"],
        "source": spec["source"],
        "origin_label": spec["origin_label"],  # GENERATED or DOWNLOADED
        "vertices": verts,
        "polygon_count": polys,
        "triangle_count": tris,
        "file_size_bytes": glb_path.stat().st_size,
    }
    print(f"[OK] {asset_id:<24} | {spec['origin_label']:<10} | {tris:>4} tris | {dims} m | {glb_path.stat().st_size:,} B")
    return entry


def import_and_rescale_downloaded(
    filepath: Path,
    target_max_dim: float,
    pivot_mode: str = "base_center",  # "base_center" or "center" or "pickup_bottom"
):
    """Imports a GLB or GLTF file, joins or parents meshes, scales uniformly to target_max_dim, and sets origin."""
    bpy.ops.import_scene.gltf(filepath=str(filepath))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in list(bpy.context.scene.objects):
        if o.type != "MESH":
            # Apply transforms to children before removing empty parents
            pass

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    for o in list(bpy.context.scene.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No meshes imported from {filepath}")

    bpy.context.view_layer.objects.active = meshes[0]
    for m in meshes:
        m.select_set(True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Measure bounds
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)

    cur_span = max(max_x - min_x, max_y - min_y, max_z - min_z, 1e-5)
    s = target_max_dim / cur_span

    cx = (min_x + max_x) * 0.5
    cy = (min_y + max_y) * 0.5
    if pivot_mode == "base_center":
        cz = min_z
    elif pivot_mode == "pickup_bottom":
        cz = min_z + (max_z - min_z) * 0.35
    else:
        cz = (min_z + max_z) * 0.5

    mat = Matrix.Scale(s, 4) @ Matrix.Translation(Vector((-cx, -cy, -cz)))
    obj.data.transform(mat)
    obj.data.update()
    obj.location = (0.0, 0.0, 0.0)
    return obj


# ==============================================================================
# BUILDERS FOR ALL 30 REQUIRED ASSETS (7 FOOD, 2 WATER, 7 COSTUMES, 9 PROPS, 5 DECOR)
# ==============================================================================

def build_food_seed_mix():
    reset_scene()
    rng = random.Random(42)
    mat_sf = make_pbr_mat("mat_sunflower", (0.16, 0.15, 0.14, 1.0), roughness=0.42)
    mat_millet = make_pbr_mat("mat_millet", (0.88, 0.71, 0.25, 1.0), roughness=0.48)
    mat_kibble = make_pbr_mat("mat_kibble", (0.35, 0.42, 0.21, 1.0), roughness=0.75)
    mat_corn = make_pbr_mat("mat_corn", (0.94, 0.68, 0.12, 1.0), roughness=0.40)

    # Central pickupable kibble + cluster of seeds around origin (paw pickup pivot at 0,0,0)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.0028, depth=0.009, location=(0, 0, 0), rotation=(0, math.pi / 2, 0))
    core = bpy.context.active_object
    core.name = "seed_mix_core"
    assign_mat(core, mat_kibble)

    for i in range(6):
        ang = i * (math.tau / 6.0)
        r = 0.0055
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.0032, location=(r * math.cos(ang), r * math.sin(ang), rng.uniform(-0.001, 0.002)))
        s = bpy.context.active_object
        s.scale = (1.4, 0.75, 0.55)
        s.rotation_euler = (0.2, 0.1, ang)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        assign_mat(s, mat_sf if i % 2 == 0 else mat_corn)

    for i in range(8):
        ang = i * (math.tau / 8.0) + 0.3
        r = 0.0035
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.0016, location=(r * math.cos(ang), r * math.sin(ang), 0.002))
        m = bpy.context.active_object
        assign_mat(m, mat_millet)

    add_socket_empty("pickup_pivot", (0.0, 0.0, 0.0))


def build_food_sunflower_seed():
    reset_scene()
    mat_hull = make_pbr_mat("mat_sunflower_hull", (0.15, 0.14, 0.13, 1.0), roughness=0.38)
    mat_stripe = make_pbr_mat("mat_sunflower_stripe", (0.86, 0.84, 0.78, 1.0), roughness=0.42)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=1.0, location=(0, 0, 0))
    seed = bpy.context.active_object
    seed.name = "food_sunflower_seed"
    for v in seed.data.vertices:
        taper = 0.55 if v.co.z > 0 else 0.95
        v.co.x *= 0.0028 * taper
        v.co.y *= 0.0016 * taper
        v.co.z *= 0.0062
    seed.data.update()
    smooth_mesh(seed)
    uv_unwrap_smart(seed)
    seed.data.materials.append(mat_hull)
    seed.data.materials.append(mat_stripe)
    for idx, poly in enumerate(seed.data.polygons):
        poly.material_index = 1 if (idx % 4 == 0) else 0

    add_socket_empty("pickup_pivot", (0.0, 0.0, 0.0))


def build_food_peanut():
    reset_scene()
    mat_peanut = make_pbr_mat("mat_peanut_shell", (0.76, 0.58, 0.36, 1.0), roughness=0.78)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=16, radius=1.0, location=(0, 0, 0))
    p = bpy.context.active_object
    p.name = "food_peanut"
    for v in p.data.vertices:
        z_norm = v.co.z  # -1..1
        # Double-lobed peanut waist pinching at z=0
        waist = 0.72 + 0.32 * (z_norm ** 2)
        rib = 1.0 + 0.05 * math.cos(math.atan2(v.co.y, v.co.x) * 10.0)
        v.co.x *= 0.0046 * waist * rib
        v.co.y *= 0.0044 * waist * rib
        v.co.z *= 0.0110
    p.data.update()
    smooth_mesh(p)
    uv_unwrap_smart(p)
    assign_mat(p, mat_peanut)
    add_socket_empty("pickup_pivot", (0.0, 0.0, 0.0))


def build_food_carrot_piece():
    reset_scene()
    obj = import_and_rescale_downloaded(
        RAW_DIR / "kenney_food-kit" / "Models" / "GLB format" / "carrot.glb",
        target_max_dim=0.022,
        pivot_mode="center",
    )
    obj.name = "food_carrot_piece"
    add_socket_empty("pickup_pivot", (0.0, 0.0, 0.0))


def build_food_broccoli_floret():
    reset_scene()
    obj = import_and_rescale_downloaded(
        RAW_DIR / "kenney_food-kit" / "Models" / "GLB format" / "broccoli.glb",
        target_max_dim=0.019,
        pivot_mode="pickup_bottom",
    )
    obj.name = "food_broccoli_floret"
    add_socket_empty("pickup_pivot", (0.0, 0.0, 0.0))


def build_food_apple_piece():
    """Seedless fresh apple wedge (safe for hamsters; seeds removed)."""
    reset_scene()
    mat_skin = make_pbr_mat("mat_apple_skin_red", (0.78, 0.14, 0.12, 1.0), roughness=0.28)
    mat_flesh = make_pbr_mat("mat_apple_flesh_cream", (0.96, 0.93, 0.78, 1.0), roughness=0.45, subsurface=0.25)

    mesh = bpy.data.meshes.new("food_apple_piece")
    bm = bmesh.new()
    steps = 12
    r_outer = 0.0095
    r_inner = 0.0020
    thick = 0.0065
    arc = math.radians(55.0)

    ring_front = []
    ring_back = []
    for i in range(steps + 1):
        theta = -arc * 0.5 + arc * (i / steps)
        xo = r_outer * math.cos(theta)
        zo = r_outer * math.sin(theta)
        ring_front.append(bm.verts.new((xo, -thick * 0.5, zo)))
        ring_back.append(bm.verts.new((xo, thick * 0.5, zo)))

    v_in_f = bm.verts.new((r_inner, -thick * 0.5, 0.0))
    v_in_b = bm.verts.new((r_inner, thick * 0.5, 0.0))

    skin_faces = []
    for i in range(steps):
        # Flesh sides
        bm.faces.new([v_in_f, ring_front[i + 1], ring_front[i]])
        bm.faces.new([v_in_b, ring_back[i], ring_back[i + 1]])
        # Outer red skin peel
        sf = bm.faces.new([ring_front[i], ring_front[i + 1], ring_back[i + 1], ring_back[i]])
        skin_faces.append(sf)

    bm.faces.new([v_in_f, ring_front[0], ring_back[0], v_in_b])
    bm.faces.new([v_in_b, ring_back[-1], ring_front[-1], v_in_f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    # Center around paw pickup point
    bmesh.ops.translate(bm, vec=Vector((-0.0055, 0.0, 0.0)), verts=bm.verts[:])
    for f in bm.faces:
        f.material_index = 1 if f in skin_faces else 0

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("food_apple_piece", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat_flesh)
    obj.data.materials.append(mat_skin)
    smooth_mesh(obj)
    uv_unwrap_smart(obj)
    add_socket_empty("pickup_pivot", (0.0, 0.0, 0.0))


def build_food_blueberry():
    reset_scene()
    mat_berry = make_pbr_mat("mat_blueberry_indigo", (0.14, 0.17, 0.36, 1.0), roughness=0.36, subsurface=0.15)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=14, radius=0.0052, location=(0, 0, 0))
    berry = bpy.context.active_object
    berry.name = "food_blueberry"
    for v in berry.data.vertices:
        v.co.z *= 0.86
        # Star crown indentation at top
        if v.co.z > 0.0032:
            ang = math.atan2(v.co.y, v.co.x)
            star = 0.0005 * math.cos(ang * 5.0)
            v.co.z -= 0.0006 - star
    berry.data.update()
    smooth_mesh(berry)
    uv_unwrap_smart(berry)
    assign_mat(berry, mat_berry)
    add_socket_empty("pickup_pivot", (0.0, 0.0, 0.0))


def build_water_bottle():
    """
    Wall-mounted / stand water bottle with a separate mesh `water_liquid`
    whose origin is at the bottom of the liquid cylinder so scaling Y (in Three.js)
    or Z (in Blender) scales the water level cleanly between 0.0 and 1.0!
    """
    reset_scene()
    mat_glass = make_pbr_mat("mat_bottle_glass", (0.88, 0.95, 1.0, 0.28), roughness=0.06, transmission=0.88, alpha=0.30)
    mat_water = make_pbr_mat("mat_water_liquid", (0.22, 0.64, 0.96, 0.72), roughness=0.08, transmission=0.75, alpha=0.75)
    mat_cap = make_pbr_mat("mat_bottle_cap", (0.18, 0.42, 0.74, 1.0), roughness=0.35)
    mat_steel = make_pbr_mat("mat_spout_steel", (0.80, 0.82, 0.86, 1.0), roughness=0.18, metallic=0.95)

    # Outer clear body (bottom of bottle body at z = 0.055, height = 0.11)
    bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=0.024, depth=0.11, location=(0, 0, 0.11))
    body = bpy.context.active_object
    body.name = "water_bottle_body"
    smooth_mesh(body)
    uv_unwrap_smart(body)
    assign_mat(body, mat_glass)

    # Separate scalable liquid mesh (`water_liquid`) with origin at bottom of liquid column (z = 0.058)
    liq_h = 0.098
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.0215, depth=liq_h, location=(0, 0, 0))
    liq = bpy.context.active_object
    liq.name = "water_liquid"
    # Shift vertices up by +liq_h/2 so local origin (0,0,0) is at the bottom of the water column!
    liq.data.transform(Matrix.Translation((0.0, 0.0, liq_h * 0.5)))
    liq.data.update()
    liq.location = (0.0, 0.0, 0.058)
    smooth_mesh(liq)
    uv_unwrap_smart(liq)
    assign_mat(liq, mat_water)

    # Blue screw cap at z = 0.048
    bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=0.0255, depth=0.018, location=(0, 0, 0.048))
    cap = bpy.context.active_object
    cap.name = "water_bottle_cap"
    smooth_mesh(cap)
    uv_unwrap_smart(cap)
    assign_mat(cap, mat_cap)

    # Angled stainless steel drinking spout + ball valve tip reaching down to z = 0.015
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16, radius=0.0042, depth=0.045,
        location=(0.0, -0.016, 0.025),
        rotation=(math.radians(42.0), 0.0, 0.0),
    )
    spout = bpy.context.active_object
    spout.name = "water_bottle_spout"
    smooth_mesh(spout)
    uv_unwrap_smart(spout)
    assign_mat(spout, mat_steel)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.0038, location=(0.0, -0.031, 0.009))
    ball = bpy.context.active_object
    ball.name = "water_bottle_ball"
    smooth_mesh(ball)
    assign_mat(ball, mat_steel)


def build_water_bowl():
    """
    Small glazed ceramic water bowl (0.068 m diam, 0.026 m tall) with separate
    scalable `water_liquid` mesh inside.
    """
    reset_scene()
    mat_ceramic = make_pbr_mat("mat_water_bowl_ceramic", (0.78, 0.88, 0.94, 1.0), roughness=0.18)
    mat_water = make_pbr_mat("mat_water_liquid", (0.22, 0.65, 0.96, 0.76), roughness=0.06, transmission=0.80, alpha=0.76)

    mesh = bpy.data.meshes.new("water_bowl_body")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32, radius1=0.029, radius2=0.034, depth=0.026)
    for f in list(bm.faces):
        if f.normal.z > 0.9:
            bmesh.ops.delete(bm, geom=[f], context="FACES")
    bmesh.ops.translate(bm, vec=Vector((0, 0, 0.013)), verts=bm.verts[:])
    bm.to_mesh(mesh)
    bm.free()

    bowl = bpy.data.objects.new("water_bowl_body", mesh)
    bpy.context.scene.collection.objects.link(bowl)
    solid = bowl.modifiers.new("Solidify", "SOLIDIFY")
    solid.thickness = 0.0045
    solid.offset = -1.0
    bpy.context.view_layer.objects.active = bowl
    bpy.ops.object.modifier_apply(modifier=solid.name)
    smooth_mesh(bowl)
    uv_unwrap_smart(bowl)
    assign_mat(bowl, mat_ceramic)

    # Separate water_liquid cylinder with origin at inner floor z = 0.0045
    liq_h = 0.018
    bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=0.028, depth=liq_h, location=(0, 0, 0))
    liq = bpy.context.active_object
    liq.name = "water_liquid"
    liq.data.transform(Matrix.Translation((0.0, 0.0, liq_h * 0.5)))
    liq.data.update()
    liq.location = (0.0, 0.0, 0.0045)
    smooth_mesh(liq)
    uv_unwrap_smart(liq)
    assign_mat(liq, mat_water)


# ==============================================================================
# COSTUMES (Origin at attachment point + named empty socket head_slot/neck_slot/back_slot)
# ==============================================================================

def build_costume_party_hat():
    reset_scene()
    mat_cone = make_pbr_mat("mat_party_cone", (0.92, 0.24, 0.48, 1.0), roughness=0.45)
    mat_pom = make_pbr_mat("mat_party_gold", (0.98, 0.82, 0.18, 1.0), roughness=0.55)

    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.013, radius2=0.001, depth=0.034, location=(0, 0, 0.017))
    cone = bpy.context.active_object
    cone.name = "costume_party_hat_cone"
    smooth_mesh(cone)
    uv_unwrap_smart(cone)
    assign_mat(cone, mat_cone)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=14, ring_count=10, radius=0.0045, location=(0, 0, 0.035))
    pom = bpy.context.active_object
    pom.name = "costume_party_hat_pom"
    smooth_mesh(pom)
    assign_mat(pom, mat_pom)

    bpy.ops.mesh.primitive_torus_add(major_radius=0.013, minor_radius=0.0018, major_segments=24, minor_segments=8, location=(0, 0, 0.0015))
    trim = bpy.context.active_object
    trim.name = "costume_party_hat_trim"
    smooth_mesh(trim)
    assign_mat(trim, mat_pom)

    add_socket_empty("head_slot", (0.0, 0.0, 0.0))


def build_costume_top_hat():
    reset_scene()
    mat_felt = make_pbr_mat("mat_tophat_felt", (0.10, 0.10, 0.12, 1.0), roughness=0.65)
    mat_ribbon = make_pbr_mat("mat_tophat_ribbon", (0.78, 0.14, 0.18, 1.0), roughness=0.35)

    # Brim at z = 0.0015
    bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=0.017, depth=0.0025, location=(0, 0, 0.0012))
    brim = bpy.context.active_object
    brim.name = "costume_top_hat_brim"
    smooth_mesh(brim)
    uv_unwrap_smart(brim)
    assign_mat(brim, mat_felt)

    # Crown cylinder
    bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=0.0115, depth=0.024, location=(0, 0, 0.014))
    crown = bpy.context.active_object
    crown.name = "costume_top_hat_crown"
    smooth_mesh(crown)
    uv_unwrap_smart(crown)
    assign_mat(crown, mat_felt)

    # Red satin band
    bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=0.0119, depth=0.0045, location=(0, 0, 0.005))
    band = bpy.context.active_object
    band.name = "costume_top_hat_band"
    smooth_mesh(band)
    assign_mat(band, mat_ribbon)

    add_socket_empty("head_slot", (0.0, 0.0, 0.0))


def build_costume_bow_tie():
    reset_scene()
    mat_silk = make_pbr_mat("mat_bowtie_crimson", (0.82, 0.12, 0.18, 1.0), roughness=0.38)

    # Center knot at origin (0,0,0) = neck_slot
    bpy.ops.mesh.primitive_uv_sphere_add(segments=14, ring_count=10, radius=0.0038, location=(0, 0, 0))
    knot = bpy.context.active_object
    knot.name = "costume_bow_tie_knot"
    knot.scale = (0.85, 0.75, 0.95)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    smooth_mesh(knot)
    assign_mat(knot, mat_silk)

    for side, sgn in (("L", -1.0), ("R", 1.0)):
        bpy.ops.mesh.primitive_cone_add(
            vertices=16, radius1=0.0068, radius2=0.0022, depth=0.012,
            location=(sgn * 0.0075, 0.0, 0.0),
            rotation=(0.0, -sgn * math.pi * 0.5, 0.0),
        )
        wing = bpy.context.active_object
        wing.name = f"costume_bow_tie_wing_{side}"
        wing.scale = (1.0, 0.45, 1.0)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        smooth_mesh(wing)
        uv_unwrap_smart(wing)
        assign_mat(wing, mat_silk)

    add_socket_empty("neck_slot", (0.0, 0.0, 0.0))


def build_costume_scarf():
    reset_scene()
    mat_knit = make_pbr_mat("mat_scarf_teal", (0.16, 0.58, 0.64, 1.0), roughness=0.78)
    mat_stripe = make_pbr_mat("mat_scarf_cream", (0.95, 0.91, 0.82, 1.0), roughness=0.75)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.020, minor_radius=0.0052,
        major_segments=28, minor_segments=12,
        location=(0, 0, 0),
    )
    ring = bpy.context.active_object
    ring.name = "costume_scarf_ring"
    smooth_mesh(ring)
    uv_unwrap_smart(ring)
    assign_mat(ring, mat_knit)

    # Hanging scarf tail in front (-Y in Blender -> +Z in glTF)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.008, -0.021, -0.010), rotation=(math.radians(20.0), 0, math.radians(-12.0)))
    tail = bpy.context.active_object
    tail.name = "costume_scarf_tail"
    tail.scale = (0.009, 0.0035, 0.018)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bev = tail.modifiers.new("Bevel", "BEVEL")
    bev.width = 0.0012
    bev.segments = 2
    bpy.context.view_layer.objects.active = tail
    bpy.ops.object.modifier_apply(modifier=bev.name)
    smooth_mesh(tail)
    uv_unwrap_smart(tail)
    assign_mat(tail, mat_stripe)

    add_socket_empty("neck_slot", (0.0, 0.0, 0.0))


def build_costume_crown():
    reset_scene()
    mat_gold = make_pbr_mat("mat_crown_gold", (0.98, 0.78, 0.18, 1.0), roughness=0.22, metallic=0.92)
    mat_gem = make_pbr_mat("mat_crown_ruby", (0.88, 0.12, 0.22, 1.0), roughness=0.12)

    mesh = bpy.data.meshes.new("costume_crown")
    bm = bmesh.new()
    segs = 20
    r_base = 0.012
    r_top = 0.0135
    h_base = 0.007
    h_peak = 0.016

    bot_ring = []
    top_ring = []
    for i in range(segs):
        theta = math.tau * (i / segs)
        bot_ring.append(bm.verts.new((r_base * math.cos(theta), r_base * math.sin(theta), 0.0)))
        is_peak = (i % 4 == 0)
        zt = h_peak if is_peak else h_base
        rt = r_top if is_peak else r_base * 1.03
        top_ring.append(bm.verts.new((rt * math.cos(theta), rt * math.sin(theta), zt)))

    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new([bot_ring[i], bot_ring[j], top_ring[j], top_ring[i]])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()

    crown = bpy.data.objects.new("costume_crown", mesh)
    bpy.context.scene.collection.objects.link(crown)
    solid = crown.modifiers.new("Solidify", "SOLIDIFY")
    solid.thickness = 0.0018
    bpy.context.view_layer.objects.active = crown
    bpy.ops.object.modifier_apply(modifier=solid.name)
    smooth_mesh(crown)
    uv_unwrap_smart(crown)
    assign_mat(crown, mat_gold)

    # 5 ruby gems on the peaks
    for k in range(5):
        theta = math.tau * (k / 5.0)
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=10, ring_count=8, radius=0.0018,
            location=(r_top * math.cos(theta), r_top * math.sin(theta), h_peak),
        )
        gem = bpy.context.active_object
        gem.name = f"costume_crown_gem_{k}"
        smooth_mesh(gem)
        assign_mat(gem, mat_gem)

    add_socket_empty("head_slot", (0.0, 0.0, 0.0))


def build_costume_tiny_glasses():
    reset_scene()
    mat_frame = make_pbr_mat("mat_glasses_brass", (0.85, 0.68, 0.28, 1.0), roughness=0.25, metallic=0.88)

    # Twin round wire rims spaced for hamster eyes (~0.026 m apart)
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        bpy.ops.mesh.primitive_torus_add(
            major_radius=0.0068, minor_radius=0.0011,
            major_segments=24, minor_segments=8,
            location=(sgn * 0.011, -0.006, 0.0),
            rotation=(math.pi * 0.5, 0.0, 0.0),
        )
        rim = bpy.context.active_object
        rim.name = f"costume_glasses_rim_{side}"
        smooth_mesh(rim)
        assign_mat(rim, mat_frame)

        # Temple arm going back towards ears (+Y)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=10, radius=0.0009, depth=0.018,
            location=(sgn * 0.017, 0.003, 0.0),
            rotation=(math.pi * 0.5, 0.0, 0.0),
        )
        arm = bpy.context.active_object
        arm.name = f"costume_glasses_arm_{side}"
        smooth_mesh(arm)
        assign_mat(arm, mat_frame)

    # Nose bridge
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=10, radius=0.0009, depth=0.009,
        location=(0.0, -0.006, 0.001),
        rotation=(0.0, math.pi * 0.5, 0.0),
    )
    bridge = bpy.context.active_object
    bridge.name = "costume_glasses_bridge"
    smooth_mesh(bridge)
    assign_mat(bridge, mat_frame)

    add_socket_empty("head_slot", (0.0, 0.0, 0.0))


def build_costume_backpack():
    """Back-slot explorer saddlebag/cape so head_slot, neck_slot, and back_slot are all represented."""
    reset_scene()
    mat_canvas = make_pbr_mat("mat_backpack_canvas", (0.72, 0.46, 0.24, 1.0), roughness=0.72)
    mat_flap = make_pbr_mat("mat_backpack_flap", (0.38, 0.24, 0.14, 1.0), roughness=0.62)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.009))
    pack = bpy.context.active_object
    pack.name = "costume_backpack_body"
    pack.scale = (0.024, 0.028, 0.016)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bev = pack.modifiers.new("Bevel", "BEVEL")
    bev.width = 0.003
    bev.segments = 3
    bpy.context.view_layer.objects.active = pack
    bpy.ops.object.modifier_apply(modifier=bev.name)
    smooth_mesh(pack)
    uv_unwrap_smart(pack)
    assign_mat(pack, mat_canvas)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.017))
    flap = bpy.context.active_object
    flap.name = "costume_backpack_flap"
    flap.scale = (0.025, 0.029, 0.004)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    smooth_mesh(flap)
    assign_mat(flap, mat_flap)

    add_socket_empty("back_slot", (0.0, 0.0, 0.0))


# ==============================================================================
# PROPS (Base-center pivot Z=0, < 5,000 tris)
# ==============================================================================

def build_prop_food_bowl():
    reset_scene()
    obj = import_and_rescale_downloaded(
        RAW_DIR / "kenney_food-kit" / "Models" / "GLB format" / "bowl.glb",
        target_max_dim=0.082,
        pivot_mode="base_center",
    )
    obj.name = "prop_food_bowl"


def build_prop_shelf():
    reset_scene()
    obj = import_and_rescale_downloaded(
        RAW_DIR / "KayKit_Dungeon_Pack_1.1_FREE" / "KayKit_Dungeon_Pack_1.1_FREE" / "Assets" / "gltf" / "shelf_small.gltf",
        target_max_dim=0.180,
        pivot_mode="base_center",
    )
    obj.name = "prop_shelf"


def build_prop_wheel():
    """Standalone 0.28 m Syrian exercise wheel on wooden stand with inner grip rungs (base-center pivot at Z=0)."""
    reset_scene()
    mat_wood = make_pbr_mat("mat_wheel_plywood", (0.78, 0.62, 0.43, 1.0), roughness=0.55)
    mat_rung = make_pbr_mat("mat_wheel_rung", (0.62, 0.46, 0.29, 1.0), roughness=0.62)
    mat_steel = make_pbr_mat("mat_wheel_axle_steel", (0.76, 0.78, 0.82, 1.0), roughness=0.22, metallic=0.92)

    wheel_r = 0.14
    wheel_w = 0.09
    hub_z = wheel_r + 0.024  # 0.164 m above base

    # Base stand plate resting at Z = 0
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.006))
    stand = bpy.context.active_object
    stand.name = "prop_wheel_stand"
    stand.scale = (0.18, 0.13, 0.012)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_mat(stand, mat_wood)

    # Vertical support arm at back (+Y)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.054, hub_z * 0.5 + 0.006))
    arm = bpy.context.active_object
    arm.name = "prop_wheel_arm"
    arm.scale = (0.028, 0.016, hub_z)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_mat(arm, mat_wood)

    # Steel axle
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=20, radius=0.018, depth=wheel_w + 0.02,
        location=(0.0, 0.008, hub_z),
        rotation=(math.pi * 0.5, 0.0, 0.0),
    )
    axle = bpy.context.active_object
    axle.name = "prop_wheel_axle"
    smooth_mesh(axle)
    assign_mat(axle, mat_steel)

    # Open-front hollow drum
    mesh = bpy.data.meshes.new("prop_wheel_drum")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=48, radius1=wheel_r, radius2=wheel_r, depth=wheel_w)
    for f in list(bm.faces):
        if f.normal.z > 0.9:
            bmesh.ops.delete(bm, geom=[f], context="FACES")
    bm.to_mesh(mesh)
    bm.free()

    drum = bpy.data.objects.new("prop_wheel_drum", mesh)
    drum.location = (0.0, 0.0, hub_z)
    drum.rotation_euler = (math.pi * 0.5, 0.0, 0.0)
    bpy.context.scene.collection.objects.link(drum)
    solid = drum.modifiers.new("Solidify", "SOLIDIFY")
    solid.thickness = 0.005
    solid.offset = -1.0
    bpy.context.view_layer.objects.active = drum
    bpy.ops.object.modifier_apply(modifier=solid.name)
    smooth_mesh(drum)
    uv_unwrap_smart(drum)
    assign_mat(drum, mat_wood)

    # 12 inner grip rungs so rotation is clearly visible
    for i in range(12):
        ang = math.tau * (i / 12.0)
        rx = (wheel_r - 0.006) * math.cos(ang)
        rz = hub_z + (wheel_r - 0.006) * math.sin(ang)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=8, radius=0.0025, depth=wheel_w * 0.86,
            location=(rx, 0.0, rz),
            rotation=(math.pi * 0.5, 0.0, 0.0),
        )
        rung = bpy.context.active_object
        rung.name = f"prop_wheel_rung_{i:02d}"
        rung.parent = drum
        rung.matrix_parent_inverse = drum.matrix_world.inverted()
        assign_mat(rung, mat_rung)


def build_prop_tunnel_straight():
    reset_scene()
    mat_bark = make_pbr_mat("mat_tunnel_bark", (0.48, 0.35, 0.22, 1.0), roughness=0.82)
    r = 0.038
    length = 0.16

    mesh = bpy.data.meshes.new("prop_tunnel_straight")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=28, radius1=r, radius2=r, depth=length)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("prop_tunnel_straight", mesh)
    obj.location = (0.0, 0.0, r + 0.004)
    obj.rotation_euler = (math.pi * 0.5, 0.0, 0.0)
    bpy.context.scene.collection.objects.link(obj)
    solid = obj.modifiers.new("Solidify", "SOLIDIFY")
    solid.thickness = 0.0045
    solid.offset = 1.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=solid.name)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    smooth_mesh(obj)
    uv_unwrap_smart(obj)
    assign_mat(obj, mat_bark)


def build_prop_tunnel_curved():
    reset_scene()
    mat_bark = make_pbr_mat("mat_tunnel_curved_bark", (0.48, 0.35, 0.22, 1.0), roughness=0.82)
    major_r = 0.08
    minor_r = 0.038

    mesh = bpy.data.meshes.new("prop_tunnel_curved")
    bm = bmesh.new()
    major_steps = 16
    minor_steps = 24
    rings = []
    for i in range(major_steps + 1):
        phi = (math.pi * 0.5) * (i / major_steps)
        ring = []
        for j in range(minor_steps):
            theta = math.tau * (j / minor_steps)
            r_curr = major_r + minor_r * math.cos(theta)
            x = r_curr * math.cos(phi) - major_r * 0.5
            y = r_curr * math.sin(phi) - major_r * 0.5
            z = minor_r * math.sin(theta) + minor_r + 0.004
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)

    for i in range(major_steps):
        for j in range(minor_steps):
            jn = (j + 1) % minor_steps
            bm.faces.new([rings[i][j], rings[i + 1][j], rings[i + 1][jn], rings[i][jn]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("prop_tunnel_curved", mesh)
    bpy.context.scene.collection.objects.link(obj)
    solid = obj.modifiers.new("Solidify", "SOLIDIFY")
    solid.thickness = 0.0045
    solid.offset = 1.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=solid.name)
    smooth_mesh(obj)
    uv_unwrap_smart(obj)
    assign_mat(obj, mat_bark)


def build_prop_hideout():
    reset_scene()
    mat_wood = make_pbr_mat("mat_hideout_wood", (0.64, 0.47, 0.30, 1.0), roughness=0.65)
    mat_roof = make_pbr_mat("mat_hideout_roof", (0.48, 0.33, 0.20, 1.0), roughness=0.68)

    hw, hd, hh = 0.16, 0.13, 0.105
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, hh * 0.5))
    cabin = bpy.context.active_object
    cabin.name = "prop_hideout_body"
    cabin.scale = (hw, hd, hh)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # Carve arched doorway
    door_w, door_h = 0.062, 0.068
    bpy.ops.mesh.primitive_cylinder_add(
        radius=door_w * 0.5, depth=hd * 1.5, vertices=20,
        location=(0.0, 0.0, door_h - door_w * 0.5),
        rotation=(math.pi * 0.5, 0.0, 0.0),
    )
    arch_top = bpy.context.active_object

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, (door_h - door_w * 0.5) * 0.5))
    arch_bot = bpy.context.active_object
    arch_bot.scale = (door_w, hd * 1.5, door_h - door_w * 0.5)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    for cutter in (arch_top, arch_bot):
        bool_mod = cabin.modifiers.new("DoorCut", "BOOLEAN")
        bool_mod.operation = "DIFFERENCE"
        bool_mod.object = cutter
        bpy.context.view_layer.objects.active = cabin
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)

    smooth_mesh(cabin)
    uv_unwrap_smart(cabin)
    assign_mat(cabin, mat_wood)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, hh + 0.007))
    roof = bpy.context.active_object
    roof.name = "prop_hideout_roof"
    roof.scale = (hw + 0.022, hd + 0.022, 0.014)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    smooth_mesh(roof)
    uv_unwrap_smart(roof)
    assign_mat(roof, mat_roof)


def build_prop_bridge_ramp():
    """Arched bendy log bridge / climbing ramp (11 tied wooden dowel logs, 0.18 m x 0.09 m)."""
    reset_scene()
    mat_log = make_pbr_mat("mat_bridge_log", (0.58, 0.42, 0.26, 1.0), roughness=0.78)
    mat_end = make_pbr_mat("mat_bridge_cut", (0.82, 0.68, 0.48, 1.0), roughness=0.65)

    n_logs = 11
    span_x = 0.17
    width_y = 0.09
    log_r = 0.0078
    arch_h = 0.042

    for i in range(n_logs):
        t = (i / (n_logs - 1)) - 0.5  # -0.5 .. +0.5
        x = t * span_x
        z = log_r + arch_h * math.cos(t * math.pi)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=14, radius=log_r, depth=width_y,
            location=(x, 0.0, z),
            rotation=(math.pi * 0.5, 0.0, 0.0),
        )
        log = bpy.context.active_object
        log.name = f"prop_bridge_log_{i:02d}"
        smooth_mesh(log)
        log.data.materials.append(mat_log)
        log.data.materials.append(mat_end)
        for poly in log.data.polygons:
            if abs(poly.normal.z) > 0.8:
                poly.material_index = 1


def build_prop_chew_toy():
    """Applewood dumbbell chew toy with gnawed middle section (0.075 m long, base-center pivot Z=0)."""
    reset_scene()
    mat_wood = make_pbr_mat("mat_chew_applewood", (0.68, 0.50, 0.32, 1.0), roughness=0.72)
    mat_bark = make_pbr_mat("mat_chew_end_bark", (0.42, 0.29, 0.18, 1.0), roughness=0.84)

    end_r = 0.014
    # Center bar
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16, radius=0.0065, depth=0.068,
        location=(0.0, 0.0, end_r),
        rotation=(0.0, math.pi * 0.5, 0.0),
    )
    bar = bpy.context.active_object
    bar.name = "prop_chew_bar"
    smooth_mesh(bar)
    uv_unwrap_smart(bar)
    assign_mat(bar, mat_wood)

    # Two wooden roller ends resting at Z=0
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=20, radius=end_r, depth=0.014,
            location=(sgn * 0.028, 0.0, end_r),
            rotation=(0.0, math.pi * 0.5, 0.0),
        )
        wheel = bpy.context.active_object
        wheel.name = f"prop_chew_end_{side}"
        smooth_mesh(wheel)
        uv_unwrap_smart(wheel)
        assign_mat(wheel, mat_bark)


def build_prop_small_ball():
    """Woven willow/rattan play ball (0.044 m diameter, resting at Z=0)."""
    reset_scene()
    mat_rattan = make_pbr_mat("mat_willow_ball", (0.74, 0.56, 0.34, 1.0), roughness=0.75)
    r = 0.022
    rotations = [
        (0.0, 0.0, 0.0),
        (math.pi * 0.5, 0.0, 0.0),
        (0.0, math.pi * 0.5, 0.0),
        (math.pi * 0.25, math.pi * 0.25, 0.0),
        (-math.pi * 0.25, math.pi * 0.25, 0.0),
        (math.pi * 0.25, -math.pi * 0.25, math.pi * 0.25),
    ]
    for idx, rot in enumerate(rotations):
        bpy.ops.mesh.primitive_torus_add(
            major_radius=r - 0.002, minor_radius=0.0022,
            major_segments=24, minor_segments=8,
            location=(0.0, 0.0, r),
            rotation=rot,
        )
        band = bpy.context.active_object
        band.name = f"prop_small_ball_band_{idx}"
        smooth_mesh(band)
        assign_mat(band, mat_rattan)


# ==============================================================================
# DECOR (Base-center pivot Z=0, < 2,000 tris)
# ==============================================================================

def build_decor_plant():
    """Hamster-safe potted spider plant in miniature terracotta pot (0.078 m tall)."""
    reset_scene()
    mat_pot = make_pbr_mat("mat_terracotta", (0.76, 0.38, 0.24, 1.0), roughness=0.72)
    mat_soil = make_pbr_mat("mat_potting_soil", (0.24, 0.18, 0.13, 1.0), roughness=0.92)
    mat_leaf = make_pbr_mat("mat_spider_leaf", (0.24, 0.62, 0.26, 1.0), roughness=0.45, subsurface=0.2)

    bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=0.016, radius2=0.022, depth=0.034, location=(0, 0, 0.017))
    pot = bpy.context.active_object
    pot.name = "decor_plant_pot"
    smooth_mesh(pot)
    uv_unwrap_smart(pot)
    assign_mat(pot, mat_pot)

    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.020, depth=0.004, location=(0, 0, 0.033))
    soil = bpy.context.active_object
    soil.name = "decor_plant_soil"
    assign_mat(soil, mat_soil)

    # 8 arching leaves
    for i in range(8):
        ang = math.tau * (i / 8.0)
        mesh = bpy.data.meshes.new(f"leaf_{i}")
        bm = bmesh.new()
        segs = 5
        verts_l = []
        verts_r = []
        for s in range(segs + 1):
            t = s / segs
            r_out = 0.003 + t * 0.036
            z_up = 0.034 + math.sin(t * math.pi * 0.78) * 0.035 - (t ** 2) * 0.012
            w = 0.0048 * math.sin(t * math.pi * 0.85 + 0.15)
            c_dir = Vector((math.cos(ang), math.sin(ang), 0.0))
            p_dir = Vector((-math.sin(ang), math.cos(ang), 0.0))
            pt = c_dir * r_out + Vector((0, 0, z_up))
            verts_l.append(bm.verts.new(pt - p_dir * w))
            verts_r.append(bm.verts.new(pt + p_dir * w))
        for s in range(segs):
            bm.faces.new([verts_l[s], verts_r[s], verts_r[s + 1], verts_l[s + 1]])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(mesh)
        bm.free()
        leaf = bpy.data.objects.new(f"decor_plant_leaf_{i}", mesh)
        bpy.context.scene.collection.objects.link(leaf)
        smooth_mesh(leaf)
        assign_mat(leaf, mat_leaf)


def build_decor_wooden_item():
    reset_scene()
    obj = import_and_rescale_downloaded(
        RAW_DIR / "KayKit_Dungeon_Pack_1.1_FREE" / "KayKit_Dungeon_Pack_1.1_FREE" / "Assets" / "gltf" / "barrel_small.gltf",
        target_max_dim=0.062,
        pivot_mode="base_center",
    )
    obj.name = "decor_wooden_item"


def build_decor_bedding_patch():
    """Soft mounded aspen & forest-moss bedding patch (0.13 m x 0.11 m x 0.018 m)."""
    reset_scene()
    mat_patch = make_pbr_mat("mat_bedding_patch_moss", (0.48, 0.58, 0.34, 1.0), roughness=0.88, subsurface=0.15)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.062, location=(0, 0, 0))
    patch = bpy.context.active_object
    patch.name = "decor_bedding_patch"
    rng = random.Random(77)
    for v in patch.data.vertices:
        if v.co.z < 0:
            v.co.z = 0.0
        else:
            v.co.z *= 0.28 + rng.uniform(-0.03, 0.04)
        v.co.x *= 1.08 + rng.uniform(-0.04, 0.04)
        v.co.y *= 0.88 + rng.uniform(-0.04, 0.04)
    patch.data.update()
    smooth_mesh(patch)
    uv_unwrap_smart(patch)
    assign_mat(patch, mat_patch)


def build_decor_flag():
    reset_scene()
    obj = import_and_rescale_downloaded(
        RAW_DIR / "KayKit_Dungeon_Pack_1.1_FREE" / "KayKit_Dungeon_Pack_1.1_FREE" / "Assets" / "gltf" / "banner_blue.gltf",
        target_max_dim=0.115,
        pivot_mode="base_center",
    )
    obj.name = "decor_flag"


def build_decor_picture_frame():
    """Mini wooden tabletop picture frame (0.072 m x 0.058 m) with easel stand and golden hamster portrait."""
    reset_scene()
    mat_frame = make_pbr_mat("mat_frame_walnut", (0.38, 0.25, 0.15, 1.0), roughness=0.52)
    mat_canvas = make_pbr_mat("mat_frame_portrait", (0.92, 0.78, 0.54, 1.0), roughness=0.35)

    fw, fh, fd = 0.068, 0.054, 0.006
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, fh * 0.5))
    frame = bpy.context.active_object
    frame.name = "decor_picture_frame_border"
    frame.scale = (fw, fd, fh)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_mat(frame, mat_frame)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, -0.001, fh * 0.5))
    art = bpy.context.active_object
    art.name = "decor_picture_frame_canvas"
    art.scale = (fw - 0.012, fd, fh - 0.012)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_mat(art, mat_canvas)

    # Back easel kickstand resting at Z=0
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.014, fh * 0.35), rotation=(math.radians(24.0), 0, 0))
    stand = bpy.context.active_object
    stand.name = "decor_picture_frame_stand"
    stand.scale = (0.014, 0.004, fh * 0.72)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    assign_mat(stand, mat_frame)


ASSET_SPECS = [
    # 1. FOODS (7 items — hamster_safe=True, pickup_pivot at paw hold point)
    {
        "id": "food_seed_mix",
        "name": "Hamster Seed & Pellet Mix",
        "category": "food",
        "pivot": "pickup_pivot",
        "attachment_slot": "paw_hold",
        "hamster_safe": True,
        "safety_note": "Balanced Syrian hamster seed mix (sunflower seeds, millet, extruded kibble, corn).",
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/food_seed_mix.blend)",
        "origin_label": "GENERATED",
        "builder": build_food_seed_mix,
    },
    {
        "id": "food_sunflower_seed",
        "name": "Striped Sunflower Seed",
        "category": "food",
        "pivot": "pickup_pivot",
        "attachment_slot": "paw_hold",
        "hamster_safe": True,
        "safety_note": "Safe high-energy Syrian hamster treat in moderation.",
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/food_sunflower_seed.blend)",
        "origin_label": "GENERATED",
        "builder": build_food_sunflower_seed,
    },
    {
        "id": "food_peanut",
        "name": "Unsalted Peanut",
        "category": "food",
        "pivot": "pickup_pivot",
        "attachment_slot": "paw_hold",
        "hamster_safe": True,
        "safety_note": "Dry unsalted whole/shelled peanut (safe; avoids sticky peanut-butter pouch impaction).",
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/food_peanut.blend)",
        "origin_label": "GENERATED",
        "builder": build_food_peanut,
    },
    {
        "id": "food_carrot_piece",
        "name": "Fresh Carrot Piece",
        "category": "food",
        "pivot": "pickup_pivot",
        "attachment_slot": "paw_hold",
        "hamster_safe": True,
        "safety_note": "Bite-sized raw carrot piece (safe root vegetable in moderation).",
        "licence": "CC0 1.0 Universal",
        "author": "Kenney (www.kenney.nl)",
        "source": "https://kenney.nl/assets/food-kit (carrot.glb rescaled to 0.022m)",
        "origin_label": "DOWNLOADED",
        "builder": build_food_carrot_piece,
    },
    {
        "id": "food_broccoli_floret",
        "name": "Broccoli Floret",
        "category": "food",
        "pivot": "pickup_pivot",
        "attachment_slot": "paw_hold",
        "hamster_safe": True,
        "safety_note": "Raw broccoli floret (excellent low-sugar vitamin-rich vegetable for Syrian hamsters).",
        "licence": "CC0 1.0 Universal",
        "author": "Kenney (www.kenney.nl)",
        "source": "https://kenney.nl/assets/food-kit (broccoli.glb rescaled to 0.019m)",
        "origin_label": "DOWNLOADED",
        "builder": build_food_broccoli_floret,
    },
    {
        "id": "food_apple_piece",
        "name": "Seedless Apple Piece",
        "category": "food",
        "pivot": "pickup_pivot",
        "attachment_slot": "paw_hold",
        "hamster_safe": True,
        "safety_note": "Fresh apple slice with core and cyanogenic seeds completely removed.",
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/food_apple_piece.blend)",
        "origin_label": "GENERATED",
        "builder": build_food_apple_piece,
    },
    {
        "id": "food_blueberry",
        "name": "Fresh Blueberry",
        "category": "food",
        "pivot": "pickup_pivot",
        "attachment_slot": "paw_hold",
        "hamster_safe": True,
        "safety_note": "Antioxidant-rich fresh blueberry treat (safe in moderation).",
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/food_blueberry.blend)",
        "origin_label": "GENERATED",
        "builder": build_food_blueberry,
    },
    # 2. WATER (2 items — separate scalable `water_liquid` mesh)
    {
        "id": "water_bottle",
        "name": "Ball-Spout Water Bottle",
        "category": "water",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": True,
        "safety_note": "Includes separate water_liquid mesh for dynamic 0..1 level scaling.",
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/water_bottle.blend)",
        "origin_label": "GENERATED",
        "builder": build_water_bottle,
    },
    {
        "id": "water_bowl",
        "name": "Ceramic Water Dish",
        "category": "water",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": True,
        "safety_note": "Includes separate water_liquid mesh for dynamic 0..1 level scaling.",
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/water_bowl.blend)",
        "origin_label": "GENERATED",
        "builder": build_water_bowl,
    },
    # 3. COSTUMES (7 items — head_slot, neck_slot, back_slot)
    {
        "id": "costume_party_hat",
        "name": "Festive Party Hat",
        "category": "costume",
        "pivot": "head_slot",
        "attachment_slot": "head_slot",
        "hamster_safe": None,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/costume_party_hat.blend)",
        "origin_label": "GENERATED",
        "builder": build_costume_party_hat,
    },
    {
        "id": "costume_top_hat",
        "name": "Dapper Top Hat",
        "category": "costume",
        "pivot": "head_slot",
        "attachment_slot": "head_slot",
        "hamster_safe": None,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/costume_top_hat.blend)",
        "origin_label": "GENERATED",
        "builder": build_costume_top_hat,
    },
    {
        "id": "costume_bow_tie",
        "name": "Crimson Silk Bow Tie",
        "category": "costume",
        "pivot": "neck_slot",
        "attachment_slot": "neck_slot",
        "hamster_safe": None,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/costume_bow_tie.blend)",
        "origin_label": "GENERATED",
        "builder": build_costume_bow_tie,
    },
    {
        "id": "costume_scarf",
        "name": "Cozy Knit Winter Scarf",
        "category": "costume",
        "pivot": "neck_slot",
        "attachment_slot": "neck_slot",
        "hamster_safe": None,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/costume_scarf.blend)",
        "origin_label": "GENERATED",
        "builder": build_costume_scarf,
    },
    {
        "id": "costume_crown",
        "name": "Golden Royal Crown",
        "category": "costume",
        "pivot": "head_slot",
        "attachment_slot": "head_slot",
        "hamster_safe": None,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/costume_crown.blend)",
        "origin_label": "GENERATED",
        "builder": build_costume_crown,
    },
    {
        "id": "costume_tiny_glasses",
        "name": "Tiny Brass Spectacles",
        "category": "costume",
        "pivot": "head_slot",
        "attachment_slot": "head_slot",
        "hamster_safe": None,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/costume_tiny_glasses.blend)",
        "origin_label": "GENERATED",
        "builder": build_costume_tiny_glasses,
    },
    {
        "id": "costume_backpack",
        "name": "Explorer Saddle Pack",
        "category": "costume",
        "pivot": "back_slot",
        "attachment_slot": "back_slot",
        "hamster_safe": None,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/costume_backpack.blend)",
        "origin_label": "GENERATED",
        "builder": build_costume_backpack,
    },
    # 4. PROPS (9 items — food bowl, shelf, wheel, straight tunnel, curved tunnel, hideout, bridge/ramp, chew toy, small ball)
    {
        "id": "prop_food_bowl",
        "name": "Ceramic Food Bowl",
        "category": "prop",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.042,
        "licence": "CC0 1.0 Universal",
        "author": "Kenney (www.kenney.nl)",
        "source": "https://kenney.nl/assets/food-kit (bowl.glb rescaled to 0.082m)",
        "origin_label": "DOWNLOADED",
        "builder": build_prop_food_bowl,
    },
    {
        "id": "prop_shelf",
        "name": "Wooden Lookout & Food Shelf",
        "category": "prop",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.065,
        "licence": "CC0 1.0 Universal",
        "author": "Kay Lousberg (www.kaylousberg.com)",
        "source": "https://kaylousberg.itch.io/kaykit-dungeon (shelf_small.gltf rescaled to 0.18m)",
        "origin_label": "DOWNLOADED",
        "builder": build_prop_shelf,
    },
    {
        "id": "prop_wheel",
        "name": "28 cm Wooden Exercise Wheel",
        "category": "prop",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.105,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/prop_wheel.blend)",
        "origin_label": "GENERATED",
        "builder": build_prop_wheel,
    },
    {
        "id": "prop_tunnel_straight",
        "name": "Straight Hollow Bark Tunnel",
        "category": "prop",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.055,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/prop_tunnel_straight.blend)",
        "origin_label": "GENERATED",
        "builder": build_prop_tunnel_straight,
    },
    {
        "id": "prop_tunnel_curved",
        "name": "Curved 90° Bark Tunnel",
        "category": "prop",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.065,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/prop_tunnel_curved.blend)",
        "origin_label": "GENERATED",
        "builder": build_prop_tunnel_curved,
    },
    {
        "id": "prop_hideout",
        "name": "Arched Wooden Hideout Cabin",
        "category": "prop",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.082,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/prop_hideout.blend)",
        "origin_label": "GENERATED",
        "builder": build_prop_hideout,
    },
    {
        "id": "prop_bridge_ramp",
        "name": "Bendy Log Bridge & Ramp",
        "category": "prop",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.065,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/prop_bridge_ramp.blend)",
        "origin_label": "GENERATED",
        "builder": build_prop_bridge_ramp,
    },
    {
        "id": "prop_chew_toy",
        "name": "Applewood Dumbbell Chew Toy",
        "category": "prop",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.032,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/prop_chew_toy.blend)",
        "origin_label": "GENERATED",
        "builder": build_prop_chew_toy,
    },
    {
        "id": "prop_small_ball",
        "name": "Woven Willow Play Ball",
        "category": "prop",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.024,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/prop_small_ball.blend)",
        "origin_label": "GENERATED",
        "builder": build_prop_small_ball,
    },
    # 5. DECOR (5 items — plant, wooden item, bedding patch, flag, picture frame)
    {
        "id": "decor_plant",
        "name": "Terracotta Spider Plant",
        "category": "decor",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.032,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/decor_plant.blend)",
        "origin_label": "GENERATED",
        "builder": build_decor_plant,
    },
    {
        "id": "decor_wooden_item",
        "name": "Mini Wooden Climbing Barrel",
        "category": "decor",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.032,
        "licence": "CC0 1.0 Universal",
        "author": "Kay Lousberg (www.kaylousberg.com)",
        "source": "https://kaylousberg.itch.io/kaykit-dungeon (barrel_small.gltf rescaled to 0.062m)",
        "origin_label": "DOWNLOADED",
        "builder": build_decor_wooden_item,
    },
    {
        "id": "decor_bedding_patch",
        "name": "Forest Moss & Aspen Patch",
        "category": "decor",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.010,  # walkable ground patch
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/decor_bedding_patch.blend)",
        "origin_label": "GENERATED",
        "builder": build_decor_bedding_patch,
    },
    {
        "id": "decor_flag",
        "name": "Hammy Pennant Flag",
        "category": "decor",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.025,
        "licence": "CC0 1.0 Universal",
        "author": "Kay Lousberg (www.kaylousberg.com)",
        "source": "https://kaylousberg.itch.io/kaykit-dungeon (banner_blue.gltf rescaled to 0.115m)",
        "origin_label": "DOWNLOADED",
        "builder": build_decor_flag,
    },
    {
        "id": "decor_picture_frame",
        "name": "Mini Wooden Portrait Frame",
        "category": "decor",
        "pivot": "base_center",
        "attachment_slot": None,
        "hamster_safe": None,
        "collision_radius_m": 0.032,
        "licence": "CC0 1.0 Universal",
        "author": "HAMMY Pipeline",
        "source": "Procedural Blender 5.2 (assets/source/decor_picture_frame.blend)",
        "origin_label": "GENERATED",
        "builder": build_decor_picture_frame,
    },
]


def main():
    print("\n" + "=" * 72)
    print(" HAMMY PIPELINE — STEP 3 & STEP 4: GENERATE, CONVERT & OPTIMIZE ASSETS")
    print("=" * 72)

    manifest_items = []
    for spec in ASSET_SPECS:
        spec["builder"]()
        entry = save_and_export_asset(spec)
        manifest_items.append(entry)

    manifest = {
        "schema_version": "1.0.0",
        "default_cage_policy": "minimal_opt_in",
        "default_cage_items": ["water_bottle"],
        "default_cage_assumption_note": "Per OVERRIDE spec: The cage starts clean and minimal with bedding and ONE basic water source (water_bottle) for the refill-water feature. All other foods, costumes, props, and decor are 100% opt-in from their respective shelves.",
        "cage_bounds_m": {
            "min_x": -0.44,
            "max_x": 0.44,
            "min_y": -0.19,
            "max_y": 0.19,
            "floor_z": 0.155,
        },
        "total_assets": len(manifest_items),
        "items": manifest_items,
    }

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    PUBLIC_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("=" * 72)
    print(f"Saved manifest with {len(manifest_items)} assets to:")
    print(f"  - {MANIFEST_PATH}")
    print(f"  - {PUBLIC_MANIFEST}")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
