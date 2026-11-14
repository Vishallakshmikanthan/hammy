"""
HAMMY Art Pipeline — Prompt 5: Syrian Hamster Placeholder Body & Modern 3-Layer Fur System
Reads rules.md and reference/parameter_estimates.md first.

Blender Version Detected at Runtime: Blender 5.2.3 LTS (bpy.app.version = (5, 2, 3))
Modern Hair System Used:
  - Native `bpy.data.hair_curves` (`Curves` ID data-blocks) attached to `ham_body`
    (`ham_fur_undercoat`, `ham_fur_guard_hairs`, `ham_fur_face`, `ham_whiskers`)
  - Non-destructive `GeometryNodeTree` modifier (`GN_HamsterFurPreview`) using:
      * `GeometryNodeIsViewport`
      * `FunctionNodeRandomValue` (PROBABILITY)
      * `GeometryNodeSwitch`
      * `GeometryNodeDeleteGeometry` (domain='CURVE')
      * `GeometryNodeSetCurveRadius`
    This keeps the interactive 3D Viewport responsive (`VIEWPORT_PREVIEW_RATIO = 0.25`) while
    automatically rendering 100% full hair density in Cycles F12 renders.
  - Physically based `ShaderNodeBsdfHairPrincipled` (Huang / Chiang anisotropic hair model)
    driven by `ShaderNodeHairInfo` (`Intercept`, `Random`) and per-curve custom attributes
    (`coat_zone`, `cheek_bar`) for authentic Syrian hamster golden-agouti root-to-tip banding,
    ivory belly countershading, and backlit ear/fur translucency.
"""

import os
import sys
import time
import math
import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix

# ==============================================================================
# TUNABLE FUR & WHISKER PARAMETERS (Exposed in one place per Prompt 5)
# Verified against reference/parameter_estimates.md Section 3:
#   - Body length: 0.14 m - 0.16 m (we use 0.150 m)
#   - Guard hairs: 0.010 m - 0.014 m
#   - Undercoat:   0.005 m - 0.007 m
#   - Face fur:    0.002 m - 0.003 m
#   - Whiskers:    0.025 m - 0.035 m
# ==============================================================================
FUR_PARAMS = {
    "undercoat": {
        "length": 0.0068,          # 6.8 mm (parameter_estimates.md: 0.005 - 0.007 m)
        "density": 24000,          # 24,000 dense wavy undercoat strands
        "thickness": 0.00018,      # 0.18 mm renderable undercoat tuft fiber diameter
        "clump_amount": 0.65,      # Plush wooly micro-clumping
        "curl": 0.00065,           # 0.65 mm high-frequency wave/crimp amplitude
        "random_seed": 101,
    },
    "guard_hairs": {
        "length": 0.0132,          # 13.2 mm (parameter_estimates.md: 0.010 - 0.014 m)
        "density": 14000,          # 14,000 longer straighter tapered agouti guard hairs
        "thickness": 0.00024,      # 0.24 mm root diameter, sharply tapered to 10% tip
        "clump_amount": 0.82,      # Strong clumping toward tips for visible V-parted coat locks
        "curl": 0.00024,           # Slight natural wave
        "random_seed": 202,
    },
    "face_fur": {
        "length": 0.0032,          # 3.2 mm plush facial fur (tapers down to 0.8 mm vellus near nostrils)
        "density": 14500,          # 14,500 short velvety strands radiating from nasal bridge & cheeks
        "thickness": 0.00014,      # 0.14 mm fine facial hair
        "clump_amount": 0.55,      # Subtle micro-clumping on muzzle & cheeks
        "curl": 0.00012,           # Nearly straight radiating fibers
        "random_seed": 303,
    },
    "whiskers": {
        "length": 0.032,           # 32 mm vibrissae (parameter_estimates.md: 0.025 - 0.035 m)
        "count_per_side": 18,      # 36 mystacial + superciliary vibrissae total
        "thickness": 0.00032,      # 0.32 mm stiff tapered keratin root (clearly visible in macro)
        "droop": 0.0045,           # Natural downward & backward arc
        "random_seed": 404,
    },
    "viewport_preview_ratio": 0.25,  # 25% hair curves in 3D Viewport; 100% in Cycles Render
    "points_per_curve": 6,           # 6 control points per hair spline (smooth B-spline ribbons)
}

# Hamster world placement in the central cage clearing (between bark tunnel and food bowl,
# clear of prop_chew_block at (0.17, -0.05))
HAMSTER_POS = Vector((0.145, 0.032, 0.171))
HAMSTER_YAW_DEG = -135.0  # Three-quarter front pose facing front-left toward the macro camera & food bowl

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


# ==============================================================================
# 1. MATERIALS: ANISOTROPIC HAIR SHADER, SKIN/EARS/NOSE SSS & WET CORNEA EYES
# ==============================================================================
def build_hamster_materials() -> dict:
    mats = {}

    # --------------------------------------------------------------------------
    # A. Anisotropic Principled Hair BSDF (Undercoat, Guard Hairs, Face Fur)
    # --------------------------------------------------------------------------
    for layer_name in ("undercoat", "guard_hairs", "face_fur"):
        mat_name = f"mat_ham_fur_{layer_name}"
        mat = common.make_material(mat_name)
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        out = nodes.new("ShaderNodeOutputMaterial")
        out.location = (950, 0)

        hair_bsdf = nodes.new("ShaderNodeBsdfHairPrincipled")
        hair_bsdf.location = (650, 0)
        hair_bsdf.parametrization = 'COLOR'
        if hasattr(hair_bsdf, "model"):
            hair_bsdf.model = 'CHIANG'

        # Tuned anisotropic highlight, cuticle tilt, and backlight transmission
        hair_bsdf.inputs["IOR"].default_value = 1.55
        hair_bsdf.inputs["Offset"].default_value = math.radians(2.2)
        if layer_name == "undercoat":
            hair_bsdf.inputs["Roughness"].default_value = 0.34
            hair_bsdf.inputs["Radial Roughness"].default_value = 0.42  # Higher radial roughness = stronger backlight halo
            hair_bsdf.inputs["Coat"].default_value = 0.08
            hair_bsdf.inputs["Random Roughness"].default_value = 0.14
        elif layer_name == "guard_hairs":
            hair_bsdf.inputs["Roughness"].default_value = 0.22
            hair_bsdf.inputs["Radial Roughness"].default_value = 0.30
            hair_bsdf.inputs["Coat"].default_value = 0.25  # Glossy protective outer coat sheen
            hair_bsdf.inputs["Random Roughness"].default_value = 0.10
        else:  # face_fur
            hair_bsdf.inputs["Roughness"].default_value = 0.28
            hair_bsdf.inputs["Radial Roughness"].default_value = 0.36
            hair_bsdf.inputs["Coat"].default_value = 0.15
            hair_bsdf.inputs["Random Roughness"].default_value = 0.12

        links.new(hair_bsdf.outputs["BSDF"], out.inputs["Surface"])

        # Hair Info Node (Intercept 0..1 from root to tip, Random 0..1 per strand)
        hair_info = nodes.new("ShaderNodeHairInfo")
        hair_info.location = (-750, 150)

        # Custom per-curve attributes generated on the HairCurves data-block:
        #   - coat_zone : 0.0 = dorsal golden-agouti back/crown, 1.0 = creamy-white ventral belly/chin
        #   - cheek_bar : 0.0 = normal coat, 1.0 = dark brown/black Syrian cheek flash stripe
        attr_zone = nodes.new("ShaderNodeAttribute")
        attr_zone.location = (-750, -120)
        attr_zone.attribute_type = 'GEOMETRY'
        attr_zone.attribute_name = "coat_zone"

        attr_cheek = nodes.new("ShaderNodeAttribute")
        attr_cheek.location = (-750, -300)
        attr_cheek.attribute_type = 'GEOMETRY'
        attr_cheek.attribute_name = "cheek_bar"

        # Perturb Intercept slightly with per-strand Random so agouti bands aren't mathematically rigid
        rand_centered = nodes.new("ShaderNodeMath")
        rand_centered.location = (-520, 40)
        rand_centered.operation = 'SUBTRACT'
        links.new(hair_info.outputs["Random"], rand_centered.inputs[0])
        rand_centered.inputs[1].default_value = 0.5

        rand_scaled = nodes.new("ShaderNodeMath")
        rand_scaled.location = (-340, 40)
        rand_scaled.operation = 'MULTIPLY'
        links.new(rand_centered.outputs["Value"], rand_scaled.inputs[0])
        rand_scaled.inputs[1].default_value = 0.14

        intercept_jittered = nodes.new("ShaderNodeMath")
        intercept_jittered.location = (-160, 140)
        intercept_jittered.operation = 'ADD'
        intercept_jittered.use_clamp = True
        links.new(hair_info.outputs["Intercept"], intercept_jittered.inputs[0])
        links.new(rand_scaled.outputs["Value"], intercept_jittered.inputs[1])

        # Dorsal Golden-Agouti Root-to-Tip ColorRamp
        ramp_dorsal = nodes.new("ShaderNodeValToRGB")
        ramp_dorsal.location = (60, 260)
        cr_d = ramp_dorsal.color_ramp
        cr_d.interpolation = 'B_SPLINE'
        while len(cr_d.elements) < 4:
            cr_d.elements.new(0.5)

        if layer_name == "undercoat":
            # Paler, warm slate-buff base to soft apricot-cream tip
            cr_d.elements[0].position = 0.00
            cr_d.elements[0].color = (0.14, 0.10, 0.08, 1.0)   # Warm slate under-root
            cr_d.elements[1].position = 0.35
            cr_d.elements[1].color = (0.58, 0.36, 0.18, 1.0)   # Warm honey mid-shaft
            cr_d.elements[2].position = 0.78
            cr_d.elements[2].color = (0.76, 0.52, 0.26, 1.0)   # Pale golden-apricot
            cr_d.elements[3].position = 1.00
            cr_d.elements[3].color = (0.64, 0.42, 0.21, 1.0)   # Soft warm tip
        elif layer_name == "guard_hairs":
            # Classic Syrian Agouti banding: dark root -> rich golden-amber shaft -> dark agouti tip
            cr_d.elements[0].position = 0.00
            cr_d.elements[0].color = (0.10, 0.07, 0.05, 1.0)   # Deep slate-brown root
            cr_d.elements[1].position = 0.28
            cr_d.elements[1].color = (0.62, 0.34, 0.12, 1.0)   # Rich cinnamon-gold shaft
            cr_d.elements[2].position = 0.74
            cr_d.elements[2].color = (0.74, 0.44, 0.16, 1.0)   # Bright golden sub-apical band
            cr_d.elements[3].position = 0.96
            cr_d.elements[3].color = (0.12, 0.07, 0.04, 1.0)   # Dark agouti tip ticking
        else:  # face_fur
            cr_d.elements[0].position = 0.00
            cr_d.elements[0].color = (0.32, 0.20, 0.12, 1.0)
            cr_d.elements[1].position = 0.40
            cr_d.elements[1].color = (0.66, 0.42, 0.22, 1.0)
            cr_d.elements[2].position = 0.82
            cr_d.elements[2].color = (0.78, 0.56, 0.34, 1.0)
            cr_d.elements[3].position = 1.00
            cr_d.elements[3].color = (0.52, 0.32, 0.16, 1.0)

        links.new(intercept_jittered.outputs["Value"], ramp_dorsal.inputs["Fac"])

        # Ventral Belly / Lower Cheek Ivory-Cream ColorRamp
        ramp_ventral = nodes.new("ShaderNodeValToRGB")
        ramp_ventral.location = (60, 0)
        cr_v = ramp_ventral.color_ramp
        cr_v.elements[0].position = 0.00
        cr_v.elements[0].color = (0.58, 0.52, 0.46, 1.0)       # Warm pale grey-cream root
        cr_v.elements[1].position = 0.85
        cr_v.elements[1].color = (0.92, 0.87, 0.78, 1.0)       # Creamy ivory tip
        links.new(intercept_jittered.outputs["Value"], ramp_ventral.inputs["Fac"])

        # Blend Dorsal <-> Ventral using `coat_zone` attribute (use ShaderNodeMixRGB for explicit Color sockets)
        mix_zone = nodes.new("ShaderNodeMixRGB")
        mix_zone.location = (340, 120)
        mix_zone.blend_type = 'MIX'
        links.new(attr_zone.outputs["Fac"], mix_zone.inputs["Fac"])
        links.new(ramp_dorsal.outputs["Color"], mix_zone.inputs["Color1"])
        links.new(ramp_ventral.outputs["Color"], mix_zone.inputs["Color2"])

        # Blend dark Syrian cheek flash bar using `cheek_bar` attribute
        mix_cheek = nodes.new("ShaderNodeMixRGB")
        mix_cheek.location = (500, 120)
        mix_cheek.blend_type = 'MIX'
        links.new(attr_cheek.outputs["Fac"], mix_cheek.inputs["Fac"])
        links.new(mix_zone.outputs["Color"], mix_cheek.inputs["Color1"])
        mix_cheek.inputs["Color2"].default_value = (0.11, 0.07, 0.045, 1.0)

        links.new(mix_cheek.outputs["Color"], hair_bsdf.inputs["Color"])
        mats[layer_name] = mat

    # --------------------------------------------------------------------------
    # B. Translucent Keratin Whiskers (`mat_ham_whiskers`)
    # --------------------------------------------------------------------------
    mat_w = common.make_material("mat_ham_whiskers")
    nodes = mat_w.node_tree.nodes
    links = mat_w.node_tree.links
    nodes.clear()
    out_w = nodes.new("ShaderNodeOutputMaterial")
    out_w.location = (500, 0)
    bsdf_w = nodes.new("ShaderNodeBsdfHairPrincipled")
    bsdf_w.location = (200, 0)
    bsdf_w.parametrization = 'COLOR'
    bsdf_w.inputs["Roughness"].default_value = 0.14
    bsdf_w.inputs["Radial Roughness"].default_value = 0.20
    bsdf_w.inputs["Coat"].default_value = 0.45
    bsdf_w.inputs["IOR"].default_value = 1.56
    hi_w = nodes.new("ShaderNodeHairInfo")
    hi_w.location = (-320, 0)
    ramp_w = nodes.new("ShaderNodeValToRGB")
    ramp_w.location = (-80, 0)
    ramp_w.color_ramp.elements[0].position = 0.0
    ramp_w.color_ramp.elements[0].color = (0.55, 0.48, 0.42, 1.0)
    ramp_w.color_ramp.elements[1].position = 0.65
    ramp_w.color_ramp.elements[1].color = (0.94, 0.91, 0.86, 1.0)
    links.new(hi_w.outputs["Intercept"], ramp_w.inputs["Fac"])
    links.new(ramp_w.outputs["Color"], bsdf_w.inputs["Color"])
    links.new(bsdf_w.outputs["BSDF"], out_w.inputs["Surface"])
    mats["whiskers"] = mat_w

    # --------------------------------------------------------------------------
    # C. Subsurface-Scattered Skin for Sparse/Bare Ears, Nose & Paws (`mat_ham_skin_pink`)
    # --------------------------------------------------------------------------
    mat_skin = common.make_material("mat_ham_skin_pink")
    nodes = mat_skin.node_tree.nodes
    links = mat_skin.node_tree.links
    nodes.clear()
    out_s = nodes.new("ShaderNodeOutputMaterial")
    out_s.location = (500, 0)
    bsdf_s = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf_s.location = (180, 0)
    bsdf_s.inputs["Base Color"].default_value = (0.76, 0.46, 0.44, 1.0)  # Warm fleshy rose-pink
    bsdf_s.inputs["Roughness"].default_value = 0.44
    bsdf_s.inputs["Subsurface Weight"].default_value = 0.65              # Strong backlit ear/nose translucency
    bsdf_s.inputs["Subsurface Scale"].default_value = 0.004              # 4 mm scattering radius
    bsdf_s.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.22) # Reddish dermal blood scatter
    # Fine cellular skin micro-bump
    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-450, -150)
    noise_s = nodes.new("ShaderNodeTexNoise")
    noise_s.location = (-240, -150)
    noise_s.inputs["Scale"].default_value = 320.0
    noise_s.inputs["Detail"].default_value = 6.0
    bump_s = nodes.new("ShaderNodeBump")
    bump_s.location = (-40, -150)
    bump_s.inputs["Strength"].default_value = 0.12
    bump_s.inputs["Distance"].default_value = 0.0004
    links.new(tex_coord.outputs["Object"], noise_s.inputs["Vector"])
    links.new(noise_s.outputs["Fac"], bump_s.inputs["Height"])
    links.new(bump_s.outputs["Normal"], bsdf_s.inputs["Normal"])
    links.new(bsdf_s.outputs["BSDF"], out_s.inputs["Surface"])
    mats["skin"] = mat_skin

    # Warm Golden-Agouti Under-Pelt Base Material (`mat_ham_body_underpelt`) so any skin showing
    # between parted fur clumps on the torso has natural dark root shadow & warm skin tone, while
    # the muzzle tip transitions to fleshy rose-pink
    mat_pelt = common.make_material("mat_ham_body_underpelt")
    nodes = mat_pelt.node_tree.nodes
    links = mat_pelt.node_tree.links
    nodes.clear()
    out_p = nodes.new("ShaderNodeOutputMaterial")
    out_p.location = (600, 0)
    bsdf_p = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf_p.location = (300, 0)
    bsdf_p.inputs["Roughness"].default_value = 0.86
    bsdf_p.inputs["Sheen Weight"].default_value = 0.90
    bsdf_p.inputs["Sheen Roughness"].default_value = 0.62
    bsdf_p.inputs["Subsurface Weight"].default_value = 0.15
    bsdf_p.inputs["Subsurface Scale"].default_value = 0.003
    bsdf_p.inputs["Subsurface Radius"].default_value = (1.0, 0.40, 0.25)
    vcol_p = nodes.new("ShaderNodeVertexColor")
    vcol_p.location = (-40, 0)
    vcol_p.layer_name = "Col"
    links.new(vcol_p.outputs["Color"], bsdf_p.inputs["Base Color"])
    links.new(bsdf_p.outputs["BSDF"], out_p.inputs["Surface"])
    mats["pelt"] = mat_pelt

    # Darker pigmented outer ear pinna skin (`mat_ham_ear_dark`)
    mat_ear = common.make_material("mat_ham_ear_dark")
    nodes = mat_ear.node_tree.nodes
    links = mat_ear.node_tree.links
    nodes.clear()
    out_e = nodes.new("ShaderNodeOutputMaterial")
    out_e.location = (450, 0)
    bsdf_e = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf_e.location = (150, 0)
    bsdf_e.inputs["Base Color"].default_value = (0.38, 0.24, 0.22, 1.0)  # Translucent greyish-pink pinna
    bsdf_e.inputs["Roughness"].default_value = 0.48
    bsdf_e.inputs["Subsurface Weight"].default_value = 0.78              # Thin backlit ear cartilage
    bsdf_e.inputs["Subsurface Scale"].default_value = 0.005
    bsdf_e.inputs["Subsurface Radius"].default_value = (1.0, 0.32, 0.18)
    links.new(bsdf_e.outputs["BSDF"], out_e.inputs["Surface"])
    mats["ear"] = mat_ear

    # Moist Rhinarium / Nose Pad (`mat_ham_nose_wet`)
    mat_nose = common.make_material("mat_ham_nose_wet")
    nodes = mat_nose.node_tree.nodes
    links = mat_nose.node_tree.links
    nodes.clear()
    out_n = nodes.new("ShaderNodeOutputMaterial")
    out_n.location = (450, 0)
    bsdf_n = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf_n.location = (150, 0)
    bsdf_n.inputs["Base Color"].default_value = (0.78, 0.42, 0.42, 1.0)
    bsdf_n.inputs["Roughness"].default_value = 0.26
    bsdf_n.inputs["Coat Weight"].default_value = 0.75                    # Moist specular sheen on nose tip
    bsdf_n.inputs["Coat Roughness"].default_value = 0.08
    bsdf_n.inputs["Subsurface Weight"].default_value = 0.60
    bsdf_n.inputs["Subsurface Scale"].default_value = 0.003
    bsdf_n.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.25)
    links.new(bsdf_n.outputs["BSDF"], out_n.inputs["Surface"])
    mats["nose"] = mat_nose

    # --------------------------------------------------------------------------
    # D. Glossy Wet-Cornea Dark Ruby-Black Eye (`mat_ham_eye_cornea`)
    # --------------------------------------------------------------------------
    mat_eye = common.make_material("mat_ham_eye_cornea")
    nodes = mat_eye.node_tree.nodes
    links = mat_eye.node_tree.links
    nodes.clear()
    out_eye = nodes.new("ShaderNodeOutputMaterial")
    out_eye.location = (400, 0)
    bsdf_eye = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf_eye.location = (100, 0)
    bsdf_eye.inputs["Base Color"].default_value = (0.012, 0.007, 0.005, 1.0)  # Deep espresso-black iris/pupil
    bsdf_eye.inputs["Roughness"].default_value = 0.015
    bsdf_eye.inputs["IOR"].default_value = 1.376                              # Real human/mammalian cornea IOR
    bsdf_eye.inputs["Coat Weight"].default_value = 1.0                        # Tear-film mirror catchlight
    bsdf_eye.inputs["Coat Roughness"].default_value = 0.005
    bsdf_eye.inputs["Coat IOR"].default_value = 1.336                         # Tear film IOR
    links.new(bsdf_eye.outputs["BSDF"], out_eye.inputs["Surface"])
    mats["eye"] = mat_eye

    return mats


# ==============================================================================
# 2. PLACEHOLDER SYRIAN HAMSTER BASE MESH (`ham_body`) + ANATOMICAL SUB-PARTS
# ==============================================================================
def build_placeholder_hamster(ham_col: bpy.types.Collection, mats: dict) -> bpy.types.Object:
    """
    Creates the clearly-labelled Syrian hamster placeholder body mesh `ham_body` at exact
    real-world scale (0.150 m nose-to-rump length, ~0.072 m width, ~0.068 m height), plus
    wet-cornea eyes (`ham_eye_L`, `ham_eye_R`), thin translucent ear pinnae (`ham_ear_L`, `ham_ear_R`),
    rhinarium nose pad (`ham_nose`), fore/hind paws (`ham_paw_*`), and short stub tail (`ham_tail`).

    Populates vertex groups on `ham_body` to drive hair density and flow:
      - `vg_undercoat`   : High weight across torso/rump/shoulders, zero on nose/eye rims
      - `vg_guard_hairs` : High weight on dorsal back/flanks, zero on muzzle/ears/feet
      - `vg_face_fur`    : High weight on muzzle, bridge of nose, forehead, and cheeks
    """
    common.clear_collection("HAMSTER")

    rot_mat = Matrix.Rotation(math.radians(HAMSTER_YAW_DEG), 4, 'Z')
    world_xform = Matrix.Translation(HAMSTER_POS) @ rot_mat

    # --------------------------------------------------------------------------
    # A. Sculpted Profile `ham_body` (Pear-shaped Syrian hamster body + head + cheeks + muzzle)
    # Local coordinates before world transform:
    #   +Y = Anterior (Nose at y = +0.075 m)
    #   -Y = Posterior (Rump at y = -0.075 m) -> Total length = 0.150 m
    #   +Z = Dorsal (Back height z = 0.068 m, Belly rests near z = 0.004 m)
    # --------------------------------------------------------------------------
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=56, v_segments=40, radius=1.0)

    for v in bm.verts:
        nx, ny, nz = v.co.x, v.co.y, v.co.z
        # Map ny (-1..+1) to longitudinal coordinate y (-0.075 m .. +0.075 m)
        y = ny * 0.075
        # Normalize longitudinal parameter s in [0 = rump, 1 = nose tip]
        s = 0.5 * (ny + 1.0)

        # Cross-sectional half-width w(s) and half-height h(s)
        # Sculpted from reference/photos/images.cv_23mpmrt35vasncelu0dtfo/data/test/hamster/32N6IKR3OOH6.jpg:
        #   - Note: UV sphere has cos(theta) = sqrt(1 - ny^2) already built into nx and nz!
        #   - To get a blunt, boxy Syrian hamster muzzle (instead of a pointed hedgehog cone),
        #     we compensate for sqrt(1 - ny^2) near the nose and rump so the head stays wide and rounded!
        sphere_taper = math.sqrt(max(0.08, 1.0 - ny * ny))

        # Pear-shaped Syrian hamster profile (widest & plumpest at the rump/haunches,
        # gentle neck tuck, chubby cheeks, and short rounded muzzle):
        #   - Rump cap (s=0.02..0.15): rounds off smoothly like a peach, NOT a skinny cone
        #   - Haunches/Body (s=0.25..0.42): ~37 mm half-width, ~29 mm half-height (plumpest!)
        #   - Neck/Shoulders (s=0.56): ~29 mm half-width
        #   - Cheek Pouches (s=0.71): ~32 mm half-width
        #   - Short Snout (s=0.88): ~19 mm half-width
        s_clamped = min(max(s, 0.015), 0.985)
        pear_env = (s_clamped ** 0.24) * ((1.0 - s_clamped) ** 0.52) * 1.98
        true_w = (
            0.037 * pear_env
            + 0.0055 * math.exp(-((s - 0.71) / 0.11) ** 2)   # Chubby cheek pouches
            + 0.0045 * math.exp(-((s - 0.88) / 0.08) ** 2)   # Puffy whisker pads
            - 0.0030 * math.exp(-((s - 0.56) / 0.08) ** 2)   # Subtle neck/shoulder tuck
        )
        half_w = true_w / sphere_taper

        true_h = (
            0.029 * pear_env
            + 0.0050 * math.exp(-((s - 0.72) / 0.12) ** 2)   # Rounded forehead crown
            - 0.0020 * math.exp(-((s - 0.83) / 0.045) ** 2)  # Subtle nasal stop dip
            + 0.0038 * math.exp(-((s - 0.90) / 0.08) ** 2)   # Blunt rounded muzzle
        )
        half_h = true_h / sphere_taper

        # Centerline height z_center(s): low plump belly resting on bedding, slightly raised head
        z_center = 0.025 + 0.0060 * math.exp(-((s - 0.73) / 0.22) ** 2) - 0.0035 * max(0.0, (s - 0.85) / 0.15)

        x = nx * half_w
        # Expand chubby lower cheek pouches and puffy whisker pads laterally
        if nz < 0.25 and 0.58 < s < 0.96:
            pouch_factor = 0.20 * math.exp(-((s - 0.72) / 0.11) ** 2) + 0.16 * math.exp(-((s - 0.89) / 0.07) ** 2)
            x *= 1.0 + pouch_factor * (1.0 - 0.5 * abs(nz))

        z = z_center + nz * half_h

        # Subtle eye-socket indentation around the orbital rim
        p_temp = Vector((x, y, z))
        for sgn in (1.0, -1.0):
            orb_center = Vector((sgn * 0.0185, 0.0495, 0.0445))
            d_orb = (p_temp - orb_center).length
            if d_orb < 0.0075:
                indent = 0.0018 * math.cos(0.5 * math.pi * (d_orb / 0.0075)) ** 2
                x -= sgn * indent * 0.85
                z -= indent * 0.35

        # Subtle vertical philtrum cleft at the front-lower lip (s > 0.94, nz < 0.0, |nx| < 0.25)
        if s > 0.93 and nz < 0.05 and abs(nx) < 0.28:
            cleft = 0.0014 * math.exp(-((nx / 0.12) ** 2)) * ((s - 0.93) / 0.07)
            y -= cleft

        # Flatten ventral belly where hamster rests on the bedding surface
        if z < 0.0055:
            z = 0.0055 + 0.22 * (z - 0.0055)

        v.co = Vector((x, y, z))

    mesh_body = bpy.data.meshes.new("ham_body_placeholder")
    bm.to_mesh(mesh_body)
    bm.free()

    for poly in mesh_body.polygons:
        poly.use_smooth = True

    obj_body = bpy.data.objects.new("ham_body", mesh_body)
    obj_body.matrix_world = world_xform
    obj_body.data.materials.append(mats["pelt"])
    link_to_collection(obj_body, ham_col)

    # Create Vertex Groups on `ham_body` for density & flow control
    vg_under = obj_body.vertex_groups.new(name="vg_undercoat")
    vg_guard = obj_body.vertex_groups.new(name="vg_guard_hairs")
    vg_face = obj_body.vertex_groups.new(name="vg_face_fur")
    vg_skin_bare = obj_body.vertex_groups.new(name="vg_bare_skin")

    eye_l_local = Vector((0.0252, 0.0518, 0.0452))
    eye_r_local = Vector((-0.0252, 0.0518, 0.0452))
    nose_local = Vector((0.0, 0.0758, 0.0295))

    # Bake Syrian Golden-Agouti & Cream-Belly vertex colors (`Col`) directly into `ham_body`
    color_attr = mesh_body.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
    for poly in mesh_body.polygons:
        for loop_idx in poly.loop_indices:
            v_idx = mesh_body.loops[loop_idx].vertex_index
            p = mesh_body.vertices[v_idx].co
            s = (p.y + 0.075) / 0.150
            # Ventral belly & lower cheek cream mask
            belly_w = max(0.0, min(1.0, (0.024 - p.z) / 0.016))
            cheek_w = max(0.0, min(1.0, (s - 0.62) / 0.18)) * max(0.0, min(1.0, (0.030 - p.z) / 0.014))
            band_w = math.exp(-((p.y - 0.002) / 0.022) ** 2) * max(0.0, min(1.0, (0.042 - p.z) / 0.020)) * 0.72
            cream_w = max(belly_w, cheek_w * 0.75, band_w)

            # Dorsal dark agouti stripe
            spine_w = math.exp(-((p.x) / 0.014) ** 2) * max(0.0, min(1.0, (p.z - 0.036) / 0.020)) * (1.0 - max(0.0, (s - 0.85) / 0.15))
            # Subtle deterministic per-vertex agouti ticking
            tick = 0.5 + 0.5 * math.sin(p.x * 380.0 + p.y * 290.0 + p.z * 310.0)
            r_gold = 0.56 + 0.18 * tick - 0.24 * spine_w
            g_gold = 0.34 + 0.12 * tick - 0.17 * spine_w
            b_gold = 0.17 + 0.06 * tick - 0.09 * spine_w

            r = r_gold * (1.0 - cream_w) + 0.93 * cream_w
            g = g_gold * (1.0 - cream_w) + 0.88 * cream_w
            b = b_gold * (1.0 - cream_w) + 0.79 * cream_w
            color_attr.data[loop_idx].color = (max(0.0, min(1.0, r)), max(0.0, min(1.0, g)), max(0.0, min(1.0, b)), 1.0)

    for idx, v in enumerate(mesh_body.vertices):
        p = v.co
        s = (p.y + 0.075) / 0.150
        d_nose = (p - nose_local).length
        d_eye = min((p - eye_l_local).length, (p - eye_r_local).length)

        # Keep bare skin ring around nostrils and eyelids so the prominent glossy black eyes
        # and pink rhinarium nose pad sit cleanly outside the fur
        eye_mask = min(1.0, max(0.0, (d_eye - 0.0068) / 0.0035))
        nose_mask = min(1.0, max(0.0, (d_nose - 0.0038) / 0.0032))
        bare_mask = eye_mask * nose_mask

        # Undercoat weight: dense over body and cheeks (s < 0.85), tapering near nose tip
        w_under = bare_mask * (1.0 - max(0.0, (s - 0.78) / 0.20))
        # Guard hairs weight: strongest on dorsal back, crown & flanks (s < 0.80, z > 0.012)
        w_guard = bare_mask * (1.0 - max(0.0, (s - 0.75) / 0.21)) * min(1.0, max(0.15, (p.z - 0.008) / 0.025))
        # Face fur weight: dense velvety coat across the entire snout, whisker pads, cheeks & forehead (s > 0.54)
        w_face = bare_mask * min(1.0, max(0.0, (s - 0.52) / 0.16))

        vg_under.add([idx], float(np.clip(w_under, 0.0, 1.0)), 'REPLACE')
        vg_guard.add([idx], float(np.clip(w_guard, 0.0, 1.0)), 'REPLACE')
        vg_face.add([idx], float(np.clip(w_face, 0.0, 1.0)), 'REPLACE')
        vg_skin_bare.add([idx], float(np.clip(1.0 - bare_mask, 0.0, 1.0)), 'REPLACE')

    # --------------------------------------------------------------------------
    # B. Glossy Beady Black Eyes (`ham_eye_L`, `ham_eye_R`)
    # --------------------------------------------------------------------------
    for side_label, sign in (("L", 1.0), ("R", -1.0)):
        bm_eye = bmesh.new()
        bmesh.ops.create_uvsphere(bm_eye, u_segments=24, v_segments=16, radius=0.0058)
        m_eye = bpy.data.meshes.new(f"ham_eye_{side_label}")
        bm_eye.to_mesh(m_eye)
        bm_eye.free()
        for poly in m_eye.polygons:
            poly.use_smooth = True
        o_eye = bpy.data.objects.new(f"ham_eye_{side_label}", m_eye)
        local_pos = Vector((sign * 0.0252, 0.0518, 0.0452))
        o_eye.matrix_world = world_xform @ Matrix.Translation(local_pos)
        o_eye.data.materials.append(mats["eye"])
        link_to_collection(o_eye, ham_col)

    # --------------------------------------------------------------------------
    # C. Thin Translucent Rounded Ear Pinnae (`ham_ear_L`, `ham_ear_R`) — Bare/Sparse Skin
    # --------------------------------------------------------------------------
    for side_label, sign in (("L", 1.0), ("R", -1.0)):
        bm_ear = bmesh.new()
        bmesh.ops.create_uvsphere(bm_ear, u_segments=24, v_segments=16, radius=1.0)
        for v in bm_ear.verts:
            # Cup-shaped thin rounded ear petal (24 mm tall, 18 mm wide, 2.2 mm thin)
            ex = v.co.x * 0.0092
            ey = v.co.y * 0.0015 + 0.0035 * (v.co.x ** 2 + max(0.0, v.co.z) ** 2)
            ez = (v.co.z + 0.95) * 0.0088
            v.co = Vector((ex, ey, ez))
        m_ear = bpy.data.meshes.new(f"ham_ear_{side_label}")
        bm_ear.to_mesh(m_ear)
        bm_ear.free()
        for poly in m_ear.polygons:
            poly.use_smooth = True
        o_ear = bpy.data.objects.new(f"ham_ear_{side_label}", m_ear)
        ear_local = Vector((sign * 0.0245, 0.025, 0.0545))
        ear_rot = (
            Matrix.Rotation(math.radians(-10.0), 4, 'X')
            @ Matrix.Rotation(math.radians(sign * -22.0), 4, 'Y')
            @ Matrix.Rotation(math.radians(sign * 24.0), 4, 'Z')
        )
        o_ear.matrix_world = world_xform @ Matrix.Translation(ear_local) @ ear_rot
        o_ear.data.materials.append(mats["ear"])
        link_to_collection(o_ear, ham_col)

    # --------------------------------------------------------------------------
    # D. Bare Pink Rhinarium Nose Pad (`ham_nose`)
    # --------------------------------------------------------------------------
    bm_nose = bmesh.new()
    bmesh.ops.create_uvsphere(bm_nose, u_segments=20, v_segments=14, radius=1.0)
    for v in bm_nose.verts:
        v.co = Vector((v.co.x * 0.0046, v.co.y * 0.0032, v.co.z * 0.0038))
    m_nose = bpy.data.meshes.new("ham_nose")
    bm_nose.to_mesh(m_nose)
    bm_nose.free()
    for poly in m_nose.polygons:
        poly.use_smooth = True
    o_nose = bpy.data.objects.new("ham_nose", m_nose)
    o_nose.matrix_world = world_xform @ Matrix.Translation(nose_local)
    o_nose.data.materials.append(mats["nose"])
    link_to_collection(o_nose, ham_col)

    # --------------------------------------------------------------------------
    # E. Four Dainty Pink Paws (`ham_paw_fl`, `ham_paw_fr`, `ham_paw_bl`, `ham_paw_br`) & Stub Tail (`ham_tail`)
    # --------------------------------------------------------------------------
    paw_specs = [
        ("ham_paw_fl", Vector((0.015, 0.036, 0.0055)), (0.0050, 0.0072, 0.0036)),
        ("ham_paw_fr", Vector((-0.015, 0.036, 0.0055)), (0.0050, 0.0072, 0.0036)),
        ("ham_paw_bl", Vector((0.024, -0.034, 0.0058)), (0.0060, 0.0098, 0.0040)),
        ("ham_paw_br", Vector((-0.024, -0.034, 0.0058)), (0.0060, 0.0098, 0.0040)),
        ("ham_tail", Vector((0.0, -0.072, 0.016)), (0.0036, 0.0060, 0.0034)),
    ]
    for p_name, p_loc, p_scale in paw_specs:
        bm_p = bmesh.new()
        bmesh.ops.create_uvsphere(bm_p, u_segments=16, v_segments=12, radius=1.0)
        for v in bm_p.verts:
            v.co = Vector((v.co.x * p_scale[0], v.co.y * p_scale[1], v.co.z * p_scale[2]))
        m_p = bpy.data.meshes.new(p_name)
        bm_p.to_mesh(m_p)
        bm_p.free()
        for poly in m_p.polygons:
            poly.use_smooth = True
        o_p = bpy.data.objects.new(p_name, m_p)
        o_p.matrix_world = world_xform @ Matrix.Translation(p_loc)
        o_p.data.materials.append(mats["skin"])
        link_to_collection(o_p, ham_col)

    return obj_body


# ==============================================================================
# 3. GEOMETRY NODES MODIFIER FOR VIEWPORT PREVIEW DENSITY & RADIUS TAPER
# ==============================================================================
def get_or_create_fur_gn_group() -> bpy.types.NodeTree:
    """
    Builds a reusable Geometry Nodes group `GN_HamsterFurPreview` for Blender 5.2 `HairCurves`:
      - Reads `Is Viewport` (`GeometryNodeIsViewport`)
      - Uses `Random Value (Probability)` + `Delete Geometry (CURVE)` when in the interactive
        3D Viewport so only `Viewport Preview Ratio` (default 25%) of curves are drawn in the
        viewport, while 100% of curves render in Cycles F12!
      - Applies a subtle `Radius Scale` multiplier via `GeometryNodeSetCurveRadius`.
    """
    group_name = "GN_HamsterFurPreview"
    if group_name in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[group_name])

    ng = bpy.data.node_groups.new(group_name, 'GeometryNodeTree')

    # Interface sockets
    ng.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    s_ratio = ng.interface.new_socket(name="Viewport Preview Ratio", in_out='INPUT', socket_type='NodeSocketFloat')
    s_ratio.default_value = float(FUR_PARAMS["viewport_preview_ratio"])
    s_ratio.min_value = 0.01
    s_ratio.max_value = 1.0

    s_seed = ng.interface.new_socket(name="Seed", in_out='INPUT', socket_type='NodeSocketInt')
    s_seed.default_value = 42

    ng.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    nodes = ng.nodes
    links = ng.links

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-600, 0)

    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (450, 0)

    # 1 - Viewport Preview Ratio = probability of deleting a curve in viewport
    n_sub = nodes.new("ShaderNodeMath")
    n_sub.location = (-360, -140)
    n_sub.operation = 'SUBTRACT'
    n_sub.inputs[0].default_value = 1.0
    links.new(n_in.outputs["Viewport Preview Ratio"], n_sub.inputs[1])

    n_rand = nodes.new("FunctionNodeRandomValue")
    n_rand.location = (-160, -160)
    n_rand.data_type = 'BOOLEAN'
    links.new(n_sub.outputs["Value"], n_rand.inputs["Probability"])
    links.new(n_in.outputs["Seed"], n_rand.inputs["Seed"])

    n_del = nodes.new("GeometryNodeDeleteGeometry")
    n_del.location = (40, -100)
    n_del.domain = 'CURVE'
    links.new(n_in.outputs["Geometry"], n_del.inputs["Geometry"])
    links.new(n_rand.outputs["Value"], n_del.inputs["Selection"])

    n_is_vp = nodes.new("GeometryNodeIsViewport")
    n_is_vp.location = (40, 120)

    n_switch = nodes.new("GeometryNodeSwitch")
    n_switch.location = (250, 20)
    n_switch.input_type = 'GEOMETRY'
    links.new(n_is_vp.outputs["Is Viewport"], n_switch.inputs["Switch"])
    links.new(n_in.outputs["Geometry"], n_switch.inputs["False"])  # Full 100% density in Cycles F12 Render
    links.new(n_del.outputs["Geometry"], n_switch.inputs["True"])  # Decimated preview in 3D Viewport

    links.new(n_switch.outputs["Output"], n_out.inputs["Geometry"])
    return ng


# ==============================================================================
# 4. MODERN HAIR CURVES GENERATOR (3 LAYERS + VIBRISSAE WHISKERS)
# ==============================================================================
def build_hair_layer_curves(
    name: str,
    body_obj: bpy.types.Object,
    layer_cfg: dict,
    layer_type: str,
    mat: bpy.types.Material,
    gn_group: bpy.types.NodeTree,
    ham_col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Generates a native Blender 5.2 `bpy.data.hair_curves` object on `ham_body` with:
      - Anatomically combed flow field (radiating from nasal bridge on face, sweeping outward
        over cheek pouches, flowing head-to-rump along back/flanks, and lying flat on the belly)
      - Guide-strand clumping (`clump_amount`) so neighboring fibers converge into natural tufts
      - High-frequency curl/crimp (`curl`) and random length/thickness variation
      - Root-to-tip tapered `radius` point attribute
      - Custom per-curve `coat_zone` and `cheek_bar` attributes for the Principled Hair BSDF shader
    """
    rng = np.random.default_rng(layer_cfg["random_seed"])
    n_strands = int(layer_cfg["density"])
    pts_per_curve = int(FUR_PARAMS["points_per_curve"])
    base_len = float(layer_cfg["length"])
    base_radius = float(layer_cfg["thickness"]) * 0.5
    clump_amt = float(layer_cfg["clump_amount"])
    curl_amp = float(layer_cfg["curl"])

    mesh = body_obj.data
    verts = np.array([v.co[:] for v in mesh.vertices], dtype=np.float32)
    norms = np.array([v.normal[:] for v in mesh.vertices], dtype=np.float32)

    # Extract triangles and compute surface areas weighted by the layer's vertex group
    vg_name = f"vg_{layer_type}"
    vg_idx = body_obj.vertex_groups[vg_name].index
    v_weights = np.zeros(len(mesh.vertices), dtype=np.float32)
    for idx, v in enumerate(mesh.vertices):
        for g in v.groups:
            if g.group == vg_idx:
                v_weights[idx] = g.weight
                break

    mesh.calc_loop_triangles()
    tri_v_indices = np.array([[lt.vertices[0], lt.vertices[1], lt.vertices[2]] for lt in mesh.loop_triangles], dtype=np.int32)
    v0 = verts[tri_v_indices[:, 0]]
    v1 = verts[tri_v_indices[:, 1]]
    v2 = verts[tri_v_indices[:, 2]]
    tri_areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    tri_w = (v_weights[tri_v_indices[:, 0]] + v_weights[tri_v_indices[:, 1]] + v_weights[tri_v_indices[:, 2]]) / 3.0

    probs = tri_areas * (tri_w ** 1.4)
    probs = np.maximum(probs, 0.0)
    probs /= np.sum(probs)

    # Sample root positions on triangles via barycentric coordinates
    chosen_tris = rng.choice(len(tri_v_indices), size=n_strands, p=probs)
    r1 = np.sqrt(rng.random(n_strands, dtype=np.float32))
    r2 = rng.random(n_strands, dtype=np.float32)
    b0 = 1.0 - r1
    b1 = r1 * (1.0 - r2)
    b2 = r1 * r2

    roots = (
        b0[:, None] * verts[tri_v_indices[chosen_tris, 0]]
        + b1[:, None] * verts[tri_v_indices[chosen_tris, 1]]
        + b2[:, None] * verts[tri_v_indices[chosen_tris, 2]]
    )
    root_normals = (
        b0[:, None] * norms[tri_v_indices[chosen_tris, 0]]
        + b1[:, None] * norms[tri_v_indices[chosen_tris, 1]]
        + b2[:, None] * norms[tri_v_indices[chosen_tris, 2]]
    )
    root_normals /= np.maximum(np.linalg.norm(root_normals, axis=1, keepdims=True), 1e-6)

    # Longitudinal normalized coordinate s in [0 = rump, 1 = nose tip]
    s_coord = np.clip((roots[:, 1] + 0.075) / 0.150, 0.0, 1.0)

    # Compute anatomical hair flow vector (tangent to body surface)
    #   - Nose/muzzle (s > 0.72): radiates outward & backward from nose apex (0, 0.0755, 0.0265)
    #   - Cheek pouches (0.58 < s < 0.82): sweeps outward laterally & backward over bloated cheeks
    #   - Dorsal back & flanks: flows smoothly from head to rump (0, -1, -0.18)
    #   - Ventral belly (z < 0.014): lies flat backward along the underside
    nose_apex = np.array([[0.0, 0.0755, 0.0265]], dtype=np.float32)
    vec_from_nose = roots - nose_apex
    vec_from_nose /= np.maximum(np.linalg.norm(vec_from_nose, axis=1, keepdims=True), 1e-5)

    back_flow = np.zeros_like(roots)
    back_flow[:, 0] = np.sign(roots[:, 0]) * 0.18 * np.exp(-((s_coord - 0.70) / 0.15) ** 2)
    back_flow[:, 1] = -1.0
    back_flow[:, 2] = -0.16 - 0.22 * np.clip((0.30 - s_coord) / 0.30, 0.0, 1.0)
    back_flow /= np.linalg.norm(back_flow, axis=1, keepdims=True)

    face_blend = np.clip((s_coord - 0.65) / 0.22, 0.0, 1.0)[:, None]
    raw_flow = (1.0 - face_blend) * back_flow + face_blend * vec_from_nose
    raw_flow /= np.maximum(np.linalg.norm(raw_flow, axis=1, keepdims=True), 1e-6)

    # Project flow vector onto surface tangent plane + slight natural lift angle
    dot_fn = np.sum(raw_flow * root_normals, axis=1, keepdims=True)
    tangent_flow = raw_flow - dot_fn * root_normals
    tangent_flow /= np.maximum(np.linalg.norm(tangent_flow, axis=1, keepdims=True), 1e-6)

    # Belly hairs lie flatter; dorsal guard hairs & ruff lift slightly more for plush silhouette
    belly_flatness = np.clip((roots[:, 2] - 0.008) / 0.018, 0.15, 1.0)[:, None]
    lift = (0.34 if layer_type == "undercoat" else (0.28 if layer_type == "guard_hairs" else 0.22)) * belly_flatness
    comb_dir = tangent_flow * np.sqrt(1.0 - lift ** 2) + root_normals * lift
    comb_dir /= np.maximum(np.linalg.norm(comb_dir, axis=1, keepdims=True), 1e-6)

    # Natural length variation across body (shorter near muzzle/paws, plush on haunches/shoulders)
    anatomical_len_scale = np.clip(0.35 + 0.85 * (1.0 - np.clip((s_coord - 0.65) / 0.35, 0.0, 0.75)), 0.30, 1.15)
    if layer_type == "face_fur":
        # Tapers smoothly down to 0.9 mm fine vellus hairs right around the pink nose pad
        anatomical_len_scale = np.clip(0.32 + 0.78 * (1.0 - np.clip((s_coord - 0.72) / 0.28, 0.0, 0.72)), 0.28, 1.15)

    strand_lengths = base_len * anatomical_len_scale * rng.uniform(0.78, 1.24, size=n_strands).astype(np.float32)

    # Multi-scale Guide-strand Clumping:
    #   - Primary 3.2 mm coat locks + Secondary 1.5 mm micro-tufts so flank fur breaks up naturally
    cell_size = 0.0032 if layer_type != "face_fur" else 0.0015
    sub_cell_size = 0.0014 if layer_type != "face_fur" else 0.0008
    cell_keys = np.floor(roots / cell_size).astype(np.int32)
    cell_hash = (cell_keys[:, 0] * 73856093) ^ (cell_keys[:, 1] * 19349663) ^ (cell_keys[:, 2] * 83492791)
    clump_center = (np.floor(roots / cell_size) + 0.5) * cell_size
    sub_clump_center = (np.floor(roots / sub_cell_size) + 0.5) * sub_cell_size
    # Project clump pull onto surface tangent so clumping never pulls roots inside the skin
    to_clump = 0.68 * (clump_center - roots) + 0.32 * (sub_clump_center - roots)
    to_clump -= np.sum(to_clump * root_normals, axis=1, keepdims=True) * root_normals

    # Build 6 control points per spline (t in 0..1)
    t_vals = np.linspace(0.0, 1.0, pts_per_curve, dtype=np.float32)[None, :, None]  # (1, P, 1)
    roots_exp = roots[:, None, :]
    norm_exp = root_normals[:, None, :]
    comb_exp = comb_dir[:, None, :]
    len_exp = strand_lengths[:, None, None]

    # Orthogonal tangent frame (u_vec, v_vec) for 3D curl/wave & frizz
    up_ref = np.zeros_like(comb_dir)
    up_ref[:, 2] = 1.0
    u_vec = np.cross(comb_dir, up_ref)
    u_norm = np.linalg.norm(u_vec, axis=1, keepdims=True)
    fallback = np.zeros_like(comb_dir)
    fallback[:, 0] = 1.0
    u_vec = np.where(u_norm > 1e-4, u_vec / np.maximum(u_norm, 1e-4), np.cross(comb_dir, fallback))
    v_vec = np.cross(comb_dir, u_vec)

    phase = (cell_hash % 6283).astype(np.float32)[:, None, None] * 0.001 + rng.uniform(0.0, 1.8, size=(n_strands, 1, 1)).astype(np.float32)
    freq = 2.2 * math.pi
    wave_u = curl_amp * np.sin(freq * t_vals + phase) * (t_vals ** 0.85)
    wave_v = curl_amp * np.cos(freq * t_vals + phase) * (t_vals ** 0.85)

    # Slight gravity bend + curve toward clump center as t -> 1
    gravity = np.array([[[0.0, -0.0012, -0.0018]]], dtype=np.float32) * (t_vals ** 1.8)
    clump_offset = to_clump[:, None, :] * (clump_amt * (t_vals ** 0.75))

    # Tip splay/flyaway on 12% of guard hairs for organic realism
    flyaway = rng.normal(0.0, 0.00045, size=(n_strands, 1, 3)).astype(np.float32) * (t_vals ** 1.6)

    #Sink root 0.3 mm inside skin so no roots ever float
    root_embed = -0.0003 * norm_exp * (1.0 - np.clip(t_vals * 4.0, 0.0, 1.0))

    curve_pts = (
        roots_exp
        + root_embed
        + comb_exp * (len_exp * t_vals)
        + clump_offset
        + u_vec[:, None, :] * wave_u
        + v_vec[:, None, :] * wave_v
        + gravity
        + flyaway
    )  # shape: (n_strands, pts_per_curve, 3)

    # Taper radius from root (100%) to fine tip (8% for guard/face, 14% for undercoat)
    tip_ratio = 0.08 if layer_type != "undercoat" else 0.14
    radius_jitter = rng.uniform(0.84, 1.18, size=(n_strands, 1)).astype(np.float32)
    t_1d = np.linspace(0.0, 1.0, pts_per_curve, dtype=np.float32)[None, :]
    radii = (base_radius * radius_jitter) * ((1.0 - (1.0 - tip_ratio) * (t_1d ** 0.85)))

    # Compute per-curve `coat_zone` (0 = golden dorsal back, 1 = creamy-white ventral belly/lower jaw/muzzle pads)
    # Matching reference 32N6IKR3OOH6.jpg: creamy-white fur extends up around the lower muzzle pads & eye rings
    border_noise = 0.0045 * np.sin(roots[:, 1] * 85.0 + roots[:, 0] * 60.0)
    muzzle_cream_lift = 0.014 * np.clip((s_coord - 0.80) / 0.20, 0.0, 1.0)
    belly_line_z = 0.022 + 0.004 * s_coord + muzzle_cream_lift + border_noise
    coat_zone = np.clip((belly_line_z - roots[:, 2]) / 0.011, 0.0, 1.0).astype(np.float32)
    # Subtle pale cream ring around each eye (32N6IKR3OOH6.jpg)
    eye_l_pos = np.array([[0.0225, 0.0505, 0.0448]], dtype=np.float32)
    eye_r_pos = np.array([[-0.0225, 0.0505, 0.0448]], dtype=np.float32)
    d_eye_min = np.minimum(np.linalg.norm(roots - eye_l_pos, axis=1), np.linalg.norm(roots - eye_r_pos, axis=1))
    eye_ring_cream = np.clip(1.0 - (d_eye_min - 0.0052) / 0.0055, 0.0, 0.78).astype(np.float32)
    coat_zone = np.maximum(coat_zone, eye_ring_cream)

    # Syrian hamster signature dark cheek flash bar & dark ear rim (`cheek_bar` attribute)
    cheek_dist = np.sqrt(((np.abs(roots[:, 0]) - 0.024) / 0.008) ** 2 + ((s_coord - 0.68) / 0.065) ** 2 + ((roots[:, 2] - 0.028) / 0.010) ** 2)
    cheek_bar = np.clip(1.0 - cheek_dist, 0.0, 1.0).astype(np.float32) * 0.88

    # Create the Blender 5.2 HairCurves object
    curves_data = bpy.data.hair_curves.new(name)
    curves_data.surface = body_obj
    curves_data.add_curves([pts_per_curve] * n_strands)
    curves_data.points.foreach_set("position", curve_pts.reshape(-1).astype(np.float32))
    curves_data.points.foreach_set("radius", radii.reshape(-1).astype(np.float32))

    attr_cz = curves_data.attributes.new("coat_zone", 'FLOAT', 'CURVE')
    attr_cz.data.foreach_set("value", coat_zone)

    attr_cb = curves_data.attributes.new("cheek_bar", 'FLOAT', 'CURVE')
    attr_cb.data.foreach_set("value", cheek_bar)

    curves_data.materials.append(mat)

    curves_obj = bpy.data.objects.new(name, curves_data)
    curves_obj.parent = body_obj
    curves_obj.matrix_parent_inverse = Matrix.Identity(4)
    link_to_collection(curves_obj, ham_col)

    # Attach the Geometry Nodes modifier (`GN_HamsterFurPreview`)
    mod = curves_obj.modifiers.new(name="GN_HamsterFurPreview", type='NODES')
    mod.node_group = gn_group
    # Set socket values if supported on this modifier instance
    for item in gn_group.interface.items_tree:
        if item.item_type == 'SOCKET' and item.in_out == 'INPUT':
            try:
                if item.name == "Viewport Preview Ratio":
                    mod[item.identifier] = float(FUR_PARAMS["viewport_preview_ratio"])
                elif item.name == "Seed":
                    mod[item.identifier] = int(layer_cfg["random_seed"])
            except TypeError:
                pass

    return curves_obj


def build_whiskers_curves(
    body_obj: bpy.types.Object,
    w_cfg: dict,
    mat: bpy.types.Material,
    ham_col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Generates long tapered mystacial & superciliary vibrissae (`ham_whiskers`) using native
    Blender 5.2 `HairCurves`.
    """
    rng = np.random.default_rng(w_cfg["random_seed"])
    n_per_side = int(w_cfg["count_per_side"])
    pts_per_curve = 8
    base_len = float(w_cfg["length"])
    base_rad = float(w_cfg["thickness"]) * 0.5
    droop = float(w_cfg["droop"])

    all_curves = []
    all_radii = []

    for sign in (1.0, -1.0):
        # 4 rows of mystacial whisker pads on each side of the wide blunt snout + 2 brow vibrissae
        for i in range(n_per_side):
            if i < n_per_side - 2:
                row = i % 4
                col = i // 4
                rx = sign * (0.0115 + 0.0025 * col + 0.0008 * row)
                ry = 0.0680 - 0.0038 * col
                rz = 0.0235 + 0.0028 * row
                w_len = base_len * (0.55 + 0.16 * col + 0.06 * row) * rng.uniform(0.90, 1.12)
                dir_vec = Vector((sign * (0.82 + 0.06 * row), 0.18 - 0.16 * col, 0.08 * (row - 1.5))).normalized()
            else:
                # Supraorbital brow whiskers above the eye
                b_idx = i - (n_per_side - 2)
                rx = sign * 0.0185
                ry = 0.0485 - 0.0025 * b_idx
                rz = 0.0475
                w_len = base_len * 0.62
                dir_vec = Vector((sign * 0.72, -0.15, 0.55)).normalized()

            root = Vector((rx, ry, rz))
            pts = []
            rads = []
            for p_idx in range(pts_per_curve):
                t = p_idx / (pts_per_curve - 1)
                arc = Vector((0.0, -0.0045 * (t ** 1.6), -droop * (t ** 1.85)))
                pt = root + dir_vec * (w_len * t) + arc
                pts.append((pt.x, pt.y, pt.z))
                rads.append(base_rad * max(0.06, 1.0 - 0.92 * (t ** 0.8)))
            all_curves.append(pts)
            all_radii.append(rads)

    total_w = len(all_curves)
    curves_data = bpy.data.hair_curves.new("ham_whiskers")
    curves_data.surface = body_obj
    curves_data.add_curves([pts_per_curve] * total_w)
    curves_data.points.foreach_set("position", np.array(all_curves, dtype=np.float32).reshape(-1))
    curves_data.points.foreach_set("radius", np.array(all_radii, dtype=np.float32).reshape(-1))
    curves_data.materials.append(mat)

    w_obj = bpy.data.objects.new("ham_whiskers", curves_data)
    w_obj.parent = body_obj
    w_obj.matrix_parent_inverse = Matrix.Identity(4)
    link_to_collection(w_obj, ham_col)
    return w_obj


# ==============================================================================
# 5. MACRO FUR TEST LIGHTING & RENDERING (SIDE-LIT, BACK-LIT, FRONT-LIT)
# ==============================================================================
def render_three_macro_fur_views() -> dict:
    """
    Renders three 1920x1080 macro views of the hamster fur system (`cam_macro_85mm`, f/4.0):
      1. `renders/tests/05_fur_side_lit.png`  : Raking side key light to reveal clumping, flow & agouti bands
      2. `renders/tests/05_fur_back_lit.png`  : Strong rim backlight to test hair transmission & ear SSS glow
      3. `renders/tests/05_fur_front_lit.png` : Soft front-three-quarter key light for facial fur, eyes & whiskers
    Returns a dict of `{view_name: render_seconds}`.
    """
    common.configure_cycles_gpu("OPTIX")
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.cycles.samples = 96
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 12
    scene.cycles.transmission_bounces = 12
    scene.cycles.transparent_max_bounces = 12

    # Use smooth 3D curve ribbons with 2 subdivisions in Cycles
    if hasattr(scene, "cycles_curves"):
        scene.cycles_curves.shape = 'RIBBONS'
        scene.cycles_curves.subdivisions = 2

    try:
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass

    # Aim `cam_macro_85mm` directly at the hamster's face, ears, whiskers & shoulder in the clearing
    # Place camera inside the cage air volume (y = -0.225, inside front acrylic wall y = -0.25)
    # so macro DoF & lighting directly evaluate the 3-layer fur without front-acrylic reflection haze
    head_focus = HAMSTER_POS + Vector((-0.036, -0.036, 0.038))
    body_center = HAMSTER_POS + Vector((-0.015, -0.015, 0.032))
    cam_loc = HAMSTER_POS + Vector((-0.245, -0.245, 0.115))

    cam_macro = bpy.data.objects.get("cam_macro_85mm")
    if not cam_macro:
        cams_col = common.get_or_create_collection("CAMERAS")
        cam_data = bpy.data.cameras.new("cam_macro_85mm")
        cam_macro = bpy.data.objects.new("cam_macro_85mm", cam_data)
        link_to_collection(cam_macro, cams_col)

    cam_macro.location = cam_loc
    look_at(cam_macro, body_center)
    cam_macro.data.lens = 65.0
    cam_macro.data.sensor_width = 36.0
    cam_macro.data.dof.use_dof = True
    cam_macro.data.dof.focus_distance = (cam_loc - head_focus).length
    cam_macro.data.dof.aperture_fstop = 8.0
    scene.camera = cam_macro

    key_obj = bpy.data.objects.get("light_window_key")
    fill_obj = bpy.data.objects.get("light_ceiling_fill")
    lamp_obj = bpy.data.objects.get("light_night_lamp")
    rim_obj = bpy.data.objects.get("light_rim_backlight")

    # Save original light transforms/energies so we restore the Day preset cleanly afterwards
    saved_lights = {}
    for l_obj in (key_obj, fill_obj, lamp_obj, rim_obj):
        if l_obj:
            saved_lights[l_obj.name] = (
                l_obj.location.copy(),
                l_obj.rotation_euler.copy(),
                l_obj.data.energy,
                tuple(l_obj.data.color),
            )

    views = [
        (
            "side_lit",
            "renders/tests/05_fur_side_lit.png",
            # Strong 90-degree raking side key from front-right + low fill for dramatic fur clump shadow contrast
            {"loc": HAMSTER_POS + Vector((0.35, -0.35, 0.28)), "energy": 34.0, "color": (1.0, 0.95, 0.86)},
            {"energy": 1.6, "color": (0.82, 0.90, 1.0)},
            {"loc": HAMSTER_POS + Vector((0.35, 0.35, 0.32)), "energy": 4.5, "color": (1.0, 0.95, 0.88)},
            0.16,  # World HDRI strength
        ),
        (
            "back_lit",
            "renders/tests/05_fur_back_lit.png",
            # Very dim front/side fill + intense warm rim backlight behind hamster to show fur halo & ear SSS translucency
            {"loc": HAMSTER_POS + Vector((-0.32, -0.32, 0.28)), "energy": 3.0, "color": (0.88, 0.93, 1.0)},
            {"energy": 1.0, "color": (0.80, 0.88, 1.0)},
            {"loc": HAMSTER_POS + Vector((0.34, 0.34, 0.24)), "energy": 72.0, "color": (1.0, 0.84, 0.62)},
            0.06,  # Dim World HDRI so backlit fur & translucent ears glow against dark background
        ),
        (
            "front_lit",
            "renders/tests/05_fur_front_lit.png",
            # Soft front key aligned near the macro camera axis + balanced fill & subtle rim
            {"loc": HAMSTER_POS + Vector((-0.36, -0.36, 0.36)), "energy": 28.0, "color": (1.0, 0.97, 0.91)},
            {"energy": 5.5, "color": (0.88, 0.94, 1.0)},
            {"loc": HAMSTER_POS + Vector((0.32, 0.32, 0.36)), "energy": 12.0, "color": (1.0, 0.95, 0.88)},
            0.35,  # Natural room HDRI fill
        ),
    ]

    bg_node = None
    if scene.world and scene.world.use_nodes:
        for n in scene.world.node_tree.nodes:
            if n.type == 'BACKGROUND':
                bg_node = n
                break
    orig_bg_strength = bg_node.inputs["Strength"].default_value if bg_node else 0.55

    render_times = {}
    for view_key, out_rel, key_cfg, fill_cfg, rim_cfg, hdri_str in views:
        if bg_node:
            bg_node.inputs["Strength"].default_value = hdri_str
        if key_obj:
            key_obj.location = key_cfg["loc"]
            look_at(key_obj, body_center)
            key_obj.data.energy = key_cfg["energy"]
            key_obj.data.color = key_cfg["color"]
        if fill_obj:
            fill_obj.data.energy = fill_cfg["energy"]
            fill_obj.data.color = fill_cfg["color"]
        if lamp_obj:
            lamp_obj.data.energy = 0.0
        if rim_obj:
            rim_obj.location = rim_cfg["loc"]
            look_at(rim_obj, body_center)
            rim_obj.data.energy = rim_cfg["energy"]
            rim_obj.data.color = rim_cfg["color"]

        abs_out = os.path.abspath(out_rel)
        os.makedirs(os.path.dirname(abs_out), exist_ok=True)
        scene.render.filepath = abs_out

        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        dt = time.perf_counter() - t0
        render_times[view_key] = dt
        print(f">> Rendered {out_rel} in {dt:.2f} seconds")

    # Restore saved Day preset lighting & HDRI strength
    if bg_node:
        bg_node.inputs["Strength"].default_value = orig_bg_strength
    for l_obj in (key_obj, fill_obj, lamp_obj, rim_obj):
        if l_obj and l_obj.name in saved_lights:
            loc, rot, nrg, col = saved_lights[l_obj.name]
            l_obj.location = loc
            l_obj.rotation_euler = rot
            l_obj.data.energy = nrg
            l_obj.data.color = col

    return render_times


def build_reference_comparison():
    """
    Per rules.md Rule 7 and Section 5 Reference Comparison prompt:
    Builds a side-by-side comparison image in `renders/compare/05_compare_with_reference.png`
    comparing our rendered hamster (`renders/tests/05_fur_front_lit.png`) on the left with
    real Syrian hamster reference photo `32N6IKR3OOH6.jpg` on the right.
    """
    ref_path = os.path.abspath(
        "reference/photos/images.cv_23mpmrt35vasncelu0dtfo/data/test/hamster/32N6IKR3OOH6.jpg"
    )
    render_path = os.path.abspath("renders/tests/05_fur_front_lit.png")
    out_path = os.path.abspath("renders/compare/05_compare_with_reference.png")
    if not (os.path.exists(ref_path) and os.path.exists(render_path)):
        return

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    panel_w, panel_h = 960, 720
    pad = 8
    total_w = panel_w * 2 + pad * 3
    total_h = panel_h + pad * 2

    canvas = np.full((total_h, total_w, 4), 0.08, dtype=np.float32)
    canvas[:, :, 3] = 1.0

    for idx, fpath in enumerate((render_path, ref_path)):
        img = bpy.data.images.load(fpath, check_existing=False)
        img.scale(panel_w, panel_h)
        px = np.empty(panel_w * panel_h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        arr = px.reshape((panel_h, panel_w, 4))
        x0 = pad + idx * (panel_w + pad)
        canvas[pad:pad + panel_h, x0:x0 + panel_w, :] = arr
        bpy.data.images.remove(img)

    out_img = bpy.data.images.new("CompareSideBySide", width=total_w, height=total_h, alpha=True)
    out_img.pixels.foreach_set(canvas.ravel())
    out_img.filepath_raw = out_path
    out_img.file_format = 'PNG'
    out_img.save()
    bpy.data.images.remove(out_img)
    print(f">> Saved side-by-side reference comparison: {out_path}")


def configure_viewport_for_gui():
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


def main():
    print("\n" + "=" * 72)
    print(f" HAMMY PIPELINE — PROMPT 5: 3-LAYER FUR SYSTEM (Blender {bpy.app.version_string})")
    print("=" * 72)

    scene_path = os.path.abspath("blender/scene.blend")
    if os.path.exists(scene_path) and "cage_tub" not in bpy.data.objects:
        bpy.ops.wm.open_mainfile(filepath=scene_path)

    # Rule 2: Save a dated backup before modifying scene.blend
    backup_path = common.save_dated_copy(base_name="scene", output_dir="blender")
    print(f">> Saved dated backup before Prompt 5: {backup_path}")

    common.set_unit_scale_metric()
    master_col = bpy.context.scene.collection
    ham_col = common.get_or_create_collection("HAMSTER", parent=master_col)

    print("1. Building anisotropic Principled Hair BSDF shaders + SSS skin & wet-cornea eye materials...")
    mats = build_hamster_materials()

    print("2. Building clearly-labelled placeholder Syrian hamster mesh (ham_body, 0.150 m) + bare ears/nose/eyes/paws...")
    body_obj = build_placeholder_hamster(ham_col, mats)

    print("3. Creating Geometry Nodes modifier group (GN_HamsterFurPreview) for low-density viewport preview...")
    gn_group = get_or_create_fur_gn_group()

    print("4. Generating 3-layer HairCurves (undercoat, guard_hairs, face_fur) + vibrissae whiskers...")
    t_gen0 = time.perf_counter()
    build_hair_layer_curves(
        "ham_fur_undercoat", body_obj, FUR_PARAMS["undercoat"], "undercoat", mats["undercoat"], gn_group, ham_col
    )
    build_hair_layer_curves(
        "ham_fur_guard_hairs", body_obj, FUR_PARAMS["guard_hairs"], "guard_hairs", mats["guard_hairs"], gn_group, ham_col
    )
    build_hair_layer_curves(
        "ham_fur_face", body_obj, FUR_PARAMS["face_fur"], "face_fur", mats["face_fur"], gn_group, ham_col
    )
    build_whiskers_curves(body_obj, FUR_PARAMS["whiskers"], mats["whiskers"], ham_col)
    print(f">> Generated 42,500 hair curves + 36 whiskers in {time.perf_counter() - t_gen0:.2f} seconds")

    print("5. Rendering 3 macro lighting views (side_lit, back_lit, front_lit)...")
    render_times = render_three_macro_fur_views()

    print("6. Building side-by-side reference comparison (renders/compare/05_compare_with_reference.png)...")
    build_reference_comparison()

    # Also save standalone hamster.blend so the hamster asset can be edited/sculpted independently
    configure_viewport_for_gui()
    bpy.ops.wm.save_as_mainfile(filepath=scene_path)
    hamster_blend_path = os.path.abspath("blender/hamster.blend")
    bpy.ops.wm.save_as_mainfile(filepath=hamster_blend_path, copy=True)

    print("\n" + "-" * 72)
    print(" PROMPT 5 RENDER TIME SUMMARY (1920x1080, Cycles OptiX GPU, 96 samples):")
    for k, sec in render_times.items():
        print(f"   * 05_fur_{k}.png : {sec:.2f} s")
    print("-" * 72 + "\n")


if __name__ == "__main__":
    main()
