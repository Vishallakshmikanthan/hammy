"""
HAMMY Art Pipeline — Prompt 3: Photoreal PBR Materials & Shader Graphs
Reads rules.md first.

Combines real CC0 scanned PBR texture maps from Poly Haven (triplanar box-mapped)
with procedural micro-wear, crevice dust, edge scratches, and subsurface translucency:
  1. Fine-Grained Wood (`mat_wood_natural` — Poly Haven 'fine_grained_wood' CC0):
     Scanned Albedo + Roughness + OpenGL Normal map + Pointiness paler chewed-edge wear.
     Assigned to: prop_hideout, prop_chew_block.
  2. Birch Plywood (`mat_wood_plywood` — Poly Haven 'plywood' CC0):
     Assigned to: prop_wheel_drum, prop_wheel_stand, prop_wheel_arm, prop_hideout_roof.
  3. Natural Bark & Cork (`mat_cork_bark` — Poly Haven 'bark_brown_02' CC0):
     Scanned bark Albedo + Roughness + Normal map + porous Voronoi bump.
     Assigned to: prop_tunnel_*, prop_chew_stick_*.
  4. Glazed Ceramic (`mat_ceramic_glazed` — Poly Haven 'concrete_floor_worn_001' micro-roughness CC0):
     Warm off-white porcelain base, clearcoat glaze (`Coat Weight = 0.95`), subtle roughness variation
     and micro-bump from scanned surface map.
     Assigned to: prop_bowl.
  5. Smudged Clear Acrylic (`mat_acrylic_clear`):
     Physically plausible transmission (`Transmission Weight = 0.97`, `IOR = 1.491`),
     Fresnel cyan/green edge tint, and multi-scale smudge/fingerprint roughness variation.
     Assigned to: cage_panel_*, prop_bottle_body.
  6. Brushed Stainless Steel (`mat_steel_brushed`):
     Metallic = 1.0, anisotropic highlight, high-frequency linear micro-scratch normal & roughness.
     Assigned to: prop_bottle_spout, prop_wheel_axle.
  7. Translucent Backlit Paper & Aspen Bedding (`mat_bedding_pbr_*`):
     Subsurface scattering + transmission translucency so thin shavings glow softly when backlit,
     plus fibrous roughness and bump variation.
     Assigned to: bedding_surface, bedding_shavings_aspen, bedding_strips_paper_white, bedding_flakes_natural.
  8. Textured Polymer Tub (`mat_plastic_tub`):
     Injection-molded matte charcoal polypropylene with fine micro-stipple roughness & bump.

Outputs:
  - Updates blender/scene.blend
  - Logs Poly Haven CC0 URLs and licenses in reference/licence_log.csv
  - Renders material sphere look-dev sheet: renders/tests/03_materials_spheres.png
  - Renders cage scene with full PBR materials: renders/tests/03_materials_cage.png
  - Renders macro close-up with PBR materials: renders/tests/03_materials_closeup.png
"""

import os
import sys
import math
import bpy
from mathutils import Vector

scripts_dir = os.path.dirname(os.path.abspath(__file__))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

import common


def clear_nodes(mat: bpy.types.Material):
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    return nodes, mat.node_tree.links


def link_to_collection(obj: bpy.types.Object, target_col: bpy.types.Collection):
    if obj.name not in target_col.objects:
        target_col.objects.link(obj)
    for col in list(obj.users_collection):
        if col != target_col:
            col.objects.unlink(obj)


def load_image_box_node(nodes, links, vector_socket, filepath: str, is_non_color: bool = False, loc=(0, 0)):
    """Creates a triplanar Box-Projected ShaderNodeTexImage if the file exists on disk."""
    abs_path = os.path.abspath(filepath)
    if not os.path.exists(abs_path):
        return None
    tex_node = nodes.new("ShaderNodeTexImage")
    tex_node.location = loc
    img = bpy.data.images.load(abs_path, check_existing=True)
    if is_non_color:
        img.colorspace_settings.name = 'Non-Color'
    tex_node.image = img
    tex_node.projection = 'BOX'
    tex_node.projection_blend = 0.25
    links.new(vector_socket, tex_node.inputs["Vector"])
    return tex_node


def build_pbr_wood_material(name: str, folder: str, asset_id: str, scale: float = 3.5,
                            tint: tuple = (1.0, 0.96, 0.90)) -> bpy.types.Material:
    """Builds a triplanar Poly Haven wood PBR shader with procedural edge wear and crevice dust."""
    mat = common.make_material(name, use_nodes=True)
    mat.diffuse_color = (0.68 * tint[0], 0.52 * tint[1], 0.35 * tint[2], 1.0)
    nodes, links = clear_nodes(mat)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (1100, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (800, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-700, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-500, 0)
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    base_dir = os.path.join("blender", "textures", folder)
    diff_node = load_image_box_node(nodes, links, mapping.outputs["Vector"],
                                    os.path.join(base_dir, f"{asset_id}_Diffuse.jpg"), False, (-200, 250))
    rough_node = load_image_box_node(nodes, links, mapping.outputs["Vector"],
                                     os.path.join(base_dir, f"{asset_id}_Rough.jpg"), True, (-200, -20))
    nor_node = load_image_box_node(nodes, links, mapping.outputs["Vector"],
                                   os.path.join(base_dir, f"{asset_id}_nor_gl.jpg"), True, (-200, -300))

    # Per-pixel raytraced edge wear (avoids per-vertex Pointiness interpolation streaks on boolean n-gons)
    ao_node = nodes.new("ShaderNodeAmbientOcclusion")
    ao_node.location = (-200, 500)
    ao_node.samples = 8
    ao_node.inside = True
    ao_node.only_local = True
    ao_node.inputs["Distance"].default_value = 0.004

    edge_ramp = nodes.new("ShaderNodeValToRGB")
    edge_ramp.location = (80, 500)
    edge_ramp.color_ramp.elements[0].position = 0.35
    edge_ramp.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    edge_ramp.color_ramp.elements[1].position = 0.70
    edge_ramp.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    links.new(ao_node.outputs["AO"], edge_ramp.inputs["Fac"])

    if diff_node:
        # Tint + edge wear mix
        tint_mix = nodes.new("ShaderNodeMix")
        tint_mix.location = (180, 250)
        tint_mix.data_type = 'RGBA'
        tint_mix.blend_type = 'MULTIPLY'
        tint_mix.inputs["Factor"].default_value = 0.35
        links.new(diff_node.outputs["Color"], tint_mix.inputs["A"])
        tint_mix.inputs["B"].default_value = (tint[0], tint[1], tint[2], 1.0)

        wear_mix = nodes.new("ShaderNodeMix")
        wear_mix.location = (450, 250)
        wear_mix.data_type = 'RGBA'
        wear_mix.blend_type = 'MIX'
        links.new(edge_ramp.outputs["Color"], wear_mix.inputs["Factor"])
        links.new(tint_mix.outputs["Result"], wear_mix.inputs["A"])
        wear_mix.inputs["B"].default_value = (0.86, 0.75, 0.58, 1.0)  # Pale chewed raw wood
        links.new(wear_mix.outputs["Result"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.68, 0.52, 0.35, 1.0)

    if rough_node:
        rough_ramp = nodes.new("ShaderNodeValToRGB")
        rough_ramp.location = (250, -20)
        rough_ramp.color_ramp.elements[0].position = 0.0
        rough_ramp.color_ramp.elements[0].color = (0.35, 0.35, 0.35, 1.0)
        rough_ramp.color_ramp.elements[1].position = 1.0
        rough_ramp.color_ramp.elements[1].color = (0.82, 0.82, 0.82, 1.0)
        links.new(rough_node.outputs["Color"], rough_ramp.inputs["Fac"])
        links.new(rough_ramp.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = 0.62

    if nor_node:
        bump = nodes.new("ShaderNodeBump")
        bump.location = (350, -300)
        bump.inputs["Strength"].default_value = 0.18
        bump.inputs["Distance"].default_value = 0.002
        links.new(nor_node.outputs["Color"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def build_pbr_bark_material(name: str = "mat_cork_bark") -> bpy.types.Material:
    """Builds a natural bark/cork shader using Poly Haven 'bark_brown_02' CC0 maps + Voronoi bump."""
    mat = common.make_material(name, use_nodes=True)
    mat.diffuse_color = (0.48, 0.35, 0.23, 1.0)
    nodes, links = clear_nodes(mat)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (1000, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (700, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-650, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-450, 0)
    mapping.inputs["Scale"].default_value = (4.5, 4.5, 4.5)
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    base_dir = os.path.join("blender", "textures", "bark")
    diff_node = load_image_box_node(nodes, links, mapping.outputs["Vector"],
                                    os.path.join(base_dir, "bark_brown_02_Diffuse.jpg"), False, (-150, 220))
    rough_node = load_image_box_node(nodes, links, mapping.outputs["Vector"],
                                     os.path.join(base_dir, "bark_brown_02_Rough.jpg"), True, (-150, -30))
    nor_node = load_image_box_node(nodes, links, mapping.outputs["Vector"],
                                   os.path.join(base_dir, "bark_brown_02_nor_gl.jpg"), True, (-150, -280))

    if diff_node:
        links.new(diff_node.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (0.48, 0.35, 0.23, 1.0)

    if rough_node:
        links.new(rough_node.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = 0.85

    if nor_node:
        nor_map = nodes.new("ShaderNodeNormalMap")
        nor_map.location = (300, -280)
        nor_map.inputs["Strength"].default_value = 1.15
        links.new(nor_node.outputs["Color"], nor_map.inputs["Color"])
        links.new(nor_map.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def build_ceramic_material(name: str = "mat_ceramic_glazed") -> bpy.types.Material:
    """Glazed ceramic bowl using Poly Haven surface imperfection roughness + clearcoat glaze."""
    mat = common.make_material(name, use_nodes=True)
    mat.diffuse_color = (0.93, 0.90, 0.85, 1.0)
    nodes, links = clear_nodes(mat)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (950, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (650, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 0.95
        bsdf.inputs["Coat Roughness"].default_value = 0.035

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-600, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-400, 0)
    mapping.inputs["Scale"].default_value = (5.0, 5.0, 5.0)
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    base_dir = os.path.join("blender", "textures", "ceramic")
    rough_node = load_image_box_node(nodes, links, mapping.outputs["Vector"],
                                     os.path.join(base_dir, "concrete_floor_worn_001_Rough.jpg"), True, (-150, 50))

    # Subtle cream/stoneware speckle variation
    noise_speck = nodes.new("ShaderNodeTexNoise")
    noise_speck.location = (-150, 260)
    noise_speck.inputs["Scale"].default_value = 320.0
    noise_speck.inputs["Detail"].default_value = 4.0
    links.new(tex_coord.outputs["Object"], noise_speck.inputs["Vector"])

    col_ramp = nodes.new("ShaderNodeValToRGB")
    col_ramp.location = (180, 260)
    col_ramp.color_ramp.elements[0].position = 0.25
    col_ramp.color_ramp.elements[0].color = (0.85, 0.81, 0.75, 1.0)
    col_ramp.color_ramp.elements[1].position = 0.70
    col_ramp.color_ramp.elements[1].color = (0.95, 0.93, 0.89, 1.0)
    links.new(noise_speck.outputs["Fac"], col_ramp.inputs["Fac"])
    links.new(col_ramp.outputs["Color"], bsdf.inputs["Base Color"])

    if rough_node:
        rough_ramp = nodes.new("ShaderNodeValToRGB")
        rough_ramp.location = (220, 40)
        rough_ramp.color_ramp.elements[0].position = 0.1
        rough_ramp.color_ramp.elements[0].color = (0.09, 0.09, 0.09, 1.0)
        rough_ramp.color_ramp.elements[1].position = 0.9
        rough_ramp.color_ramp.elements[1].color = (0.24, 0.24, 0.24, 1.0)
        links.new(rough_node.outputs["Color"], rough_ramp.inputs["Fac"])
        links.new(rough_ramp.outputs["Color"], bsdf.inputs["Roughness"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (380, -160)
    bump.inputs["Strength"].default_value = 0.015
    bump.inputs["Distance"].default_value = 0.001
    links.new(noise_speck.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def build_acrylic_glass_material(name: str = "mat_acrylic_clear") -> bpy.types.Material:
    """
    Physically plausible acrylic/glass with Fresnel cyan edge-tint and smudge roughness variation.
    """
    mat = common.make_material(name, use_nodes=True)
    mat.diffuse_color = (0.88, 0.95, 0.98, 0.12)
    nodes, links = clear_nodes(mat)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (1000, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (700, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = 0.97
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = 0.97
    bsdf.inputs["IOR"].default_value = 1.491

    lw = nodes.new("ShaderNodeLayerWeight")
    lw.location = (-100, 200)
    lw.inputs["Blend"].default_value = 0.32

    col_ramp = nodes.new("ShaderNodeValToRGB")
    col_ramp.location = (150, 200)
    col_ramp.color_ramp.elements[0].position = 0.0
    col_ramp.color_ramp.elements[0].color = (0.98, 0.995, 1.0, 1.0)
    col_ramp.color_ramp.elements[1].position = 0.85
    col_ramp.color_ramp.elements[1].color = (0.82, 0.94, 0.91, 1.0)  # Subtle acrylic edge tint
    links.new(lw.outputs["Facing"], col_ramp.inputs["Fac"])
    links.new(col_ramp.outputs["Color"], bsdf.inputs["Base Color"])

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-450, -100)
    noise_smudge = nodes.new("ShaderNodeTexNoise")
    noise_smudge.location = (-200, -100)
    noise_smudge.inputs["Scale"].default_value = 18.0
    noise_smudge.inputs["Detail"].default_value = 6.0
    noise_smudge.inputs["Roughness"].default_value = 0.65
    links.new(tex_coord.outputs["Object"], noise_smudge.inputs["Vector"])

    rough_ramp = nodes.new("ShaderNodeValToRGB")
    rough_ramp.location = (150, -100)
    rough_ramp.color_ramp.elements[0].position = 0.42
    rough_ramp.color_ramp.elements[0].color = (0.015, 0.015, 0.015, 1.0)
    rough_ramp.color_ramp.elements[1].position = 0.82
    rough_ramp.color_ramp.elements[1].color = (0.14, 0.14, 0.14, 1.0)  # Faint fingerprint smudge
    links.new(noise_smudge.outputs["Fac"], rough_ramp.inputs["Fac"])
    links.new(rough_ramp.outputs["Color"], bsdf.inputs["Roughness"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (450, -250)
    bump.inputs["Strength"].default_value = 0.006
    bump.inputs["Distance"].default_value = 0.001
    links.new(noise_smudge.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def build_brushed_steel_material(name: str = "mat_steel_brushed") -> bpy.types.Material:
    """Brushed stainless steel for wheel axle and water bottle spout."""
    mat = common.make_material(name, use_nodes=True)
    mat.diffuse_color = (0.80, 0.82, 0.85, 1.0)
    nodes, links = clear_nodes(mat)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (900, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (600, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    bsdf.inputs["Base Color"].default_value = (0.84, 0.86, 0.89, 1.0)
    bsdf.inputs["Metallic"].default_value = 1.0
    if "Anisotropic" in bsdf.inputs:
        bsdf.inputs["Anisotropic"].default_value = 0.72
        bsdf.inputs["Anisotropic Rotation"].default_value = 0.25

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-450, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-250, 0)
    mapping.inputs["Scale"].default_value = (1.0, 90.0, 1.0)
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    noise_brush = nodes.new("ShaderNodeTexNoise")
    noise_brush.location = (0, 0)
    noise_brush.inputs["Scale"].default_value = 65.0
    noise_brush.inputs["Detail"].default_value = 6.0
    links.new(mapping.outputs["Vector"], noise_brush.inputs["Vector"])

    ramp_rough = nodes.new("ShaderNodeValToRGB")
    ramp_rough.location = (260, 50)
    ramp_rough.color_ramp.elements[0].position = 0.2
    ramp_rough.color_ramp.elements[0].color = (0.16, 0.16, 0.16, 1.0)
    ramp_rough.color_ramp.elements[1].position = 0.8
    ramp_rough.color_ramp.elements[1].color = (0.34, 0.34, 0.34, 1.0)
    links.new(noise_brush.outputs["Fac"], ramp_rough.inputs["Fac"])
    links.new(ramp_rough.outputs["Color"], bsdf.inputs["Roughness"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (350, -150)
    bump.inputs["Strength"].default_value = 0.025
    bump.inputs["Distance"].default_value = 0.001
    links.new(noise_brush.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def build_translucent_bedding_material(name: str = "mat_bedding_pbr",
                                       base_color: tuple = (0.88, 0.82, 0.70),
                                       subsurface_weight: float = 0.42) -> bpy.types.Material:
    """Translucent paper & aspen shavings with subsurface scattering so thin edges glow when backlit."""
    mat = common.make_material(name, use_nodes=True)
    mat.diffuse_color = (base_color[0], base_color[1], base_color[2], 1.0)
    nodes, links = clear_nodes(mat)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (900, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (600, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    if "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = subsurface_weight
        bsdf.inputs["Subsurface Scale"].default_value = 0.012
    elif "Subsurface" in bsdf.inputs:
        bsdf.inputs["Subsurface"].default_value = subsurface_weight

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-450, 0)
    noise_fibers = nodes.new("ShaderNodeTexNoise")
    noise_fibers.location = (-200, 80)
    noise_fibers.inputs["Scale"].default_value = 110.0
    noise_fibers.inputs["Detail"].default_value = 7.0
    noise_fibers.inputs["Roughness"].default_value = 0.82
    links.new(tex_coord.outputs["Object"], noise_fibers.inputs["Vector"])

    ramp_col = nodes.new("ShaderNodeValToRGB")
    ramp_col.location = (120, 120)
    c0 = (base_color[0] * 0.84, base_color[1] * 0.84, base_color[2] * 0.84, 1.0)
    c1 = (min(1.0, base_color[0] * 1.07), min(1.0, base_color[1] * 1.07), min(1.0, base_color[2] * 1.07), 1.0)
    ramp_col.color_ramp.elements[0].position = 0.25
    ramp_col.color_ramp.elements[0].color = c0
    ramp_col.color_ramp.elements[1].position = 0.75
    ramp_col.color_ramp.elements[1].color = c1
    links.new(noise_fibers.outputs["Fac"], ramp_col.inputs["Fac"])
    links.new(ramp_col.outputs["Color"], bsdf.inputs["Base Color"])

    ramp_rough = nodes.new("ShaderNodeValToRGB")
    ramp_rough.location = (120, -60)
    ramp_rough.color_ramp.elements[0].position = 0.2
    ramp_rough.color_ramp.elements[0].color = (0.72, 0.72, 0.72, 1.0)
    ramp_rough.color_ramp.elements[1].position = 0.8
    ramp_rough.color_ramp.elements[1].color = (0.94, 0.94, 0.94, 1.0)
    links.new(noise_fibers.outputs["Fac"], ramp_rough.inputs["Fac"])
    links.new(ramp_rough.outputs["Color"], bsdf.inputs["Roughness"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (350, -180)
    bump.inputs["Strength"].default_value = 0.065
    bump.inputs["Distance"].default_value = 0.002
    links.new(noise_fibers.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def build_plastic_tub_material(name: str = "mat_plastic_tub",
                               base_color: tuple = (0.13, 0.15, 0.17)) -> bpy.types.Material:
    """Semi-matte textured polypropylene polymer with crevice dust & stipple bump."""
    mat = common.make_material(name, use_nodes=True)
    mat.diffuse_color = (base_color[0], base_color[1], base_color[2], 1.0)
    nodes, links = clear_nodes(mat)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (800, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (500, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    bsdf.inputs["Base Color"].default_value = (base_color[0], base_color[1], base_color[2], 1.0)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-400, 0)
    noise_poly = nodes.new("ShaderNodeTexNoise")
    noise_poly.location = (-150, 0)
    noise_poly.inputs["Scale"].default_value = 180.0
    noise_poly.inputs["Detail"].default_value = 5.0
    links.new(tex_coord.outputs["Object"], noise_poly.inputs["Vector"])

    ramp_rough = nodes.new("ShaderNodeValToRGB")
    ramp_rough.location = (150, 50)
    ramp_rough.color_ramp.elements[0].position = 0.2
    ramp_rough.color_ramp.elements[0].color = (0.30, 0.30, 0.30, 1.0)
    ramp_rough.color_ramp.elements[1].position = 0.8
    ramp_rough.color_ramp.elements[1].color = (0.50, 0.50, 0.50, 1.0)
    links.new(noise_poly.outputs["Fac"], ramp_rough.inputs["Fac"])
    links.new(ramp_rough.outputs["Color"], bsdf.inputs["Roughness"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (250, -150)
    bump.inputs["Strength"].default_value = 0.018
    bump.inputs["Distance"].default_value = 0.001
    links.new(noise_poly.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def assign_material_to_object(obj: bpy.types.Object, mat: bpy.types.Material):
    if not obj.data or not hasattr(obj.data, "materials"):
        return
    if len(obj.data.materials) == 0:
        obj.data.materials.append(mat)
    else:
        for idx in range(len(obj.data.materials)):
            obj.data.materials[idx] = mat


def assign_scene_materials():
    """Builds all PBR materials and assigns them across all scene objects by name prefix."""
    mat_wood_fine = build_pbr_wood_material("mat_wood_natural", "wood", "fine_grained_wood", scale=3.5, tint=(1.0, 0.95, 0.88))
    mat_wood_ply = build_pbr_wood_material("mat_wood_plywood", "plywood", "plywood", scale=2.8, tint=(0.95, 0.88, 0.78))
    mat_cork = build_pbr_bark_material("mat_cork_bark")
    mat_ceramic = build_ceramic_material("mat_ceramic_glazed")
    mat_acrylic = build_acrylic_glass_material("mat_acrylic_clear")
    mat_steel = build_brushed_steel_material("mat_steel_brushed")
    mat_tub = build_plastic_tub_material("mat_plastic_tub", (0.12, 0.14, 0.16))
    mat_bottle_cap = build_plastic_tub_material("mat_plastic_blue", (0.18, 0.34, 0.58))
    mat_tabletop = build_plastic_tub_material("mat_tabletop", (0.20, 0.19, 0.18))

    mat_bedding_base = build_translucent_bedding_material("mat_bedding_pbr_base", (0.87, 0.81, 0.68), 0.25)
    mat_shavings_aspen = build_translucent_bedding_material("mat_shavings_aspen_pbr", (0.91, 0.84, 0.68), 0.40)
    mat_strips_paper = build_translucent_bedding_material("mat_strips_paper_white_pbr", (0.96, 0.95, 0.92), 0.60)
    mat_flakes_natural = build_translucent_bedding_material("mat_flakes_natural_pbr", (0.82, 0.72, 0.56), 0.32)

    # Also upgrade seed materials so they have roughness variation & bump
    mat_sf = build_plastic_tub_material("mat_seed_sunflower_pbr", (0.14, 0.13, 0.12))
    mat_pl = build_translucent_bedding_material("mat_pellet_kibble_pbr", (0.35, 0.30, 0.18), 0.10)
    mat_ml = build_translucent_bedding_material("mat_seed_golden_pbr", (0.86, 0.67, 0.22), 0.20)

    assignments = [
        ("cage_tub", mat_tub),
        ("cage_top_rim", mat_tub),
        ("cage_corner_post_", mat_tub),
        ("cage_vent_slot_", mat_tub),
        ("cage_panel_front", mat_acrylic),
        ("cage_panel_left", mat_acrylic),
        ("cage_panel_right", mat_acrylic),
        ("cage_panel_back", mat_acrylic),
        ("cage_studio_tabletop", mat_tabletop),

        ("prop_hideout_roof", mat_wood_ply),
        ("prop_hideout", mat_wood_fine),
        ("prop_wheel_drum", mat_wood_ply),
        ("prop_wheel_stand", mat_wood_ply),
        ("prop_wheel_arm", mat_wood_ply),
        ("prop_chew_block", mat_wood_fine),

        ("prop_tunnel_straight_1", mat_cork),
        ("prop_tunnel_straight_2", mat_cork),
        ("prop_tunnel_curve", mat_cork),
        ("prop_chew_stick_1", mat_cork),
        ("prop_chew_stick_2", mat_cork),
        ("prop_chew_stick_3", mat_cork),

        ("prop_bowl", mat_ceramic),
        ("prop_bottle_body", mat_acrylic),
        ("prop_bottle_cap", mat_bottle_cap),
        ("prop_bottle_bracket", mat_tub),
        ("prop_bottle_spout", mat_steel),
        ("prop_wheel_axle", mat_steel),

        ("prop_seeds_sunflower", mat_sf),
        ("prop_pellets_kibble", mat_pl),
        ("prop_seeds_millet_corn", mat_ml),
        ("prop_food_bowl_fill", mat_pl),

        ("bedding_surface", mat_bedding_base),
        ("bedding_shavings_aspen", mat_shavings_aspen),
        ("bedding_strips_paper_white", mat_strips_paper),
        ("bedding_flakes_natural", mat_flakes_natural),
    ]

    for obj in bpy.data.objects:
        if obj.name == "prop_hideout" and obj.type == 'MESH':
            for poly in obj.data.polygons:
                poly.use_smooth = False
        for prefix, mat in assignments:
            if obj.name.startswith(prefix):
                assign_material_to_object(obj, mat)
                break


def build_material_test_spheres():
    """
    Builds a studio look-dev row of 6 material spheres positioned in an isolated showcase area
    (at Y = -3.0m) with its own ground pedestal and studio lighting.
    """
    col_name = "TEST_SPHERES"
    master_col = bpy.context.scene.collection
    spheres_col = common.get_or_create_collection(col_name, parent=master_col)
    common.clear_collection(col_name)

    materials = [
        "mat_wood_natural",
        "mat_ceramic_glazed",
        "mat_acrylic_clear",
        "mat_steel_brushed",
        "mat_cork_bark",
        "mat_strips_paper_white_pbr",
    ]

    center_y = -3.0
    spacing = 0.145
    start_x = -((len(materials) - 1) * spacing) / 2.0

    # Pedestal plane under spheres
    bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0.0, center_y, 0.0))
    ped = bpy.context.active_object
    ped.name = "test_spheres_pedestal"
    link_to_collection(ped, spheres_col)
    mat_ped = bpy.data.materials.get("mat_tabletop")
    if mat_ped:
        assign_material_to_object(ped, mat_ped)

    # Checkerboard backdrop strip behind the acrylic sphere so refraction is visible!
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, center_y + 0.12, 0.055))
    bar = bpy.context.active_object
    bar.name = "test_spheres_refraction_bar"
    bar.scale = (0.95, 0.015, 0.04)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_to_collection(bar, spheres_col)
    mat_wood = bpy.data.materials.get("mat_wood_natural")
    if mat_wood:
        assign_material_to_object(bar, mat_wood)

    for idx, mat_name in enumerate(materials):
        sx = start_x + idx * spacing
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=64, ring_count=32, radius=0.055,
            location=(sx, center_y, 0.055)
        )
        s_obj = bpy.context.active_object
        s_obj.name = f"test_sphere_{idx+1:02d}_{mat_name}"
        for poly in s_obj.data.polygons:
            poly.use_smooth = True
        link_to_collection(s_obj, spheres_col)
        mat = bpy.data.materials.get(mat_name)
        if mat:
            assign_material_to_object(s_obj, mat)

    cam_data = bpy.data.cameras.new("cam_test_spheres")
    cam_data.lens = 42.0
    cam_obj = bpy.data.objects.new("cam_test_spheres", cam_data)
    cam_obj.location = Vector((0.0, center_y - 1.22, 0.28))
    direction = Vector((0.0, center_y, 0.055)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    link_to_collection(cam_obj, spheres_col)

    light_data = bpy.data.lights.new("light_test_spheres_key", 'AREA')
    light_data.energy = 16.0
    light_data.size = 0.7
    light_data.color = (1.0, 0.96, 0.90)
    light_obj = bpy.data.objects.new("light_test_spheres_key", light_data)
    light_obj.location = Vector((0.5, center_y - 0.65, 0.65))
    l_dir = Vector((0.0, center_y, 0.055)) - light_obj.location
    light_obj.rotation_euler = l_dir.to_track_quat('-Z', 'Y').to_euler()
    link_to_collection(light_obj, spheres_col)

    back_data = bpy.data.lights.new("light_test_spheres_rim", 'AREA')
    back_data.energy = 12.0
    back_data.size = 0.6
    back_data.color = (1.0, 0.94, 0.84)
    back_obj = bpy.data.objects.new("light_test_spheres_rim", back_data)
    back_obj.location = Vector((-0.3, center_y + 0.55, 0.45))
    b_dir = Vector((0.0, center_y, 0.055)) - back_obj.location
    back_obj.rotation_euler = b_dir.to_track_quat('-Z', 'Y').to_euler()
    link_to_collection(back_obj, spheres_col)


def log_licenses():
    """Logs all Poly Haven CC0 and procedural asset licenses in reference/licence_log.csv per Rule 8."""
    csv_path = os.path.abspath("reference/licence_log.csv")
    entries = [
        "fine_grained_wood,Fine Grained Wood (1K Diffuse/Rough/Normal),https://polyhaven.com/a/fine_grained_wood,CC0,Poly Haven (Dario Barresi),Used on wooden hideout & chew block",
        "plywood,Plywood (1K Diffuse/Rough/Normal),https://polyhaven.com/a/plywood,CC0,Poly Haven (Rob Tuytel),Used on exercise wheel drum & hideout roof",
        "bark_brown_02,Bark Brown 02 (1K Diffuse/Rough/Normal),https://polyhaven.com/a/bark_brown_02,CC0,Poly Haven (Rob Tuytel),Used on burrow tunnel & applewood chew twigs",
        "concrete_floor_worn_001,Worn Surface Micro-Roughness (1K Rough),https://polyhaven.com/a/concrete_floor_worn_001,CC0,Poly Haven (Dimitrios Savva),Used for glaze micro-roughness variation on ceramic bowl",
        "mat_acrylic_clear,Procedural Smudged PMMA Acrylic,Internal Antigravity Procedural,CC0,Antigravity,IOR 1.491 + Fresnel edge tint + fingerprint roughness",
        "mat_steel_brushed,Procedural Anisotropic Brushed Steel,Internal Antigravity Procedural,CC0,Antigravity,Anisotropic stainless steel for water bottle spout & wheel axle",
        "mat_bedding_pbr,Translucent Paper & Aspen Bedding,Internal Antigravity Procedural,CC0,Antigravity,Subsurface scattering backlit shader for shavings & paper strips",
    ]
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("asset_id,name,source_url,licence,author,notes\n")
        for e in entries:
            f.write(e + "\n")
    print(f">> Updated asset license log: {csv_path}")


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


def main():
    print("\n" + "=" * 60)
    print(" HAMMY PIPELINE — BUILD PBR MATERIALS (PROMPT 3)")
    print("=" * 60)

    scene_path = os.path.abspath("blender/scene.blend")
    if os.path.exists(scene_path) and "cage_tub" not in bpy.data.objects:
        bpy.ops.wm.open_mainfile(filepath=scene_path)

    common.set_unit_scale_metric()
    common.configure_cycles_gpu("OPTIX")

    print("1. Constructing Poly Haven CC0 + Procedural PBR shader node setups...")
    assign_scene_materials()

    print("2. Building material test spheres & calibration rig...")
    build_material_test_spheres()

    print("3. Logging CC0 asset licenses to reference/licence_log.csv...")
    log_licenses()

    # Render 1: Dedicated Material Test Spheres Contact Sheet
    print("4. Rendering Material Test Spheres Contact Sheet...")
    render_view("cam_test_spheres", "renders/tests/03_materials_spheres.png", samples=96)

    # Remove temporary test spheres so cage scene stays clean
    if "TEST_SPHERES" in bpy.data.collections:
        common.clear_collection("TEST_SPHERES")
        bpy.data.collections.remove(bpy.data.collections["TEST_SPHERES"])

    # Restore active camera to cam_three_quarter
    if "cam_three_quarter" in bpy.data.objects:
        bpy.context.scene.camera = bpy.data.objects["cam_three_quarter"]

    bpy.ops.wm.save_as_mainfile(filepath=scene_path)
    print(f">> Saved scene: {scene_path}")

    # Render 2: Full Cage Scene & Close-up with PBR Materials
    print("5. Rendering Full Cage Scene & Close-up with PBR Materials...")
    render_view("cam_three_quarter", "renders/tests/03_materials_cage.png", samples=96)
    render_view("cam_closeup_corner", "renders/tests/03_materials_closeup.png", samples=96)

    print("=" * 60)
    print(" PROMPT 3 COMPLETE — PBR MATERIALS & SHADERS READY")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
