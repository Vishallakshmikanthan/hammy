"""
HAMMY Art Pipeline — Prompt 4: Lighting, Indoor HDRI & Cinematic Camera Rig
Reads rules.md first.

Features:
  1. Poly Haven CC0 Indoor Room HDRI ('brown_photostudio_02_1k.hdr') for realistic multi-bounce
     environment lighting & glass/ceramic specular reflections. Logged in reference/licence_log.csv.
  2. Three switchable lighting presets controlled by LIGHTING_PRESET at top of script:
       - 'day'     : Bright soft window daylight (5600K) + cool sky ceiling fill + indoor HDRI.
       - 'evening' : Warm golden-hour low window sun (3400K) + warm desk lamp + dimmed HDRI.
       - 'night'   : Cozy nocturnal tungsten lamp (2650K) + faint cool moonlight fill.
  3. Three calibrated cameras in CAMERAS with physical Depth of Field (DoF):
       - cam_macro_85mm         : 85mm low hamster-eye macro view, f/3.2 shallow DoF.
       - cam_three_quarter_50mm : 50mm three-quarter hero view, f/5.6 DoF.
       - cam_wide_35mm          : 35mm wide establishing view, f/8.0 DoF.
  4. Optical imperfections (mild highlight bloom on bright speculars, subtle radial lens vignette,
     and fine organic film grain) + AgX High-Contrast color management.
  5. Functions configure_test_render_settings() (1080p, 128 samples, OptiX) and
     configure_final_render_settings() (4K, 512 samples, OptiX).
  6. Renders all 3 cameras across all 3 presets (9 shots) and builds a 3x3 Contact Sheet
     at renders/tests/04_lighting_contact_sheet.png, plus 1080p hero renders.
"""

import os
import sys
import math
import bpy
import numpy as np
from mathutils import Vector

# ==============================================================================
# SWITCHABLE LIGHTING PRESET ('day', 'evening', 'night')
# ==============================================================================
LIGHTING_PRESET = "day"

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


def setup_world_hdri(hdri_strength: float = 0.55, hdri_rot_z_deg: float = 35.0, tint=(1.0, 1.0, 1.0)):
    """Configures World environment lighting with Poly Haven indoor room HDRI."""
    scene = bpy.context.scene
    world = scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputWorld")
    output.location = (600, 0)

    bg = nodes.new("ShaderNodeBackground")
    bg.location = (350, 0)
    bg.inputs["Strength"].default_value = hdri_strength
    links.new(bg.outputs["Background"], output.inputs["Surface"])

    hdri_path = os.path.abspath("blender/textures/hdri/brown_photostudio_02_1k.hdr")
    if os.path.exists(hdri_path):
        tex_coord = nodes.new("ShaderNodeTexCoord")
        tex_coord.location = (-550, 0)

        mapping = nodes.new("ShaderNodeMapping")
        mapping.location = (-350, 0)
        mapping.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(hdri_rot_z_deg))
        links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])

        env_tex = nodes.new("ShaderNodeTexEnvironment")
        env_tex.location = (-100, 0)
        env_tex.image = bpy.data.images.load(hdri_path, check_existing=True)
        links.new(mapping.outputs["Vector"], env_tex.inputs["Vector"])

        # Optional color temperature tint mix for evening/night
        mix_tint = nodes.new("ShaderNodeMix")
        mix_tint.location = (150, 0)
        mix_tint.data_type = 'RGBA'
        mix_tint.blend_type = 'MULTIPLY'
        mix_tint.inputs["Factor"].default_value = 1.0
        links.new(env_tex.outputs["Color"], mix_tint.inputs["A"])
        mix_tint.inputs["B"].default_value = (tint[0], tint[1], tint[2], 1.0)
        links.new(mix_tint.outputs["Result"], bg.inputs["Color"])
    else:
        bg.inputs["Color"].default_value = (0.20 * tint[0], 0.20 * tint[1], 0.22 * tint[2], 1.0)


def build_lighting_rig(lights_col: bpy.types.Collection):
    """
    Creates the 3 physical room light sources in LIGHTS:
      1. light_window_key   : Large soft window area light (key)
      2. light_ceiling_fill : Broad overhead ceiling fill
      3. light_night_lamp   : Warm low-intensity desk/corner lamp
    """
    common.clear_collection("LIGHTS")
    target = Vector((0.05, 0.0, 0.17))

    # 1. Large Soft Window Key Light (simulates indoor room window to front-right)
    key_data = bpy.data.lights.new("light_window_key", 'AREA')
    key_data.shape = 'RECTANGLE'
    key_data.size = 1.15
    key_data.size_y = 1.45
    key_obj = bpy.data.objects.new("light_window_key", key_data)
    key_obj.location = Vector((1.15, -0.95, 1.05))
    look_at(key_obj, target)
    link_to_collection(key_obj, lights_col)

    # 2. Weak Ceiling Fill Light (soft overhead room bounce)
    fill_data = bpy.data.lights.new("light_ceiling_fill", 'AREA')
    fill_data.shape = 'RECTANGLE'
    fill_data.size = 1.60
    fill_data.size_y = 1.20
    fill_obj = bpy.data.objects.new("light_ceiling_fill", fill_data)
    fill_obj.location = Vector((-0.35, 0.25, 1.55))
    look_at(fill_obj, target)
    link_to_collection(fill_obj, lights_col)

    # 3. Warm Low-Intensity Lamp (for Evening & Night presets)
    lamp_data = bpy.data.lights.new("light_night_lamp", 'AREA')
    lamp_data.shape = 'DISK'
    lamp_data.size = 0.28
    lamp_obj = bpy.data.objects.new("light_night_lamp", lamp_data)
    lamp_obj.location = Vector((-0.62, -0.45, 0.62))
    look_at(lamp_obj, Vector((0.10, 0.02, 0.17)))
    link_to_collection(lamp_obj, lights_col)

    # 4. Subtle Backlight / Rim Light (for natural specular separation & backlit bedding translucency)
    rim_data = bpy.data.lights.new("light_rim_backlight", 'AREA')
    rim_data.shape = 'RECTANGLE'
    rim_data.size = 0.85
    rim_data.size_y = 0.45
    rim_obj = bpy.data.objects.new("light_rim_backlight", rim_data)
    rim_obj.location = Vector((0.15, 0.88, 0.72))
    look_at(rim_obj, Vector((0.15, -0.05, 0.17)))
    link_to_collection(rim_obj, lights_col)


def apply_lighting_preset(preset: str = "day"):
    """
    Switches the scene lighting and World HDRI between 'day', 'evening', and 'night'.
    """
    preset = preset.lower().strip()
    key_obj = bpy.data.objects.get("light_window_key")
    fill_obj = bpy.data.objects.get("light_ceiling_fill")
    lamp_obj = bpy.data.objects.get("light_night_lamp")
    rim_obj = bpy.data.objects.get("light_rim_backlight")

    target = Vector((0.05, 0.0, 0.17))

    if preset == "day":
        setup_world_hdri(hdri_strength=0.60, hdri_rot_z_deg=35.0, tint=(1.0, 0.99, 0.97))
        if key_obj:
            key_obj.location = Vector((1.15, -0.95, 1.08))
            look_at(key_obj, target)
            key_obj.data.energy = 26.0
            key_obj.data.color = (1.0, 0.97, 0.91)  # 5600K natural window sun
        if fill_obj:
            fill_obj.data.energy = 7.5
            fill_obj.data.color = (0.88, 0.94, 1.0)  # Cool sky indoor bounce
        if lamp_obj:
            lamp_obj.data.energy = 0.0
        if rim_obj:
            rim_obj.data.energy = 11.0
            rim_obj.data.color = (1.0, 0.96, 0.90)

    elif preset == "evening":
        # Golden hour low window angle + warm desk lamp
        setup_world_hdri(hdri_strength=0.28, hdri_rot_z_deg=55.0, tint=(1.0, 0.82, 0.64))
        if key_obj:
            key_obj.location = Vector((1.28, -0.85, 0.64))  # Lower sun angle casting longer shadows
            look_at(key_obj, target)
            key_obj.data.energy = 18.0
            key_obj.data.color = (1.0, 0.72, 0.44)  # 3300K golden hour glow
        if fill_obj:
            fill_obj.data.energy = 2.8
            fill_obj.data.color = (0.78, 0.84, 1.0)
        if lamp_obj:
            lamp_obj.data.energy = 5.5
            lamp_obj.data.color = (1.0, 0.68, 0.36)
        if rim_obj:
            rim_obj.data.energy = 8.5
            rim_obj.data.color = (1.0, 0.76, 0.50)

    elif preset == "night":
        # Cozy nocturnal room: warm tungsten corner lamp + faint cool window moonlight
        setup_world_hdri(hdri_strength=0.06, hdri_rot_z_deg=35.0, tint=(0.55, 0.68, 1.0))
        if key_obj:
            key_obj.location = Vector((1.15, -0.95, 1.08))
            look_at(key_obj, target)
            key_obj.data.energy = 2.2
            key_obj.data.color = (0.52, 0.68, 1.0)  # Cool moonlight
        if fill_obj:
            fill_obj.data.energy = 0.8
            fill_obj.data.color = (0.60, 0.70, 0.95)
        if lamp_obj:
            lamp_obj.data.energy = 12.5
            lamp_obj.data.color = (1.0, 0.64, 0.32)  # 2600K cozy warm lamp
        if rim_obj:
            rim_obj.data.energy = 3.5
            rim_obj.data.color = (1.0, 0.70, 0.40)


def build_cameras(cams_col: bpy.types.Collection):
    """
    Creates the 3 cameras required by Prompt 4 in CAMERAS with Depth of Field enabled:
      1. cam_macro_85mm         : Low macro (85mm, shallow DoF f/3.2)
      2. cam_three_quarter_50mm : Three-quarter (50mm, DoF f/5.6)
      3. cam_wide_35mm          : Wide angle (35mm, DoF f/8.0)
    """
    common.clear_collection("CAMERAS")

    # 1. Low Macro Camera (85mm, shallow DoF focused on ceramic bowl, spilled seeds & hideout arch)
    macro_target = Vector((0.26, -0.02, 0.185))
    macro_loc = Vector((-0.06, -0.58, 0.34))
    cam_macro_data = bpy.data.cameras.new("cam_macro_85mm")
    cam_macro_data.lens = 85.0
    cam_macro_data.sensor_width = 36.0
    cam_macro_data.clip_start = 0.01
    cam_macro_data.clip_end = 50.0
    cam_macro_data.dof.use_dof = True
    cam_macro_data.dof.focus_distance = (macro_loc - macro_target).length
    cam_macro_data.dof.aperture_fstop = 3.2

    cam_macro = bpy.data.objects.new("cam_macro_85mm", cam_macro_data)
    cam_macro.location = macro_loc
    look_at(cam_macro, macro_target)
    link_to_collection(cam_macro, cams_col)

    # 2. Three-Quarter Camera (50mm, natural human-eye perspective)
    tq_target = Vector((0.0, 0.0, 0.175))
    tq_loc = Vector((1.08, -1.28, 0.82))
    cam_tq_data = bpy.data.cameras.new("cam_three_quarter_50mm")
    cam_tq_data.lens = 50.0
    cam_tq_data.sensor_width = 36.0
    cam_tq_data.clip_start = 0.01
    cam_tq_data.clip_end = 50.0
    cam_tq_data.dof.use_dof = True
    cam_tq_data.dof.focus_distance = (tq_loc - tq_target).length
    cam_tq_data.dof.aperture_fstop = 5.6

    cam_tq = bpy.data.objects.new("cam_three_quarter_50mm", cam_tq_data)
    cam_tq.location = tq_loc
    look_at(cam_tq, tq_target)
    link_to_collection(cam_tq, cams_col)

    # 3. Wide Camera (35mm, wide establishing view from front-left)
    wide_target = Vector((0.02, 0.0, 0.175))
    wide_loc = Vector((-0.82, -1.02, 0.66))
    cam_wide_data = bpy.data.cameras.new("cam_wide_35mm")
    cam_wide_data.lens = 35.0
    cam_wide_data.sensor_width = 36.0
    cam_wide_data.clip_start = 0.01
    cam_wide_data.clip_end = 50.0
    cam_wide_data.dof.use_dof = True
    cam_wide_data.dof.focus_distance = (wide_loc - wide_target).length
    cam_wide_data.dof.aperture_fstop = 8.0

    cam_wide = bpy.data.objects.new("cam_wide_35mm", cam_wide_data)
    cam_wide.location = wide_loc
    look_at(cam_wide, wide_target)
    link_to_collection(cam_wide, cams_col)


def configure_test_render_settings(samples: int = 128, res_x: int = 1920, res_y: int = 1080):
    """
    Sets Cycles to the test render settings in rules.md:
    Cycles, GPU (OptiX), 128 samples, denoise on, 1920x1080, AgX view transform.
    """
    common.configure_cycles_gpu("OPTIX")
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 12
    scene.cycles.transmission_bounces = 12
    scene.cycles.transparent_max_bounces = 8

    # AgX Color Management for realistic highlight roll-off
    try:
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        scene.view_settings.view_transform = 'Filmic'


def configure_final_render_settings(samples: int = 512):
    """
    Switches Cycles to final 4K production render settings per rules.md:
    512+ samples, 3840x2160 (4K), OptiX GPU.
    """
    configure_test_render_settings(samples=samples, res_x=3840, res_y=2160)


def apply_optical_imperfections(image_path: str, vignette_strength: float = 0.14,
                                grain_sigma: float = 0.008, bloom_strength: float = 0.08):
    """
    Applies physically plausible camera imperfections (mild highlight bloom on bright speculars,
    natural radial vignette, and subtle organic film grain) directly to a rendered image via
    Blender's bpy.data.images pixel buffer + NumPy.
    """
    img = bpy.data.images.load(os.path.abspath(image_path), check_existing=False)
    w, h = img.size[0], img.size[1]
    pixels = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(pixels)
    arr = pixels.reshape((h, w, 4))
    rgb = arr[:, :, :3].copy()

    # 1. Mild Highlight Bloom (box-filtered glow on bright specular highlights > 0.78)
    lum = 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]
    bright_mask = np.clip((lum - 0.75) / 0.25, 0.0, 1.0)[:, :, None]
    highlights = rgb * bright_mask
    # Fast separable multi-pass box blur to approximate soft optical halation/bloom
    bloom = highlights.copy()
    for shift in (2, 5, 11, 21):
        bloom = 0.25 * (
            np.roll(bloom, shift, axis=0)
            + np.roll(bloom, -shift, axis=0)
            + np.roll(bloom, shift, axis=1)
            + np.roll(bloom, -shift, axis=1)
        )
    rgb = np.clip(rgb + bloom * bloom_strength, 0.0, 1.0)

    # 2. Subtle Radial Optical Vignette
    y_coords = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
    x_coords = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    r_sq = (x_coords * 0.92) ** 2 + (y_coords * 0.92) ** 2
    vignette = np.clip(1.0 - vignette_strength * (r_sq ** 1.25), 0.72, 1.0)[:, :, None]
    rgb = rgb * vignette

    # 3. Subtle Organic Film Grain (midtone-weighted so blacks don't clip noisily)
    rng = np.random.default_rng(42)
    noise_field = rng.normal(0.0, grain_sigma, size=(h, w, 1)).astype(np.float32)
    midtone_weight = 4.0 * rgb * (1.0 - rgb) + 0.25
    rgb = np.clip(rgb + noise_field * midtone_weight, 0.0, 1.0)

    arr[:, :, :3] = rgb
    img.pixels.foreach_set(arr.ravel())
    img.save()
    bpy.data.images.remove(img)


def build_contact_sheet(grid_paths: list[list[str]], output_path: str, cell_w: int = 640, cell_h: int = 360):
    """
    Stitches the 3x3 matrix of rendered images (Rows: Day, Evening, Night;
    Cols: Macro 85mm, Three-Quarter 50mm, Wide 35mm) into a single 1920x1080 contact sheet
    with clean border separators.
    """
    rows = len(grid_paths)
    cols = len(grid_paths[0])
    pad = 4
    total_w = cols * cell_w + (cols + 1) * pad
    total_h = rows * cell_h + (rows + 1) * pad

    canvas = np.full((total_h, total_w, 4), 0.08, dtype=np.float32)
    canvas[:, :, 3] = 1.0

    for r_idx, row_files in enumerate(grid_paths):
        # Note: Blender image rows start from bottom (y=0 is bottom), so invert r_idx for top-to-bottom layout
        inv_r = (rows - 1) - r_idx
        y0 = pad + inv_r * (cell_h + pad)
        for c_idx, fpath in enumerate(row_files):
            x0 = pad + c_idx * (cell_w + pad)
            img = bpy.data.images.load(os.path.abspath(fpath), check_existing=False)
            img.scale(cell_w, cell_h)
            px = np.empty(cell_w * cell_h * 4, dtype=np.float32)
            img.pixels.foreach_get(px)
            cell_arr = px.reshape((cell_h, cell_w, 4))
            canvas[y0:y0 + cell_h, x0:x0 + cell_w, :] = cell_arr
            bpy.data.images.remove(img)

    out_img = bpy.data.images.new("ContactSheet", width=total_w, height=total_h, alpha=True)
    out_img.pixels.foreach_set(canvas.ravel())
    out_img.filepath_raw = os.path.abspath(output_path)
    out_img.file_format = 'PNG'
    out_img.save()
    bpy.data.images.remove(out_img)
    print(f">> Saved 3x3 Contact Sheet: {output_path}")


def configure_viewport_for_gui():
    """
    Configures all 3D Viewports inside scene.blend to open directly in CAMERA view
    with MATERIAL/RENDERED shading and scene lights enabled, so the user sees the
    photoreal habitat immediately upon opening scene.blend in Blender!
    """
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'
                        space.shading.use_scene_lights = True
                        space.shading.use_scene_world = True
                        if space.region_3d:
                            space.region_3d.view_perspective = 'CAMERA'


def update_license_log():
    """Appends the Poly Haven indoor HDRI license entry to reference/licence_log.csv."""
    csv_path = os.path.abspath("reference/licence_log.csv")
    hdri_line = "brown_photostudio_02,Brown Photostudio 02 Indoor HDRI (1K HDR),https://polyhaven.com/a/brown_photostudio_02,CC0,Poly Haven (Sergej Majboroda),Indoor room world lighting & reflections\n"
    existing = ""
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            existing = f.read()
    if "brown_photostudio_02" not in existing:
        with open(csv_path, "a", encoding="utf-8") as f:
            f.write(hdri_line)
    print(f">> Logged brown_photostudio_02 HDRI in {csv_path}")


def render_view(camera_name: str, output_path: str, samples: int = 64, res_x: int = 960, res_y: int = 540):
    configure_test_render_settings(samples=samples, res_x=res_x, res_y=res_y)
    scene = bpy.context.scene
    scene.camera = bpy.data.objects[camera_name]
    abs_out = os.path.abspath(output_path)
    scene.render.filepath = abs_out
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)
    bpy.ops.render.render(write_still=True)
    apply_optical_imperfections(abs_out)
    print(f">> Rendered (with optical bloom/vignette/grain): {output_path}")


def main():
    print("\n" + "=" * 65)
    print(f" HAMMY PIPELINE — LIGHTING & CAMERA RIGS (PROMPT 4 | PRESET={LIGHTING_PRESET})")
    print("=" * 65)

    scene_path = os.path.abspath("blender/scene.blend")
    if os.path.exists(scene_path) and "cage_tub" not in bpy.data.objects:
        bpy.ops.wm.open_mainfile(filepath=scene_path)

    common.set_unit_scale_metric()
    master_col = bpy.context.scene.collection
    lights_col = common.get_or_create_collection("LIGHTS", parent=master_col)
    cams_col = common.get_or_create_collection("CAMERAS", parent=master_col)

    print("1. Building physical room lighting rig (Window Key, Ceiling Fill, Night Lamp, Rim)...")
    build_lighting_rig(lights_col)

    print("2. Building 3 Depth-of-Field cameras (85mm Macro, 50mm Three-Quarter, 35mm Wide)...")
    build_cameras(cams_col)

    print("3. Updating reference/licence_log.csv with Poly Haven indoor HDRI...")
    update_license_log()

    presets = ["day", "evening", "night"]
    cameras = [
        ("cam_macro_85mm", "macro85"),
        ("cam_three_quarter_50mm", "tq50"),
        ("cam_wide_35mm", "wide35"),
    ]

    print("4. Rendering 3x3 Preset x Camera matrix (9 shots)...")
    grid_paths = []
    for preset in presets:
        apply_lighting_preset(preset)
        row_paths = []
        for cam_name, cam_short in cameras:
            out_file = f"renders/tests/04_{preset}_{cam_short}.png"
            render_view(cam_name, out_file, samples=64, res_x=960, res_y=540)
            row_paths.append(out_file)
        grid_paths.append(row_paths)

    print("5. Assembling 3x3 Contact Sheet (renders/tests/04_lighting_contact_sheet.png)...")
    build_contact_sheet(grid_paths, "renders/tests/04_lighting_contact_sheet.png", cell_w=640, cell_h=360)

    print("6. Rendering 1080p Hero Views (128 samples per rules.md)...")
    apply_lighting_preset("day")
    render_view("cam_three_quarter_50mm", "renders/tests/04_hero_day_tq50.png", samples=128, res_x=1920, res_y=1080)
    apply_lighting_preset("evening")
    render_view("cam_macro_85mm", "renders/tests/04_hero_evening_macro85.png", samples=128, res_x=1920, res_y=1080)

    # Set active preset and default camera before saving scene.blend
    apply_lighting_preset(LIGHTING_PRESET)
    configure_test_render_settings(samples=128, res_x=1920, res_y=1080)
    bpy.context.scene.camera = bpy.data.objects["cam_three_quarter_50mm"]
    configure_viewport_for_gui()

    bpy.ops.wm.save_as_mainfile(filepath=scene_path)
    print(f">> Saved scene (with Viewport pre-set to CAMERA + MATERIAL mode): {scene_path}")

    print("=" * 65)
    print(" PROMPT 4 COMPLETE — LIGHTING, HDRI, CAMERAS & CONTACT SHEET READY")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()

