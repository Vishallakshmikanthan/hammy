"""
HAMMY Art Pipeline — Prompt 6 / Phase 3 Asset Export:
Builds the HamsterRig armature, skinning weights, blend shapes (shape keys),
and 3 LOD levels (LOD0, LOD1, LOD2) on the hamster from blender/hamster.blend,
then exports:
  - web/public/assets/hamster.glb
  - web/public/assets/cage.glb (from blender/scene.blend: CAGE, PROPS, BEDDING)
"""

import math
import os
import shutil
import bpy
from mathutils import Euler, Matrix, Vector

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BLENDER_DIR = os.path.join(ROOT_DIR, "blender")
ASSETS_DIR = os.path.join(ROOT_DIR, "web", "public", "assets")
HDRI_SRC = os.path.join(BLENDER_DIR, "textures", "hdri", "brown_photostudio_02_1k.hdr")
HDRI_DST = os.path.join(ASSETS_DIR, "hdri", "brown_photostudio_02_1k.hdr")

HAMSTER_PARTS = [
    "ham_body",
    "ham_ear_L",
    "ham_ear_R",
    "ham_eye_L",
    "ham_eye_R",
    "ham_nose",
    "ham_paw_fl",
    "ham_paw_fr",
    "ham_paw_bl",
    "ham_paw_br",
    "ham_tail",
]


def _recenter_hamster_to_origin():
    """Transform hamster parts from cage placement back to canonical origin space.

    In hamster.blend, ham_body is at HAMSTER_POS=(0.145, 0.032, 0.171) with yaw=-135 deg.
    We invert that transform and rotate so the hamster faces +Y in Blender (which exports
    as +Z forward in glTF Y-up), with paws resting at Z=0.
    """
    body = bpy.data.objects["ham_body"]
    pivot = body.location.copy()
    yaw = body.rotation_euler.z  # -2.3562 rad (-135 deg)

    # Determine forward direction in local space using nose vs tail
    nose = bpy.data.objects["ham_nose"]
    tail = bpy.data.objects["ham_tail"]
    inv_rot = Matrix.Rotation(-yaw, 4, "Z")

    nose_local = inv_rot @ (nose.matrix_world.translation - pivot)
    tail_local = inv_rot @ (tail.matrix_world.translation - pivot)
    fwd_xy = Vector((nose_local.x - tail_local.x, nose_local.y - tail_local.y, 0.0)).normalized()
    # Rotate so fwd_xy aligns with Blender +Y (which maps to +Z in glTF? Wait:
    # Blender glTF exporter maps Blender +X->+X, +Y->-Z, +Z->+Y.
    # So Blender -Y maps to glTF +Z (forward)!
    angle_to_minus_y = math.atan2(fwd_xy.x, -fwd_xy.y)
    align_rot = Matrix.Rotation(angle_to_minus_y, 4, "Z")

    # Apply combined rigid transform to each hamster mesh data directly
    for name in HAMSTER_PARTS:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            continue
        # Bake current world matrix into mesh, then apply inverse pivot & align_rot
        world_m = obj.matrix_world.copy()
        obj.parent = None
        obj.location = (0.0, 0.0, 0.0)
        obj.rotation_euler = (0.0, 0.0, 0.0)
        obj.scale = (1.0, 1.0, 1.0)
        obj.data.transform(align_rot @ inv_rot @ Matrix.Translation(-pivot) @ world_m)
        obj.data.update()

    # Shift Z so lowest paw vertex sits at Z = 0
    min_z = min(
        (v.co.z for n in HAMSTER_PARTS if n in bpy.data.objects for v in bpy.data.objects[n].data.vertices),
        default=0.0,
    )
    if abs(min_z) > 1e-6:
        shift = Matrix.Translation((0.0, 0.0, -min_z))
        for name in HAMSTER_PARTS:
            obj = bpy.data.objects.get(name)
            if obj and obj.type == "MESH":
                obj.data.transform(shift)
                obj.data.update()


def _create_hamster_armature() -> bpy.types.Object:
    """Create the HamsterRig armature aligned with the recentered hamster."""
    arm_data = bpy.data.armatures.new("HamsterRigData")
    arm_obj = bpy.data.objects.new("HamsterRig", arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")

    def part_center(name: str) -> Vector:
        obj = bpy.data.objects[name]
        verts = obj.data.vertices
        acc = Vector((0.0, 0.0, 0.0))
        for v in verts:
            acc += v.co
        return acc / max(len(verts), 1)

    nose_c = part_center("ham_nose")
    tail_c = part_center("ham_tail")
    ear_l_c = part_center("ham_ear_L")
    ear_r_c = part_center("ham_ear_R")
    eye_l_c = part_center("ham_eye_L")
    eye_r_c = part_center("ham_eye_R")
    paw_fl_c = part_center("ham_paw_fl")
    paw_fr_c = part_center("ham_paw_fr")
    paw_bl_c = part_center("ham_paw_bl")
    paw_br_c = part_center("ham_paw_br")

    # Note: after _recenter_hamster_to_origin, nose is at -Y, tail is at +Y
    pelvis_pos = Vector((0.0, tail_c.y * 0.72, 0.028))
    head_pos = Vector((0.0, nose_c.y * 0.62, 0.036))

    bones_spec = [
        ("root", None, Vector((0.0, 0.0, 0.0)), Vector((0.0, -0.02, 0.0))),
        ("pelvis", "root", pelvis_pos, pelvis_pos + Vector((0.0, -0.015, 0.002))),
        ("spine_1", "pelvis", pelvis_pos.lerp(head_pos, 0.18), pelvis_pos.lerp(head_pos, 0.36)),
        ("spine_2", "spine_1", pelvis_pos.lerp(head_pos, 0.36), pelvis_pos.lerp(head_pos, 0.54)),
        ("spine_3", "spine_2", pelvis_pos.lerp(head_pos, 0.54), pelvis_pos.lerp(head_pos, 0.72)),
        ("spine_4", "spine_3", pelvis_pos.lerp(head_pos, 0.72), pelvis_pos.lerp(head_pos, 0.88)),
        ("neck", "spine_4", pelvis_pos.lerp(head_pos, 0.88), head_pos),
        ("head", "neck", head_pos, nose_c),
        ("jaw", "head", head_pos + Vector((0.0, -0.008, -0.012)), nose_c + Vector((0.0, 0.004, -0.012))),
        ("ear_L_1", "head", ear_l_c + Vector((0.0, 0.0, -0.006)), ear_l_c),
        ("ear_L_2", "ear_L_1", ear_l_c, ear_l_c + Vector((-0.003, 0.002, 0.008))),
        ("ear_R_1", "head", ear_r_c + Vector((0.0, 0.0, -0.006)), ear_r_c),
        ("ear_R_2", "ear_R_1", ear_r_c, ear_r_c + Vector((0.003, 0.002, 0.008))),
        ("eye_L", "head", eye_l_c, eye_l_c + Vector((-0.004, -0.004, 0.0))),
        ("eye_R", "head", eye_r_c, eye_r_c + Vector((0.004, -0.004, 0.0))),
        ("whisker_L", "head", nose_c + Vector((-0.008, 0.004, -0.002)), nose_c + Vector((-0.025, -0.004, -0.003))),
        ("whisker_R", "head", nose_c + Vector((0.008, 0.004, -0.002)), nose_c + Vector((0.025, -0.004, -0.003))),
        # Front limbs
        ("shoulder_L", "spine_4", Vector((-0.014, paw_fl_c.y + 0.005, 0.026)), Vector((-0.017, paw_fl_c.y + 0.002, 0.018))),
        ("upper_arm_L", "shoulder_L", Vector((-0.017, paw_fl_c.y + 0.002, 0.018)), Vector((-0.016, paw_fl_c.y, 0.010))),
        ("forearm_L", "upper_arm_L", Vector((-0.016, paw_fl_c.y, 0.010)), paw_fl_c + Vector((0.0, 0.0, 0.002))),
        ("paw_fl", "forearm_L", paw_fl_c + Vector((0.0, 0.0, 0.002)), paw_fl_c + Vector((0.0, -0.008, 0.0))),
        ("shoulder_R", "spine_4", Vector((0.014, paw_fr_c.y + 0.005, 0.026)), Vector((0.017, paw_fr_c.y + 0.002, 0.018))),
        ("upper_arm_R", "shoulder_R", Vector((0.017, paw_fr_c.y + 0.002, 0.018)), Vector((0.016, paw_fr_c.y, 0.010))),
        ("forearm_R", "upper_arm_R", Vector((0.016, paw_fr_c.y, 0.010)), paw_fr_c + Vector((0.0, 0.0, 0.002))),
        ("paw_fr", "forearm_R", paw_fr_c + Vector((0.0, 0.0, 0.002)), paw_fr_c + Vector((0.0, -0.008, 0.0))),
        # Hind limbs
        ("hip_L", "pelvis", Vector((-0.018, paw_bl_c.y, 0.028)), Vector((-0.022, paw_bl_c.y - 0.002, 0.018))),
        ("thigh_L", "hip_L", Vector((-0.022, paw_bl_c.y - 0.002, 0.018)), Vector((-0.020, paw_bl_c.y - 0.004, 0.010))),
        ("shin_L", "thigh_L", Vector((-0.020, paw_bl_c.y - 0.004, 0.010)), paw_bl_c + Vector((0.0, 0.0, 0.002))),
        ("paw_bl", "shin_L", paw_bl_c + Vector((0.0, 0.0, 0.002)), paw_bl_c + Vector((0.0, -0.010, 0.0))),
        ("hip_R", "pelvis", Vector((0.018, paw_br_c.y, 0.028)), Vector((0.022, paw_br_c.y - 0.002, 0.018))),
        ("thigh_R", "hip_R", Vector((0.022, paw_br_c.y - 0.002, 0.018)), Vector((0.020, paw_br_c.y - 0.004, 0.010))),
        ("shin_R", "thigh_R", Vector((0.020, paw_br_c.y - 0.004, 0.010)), paw_br_c + Vector((0.0, 0.0, 0.002))),
        ("paw_br", "shin_R", paw_br_c + Vector((0.0, 0.0, 0.002)), paw_br_c + Vector((0.0, -0.010, 0.0))),
        # Tail
        ("tail_1", "pelvis", tail_c + Vector((0.0, -0.006, 0.0)), tail_c),
        ("tail_2", "tail_1", tail_c, tail_c + Vector((0.0, 0.007, 0.002))),
        # Spring/jiggle bones
        ("jiggle_cheek_L", "head", head_pos + Vector((-0.018, -0.004, -0.004)), head_pos + Vector((-0.026, -0.004, -0.006))),
        ("jiggle_cheek_R", "head", head_pos + Vector((0.018, -0.004, -0.004)), head_pos + Vector((0.026, -0.004, -0.006))),
        ("jiggle_flank_L", "spine_2", Vector((-0.025, 0.010, 0.026)), Vector((-0.034, 0.010, 0.024))),
        ("jiggle_flank_R", "spine_2", Vector((0.025, 0.010, 0.026)), Vector((0.034, 0.010, 0.024))),
        ("jiggle_scruff", "neck", Vector((0.0, -0.018, 0.044)), Vector((0.0, -0.014, 0.052))),
    ]

    eb = arm_data.edit_bones
    created = {}
    for bname, parent_name, head_pt, tail_pt in bones_spec:
        b = eb.new(bname)
        b.head = head_pt
        b.tail = tail_pt
        if parent_name and parent_name in created:
            b.parent = created[parent_name]
        created[bname] = b

    bpy.ops.object.mode_set(mode="OBJECT")
    return arm_obj


def _bind_part_to_bone(obj: bpy.types.Object, arm_obj: bpy.types.Object, bone_name: str):
    vg = obj.vertex_groups.new(name=bone_name)
    vg.add([v.index for v in obj.data.vertices], 1.0, "REPLACE")
    obj.parent = arm_obj
    mod = obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = arm_obj


def _skin_body_to_armature(body: bpy.types.Object, arm_obj: bpy.types.Object):
    """Assign smooth inverse-distance skinning weights on ham_body across spine/head/pelvis."""
    deform_bones = ["pelvis", "spine_1", "spine_2", "spine_3", "spine_4", "neck", "head",
                    "jiggle_cheek_L", "jiggle_cheek_R", "jiggle_flank_L", "jiggle_flank_R", "jiggle_scruff"]
    bone_centers = {}
    for bname in deform_bones:
        b = arm_obj.data.bones[bname]
        bone_centers[bname] = (b.head_local + b.tail_local) * 0.5
        body.vertex_groups.new(name=bname)

    for v in body.data.vertices:
        weights = []
        for bname, ctr in bone_centers.items():
            d = (v.co - ctr).length
            w = 1.0 / (0.0004 + d * d * 8.0)
            weights.append((bname, w))
        weights.sort(key=lambda x: x[1], reverse=True)
        top = weights[:4]
        total = sum(w for _, w in top) or 1.0
        for bname, w in top:
            body.vertex_groups[bname].add([v.index], w / total, "REPLACE")

    body.parent = arm_obj
    mod = body.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = arm_obj


def _add_body_shape_keys(body: bpy.types.Object):
    """Create the realistic facial and body blend shapes required by P3.2."""
    eye_l_c = Vector((-0.014, -0.036, 0.041))
    eye_r_c = Vector((0.014, -0.036, 0.041))
    nose_c = Vector((0.0, -0.056, 0.029))
    ear_l_c = Vector((-0.014, -0.020, 0.056))
    ear_r_c = Vector((0.014, -0.020, 0.056))

    # Recompute approximate landmarks from actual parts
    if "ham_eye_L" in bpy.data.objects:
        eye_l_c = sum((v.co for v in bpy.data.objects["ham_eye_L"].data.vertices), Vector()) / len(bpy.data.objects["ham_eye_L"].data.vertices)
    if "ham_eye_R" in bpy.data.objects:
        eye_r_c = sum((v.co for v in bpy.data.objects["ham_eye_R"].data.vertices), Vector()) / len(bpy.data.objects["ham_eye_R"].data.vertices)
    if "ham_nose" in bpy.data.objects:
        nose_c = sum((v.co for v in bpy.data.objects["ham_nose"].data.vertices), Vector()) / len(bpy.data.objects["ham_nose"].data.vertices)
    if "ham_ear_L" in bpy.data.objects:
        ear_l_c = sum((v.co for v in bpy.data.objects["ham_ear_L"].data.vertices), Vector()) / len(bpy.data.objects["ham_ear_L"].data.vertices)
    if "ham_ear_R" in bpy.data.objects:
        ear_r_c = sum((v.co for v in bpy.data.objects["ham_ear_R"].data.vertices), Vector()) / len(bpy.data.objects["ham_ear_R"].data.vertices)

    body.shape_key_add(name="Basis", from_mix=False)
    basis = body.data.shape_keys.key_blocks["Basis"]

    def make_key(name: str, fn):
        sk = body.shape_key_add(name=name, from_mix=False)
        for i, v in enumerate(basis.data):
            sk.data[i].co = fn(v.co.copy())

    def falloff(p: Vector, center: Vector, radius: float) -> float:
        d = (p - center).length
        if d >= radius:
            return 0.0
        t = 1.0 - d / radius
        return t * t * (3.0 - 2.0 * t)

    cheek_l_c = Vector((-0.022, (nose_c.y + ear_l_c.y) * 0.5 + 0.010, 0.028))
    cheek_r_c = Vector((0.022, (nose_c.y + ear_r_c.y) * 0.5 + 0.010, 0.028))

    make_key("cheek_pouch_left", lambda p: p + Vector((-0.018, 0.008, -0.004)) * falloff(p, cheek_l_c, 0.032))
    make_key("cheek_pouch_right", lambda p: p + Vector((0.018, 0.008, -0.004)) * falloff(p, cheek_r_c, 0.032))

    def blink_fn(p: Vector) -> Vector:
        fl = falloff(p, eye_l_c, 0.012)
        fr = falloff(p, eye_r_c, 0.012)
        dz_l = (eye_l_c.z - p.z) * 0.65 * fl
        dz_r = (eye_r_c.z - p.z) * 0.65 * fr
        return p + Vector((0.0, 0.0, dz_l + dz_r))

    make_key("blink", blink_fn)
    make_key("squint", lambda p: p.lerp(blink_fn(p), 0.55))

    mouth_c = nose_c + Vector((0.0, 0.004, -0.010))
    make_key("mouth_open", lambda p: p + Vector((0.0, 0.002, -0.007)) * falloff(p, mouth_c, 0.016))
    make_key("chew", lambda p: p + Vector((0.003, 0.002, -0.004)) * falloff(p, mouth_c, 0.020))
    make_key("nose_wrinkle", lambda p: p + Vector((0.0, -0.002, 0.003)) * falloff(p, nose_c, 0.014))

    def ear_fold_fn(p: Vector) -> Vector:
        fl = falloff(p, ear_l_c, 0.016)
        fr = falloff(p, ear_r_c, 0.016)
        return p + Vector((0.0, 0.005, -0.005)) * (fl + fr)

    make_key("ear_fold", ear_fold_fn)
    make_key("whisker_forward", lambda p: p + Vector((0.0, -0.004, 0.0)) * falloff(p, nose_c + Vector((0.0, 0.004, -0.002)), 0.020))

    chest_c = Vector((0.0, 0.0, 0.030))
    make_key("breath_in", lambda p: p + Vector((p.x * 0.06, 0.0, (p.z - 0.025) * 0.08)) * falloff(p, chest_c, 0.055))


def _create_lod_copy(src_body: bpy.types.Object, arm_obj: bpy.types.Object, name: str, ratio: float) -> bpy.types.Object:
    """Create a decimated LOD mesh copy and transfer shape keys from src_body."""
    lod = src_body.copy()
    lod.data = src_body.data.copy()
    lod.name = name
    bpy.context.scene.collection.objects.link(lod)

    # Remove Armature modifier and shape keys temporarily so Decimate applies cleanly first
    for m in list(lod.modifiers):
        if m.type == "ARMATURE":
            lod.modifiers.remove(m)
    if lod.data.shape_keys:
        for kb in list(lod.data.shape_keys.key_blocks)[::-1]:
            lod.shape_key_remove(kb)

    dec = lod.modifiers.new(name="Decimate", type="DECIMATE")
    dec.ratio = ratio
    bpy.context.view_layer.objects.active = lod
    bpy.ops.object.modifier_apply(modifier=dec.name)

    arm_mod = lod.modifiers.new(name="Armature", type="ARMATURE")
    arm_mod.object = arm_obj

    # Transfer shape keys via nearest vertex in Basis
    src_basis = src_body.data.shape_keys.key_blocks["Basis"].data
    lod.shape_key_add(name="Basis", from_mix=False)
    lod_basis = lod.data.shape_keys.key_blocks["Basis"].data
    nearest_idx = []
    for lv in lod_basis:
        best_i = 0
        best_d = 1e9
        for si, sv in enumerate(src_basis):
            d = (lv.co - sv.co).length_squared
            if d < best_d:
                best_d = d
                best_i = si
        nearest_idx.append(best_i)

    for kb in src_body.data.shape_keys.key_blocks:
        if kb.name == "Basis":
            continue
        new_kb = lod.shape_key_add(name=kb.name, from_mix=False)
        for li, si in enumerate(nearest_idx):
            delta = kb.data[si].co - src_basis[si].co
            new_kb.data[li].co = lod_basis[li].co + delta

    lod.parent = arm_obj
    return lod


def export_hamster_glb():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(BLENDER_DIR, "hamster.blend"))
    _recenter_hamster_to_origin()

    # Delete non-hamster objects so hamster.glb only contains the character + rig
    keep = set(HAMSTER_PARTS)
    for obj in list(bpy.data.objects):
        if obj.name not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)

    arm_obj = _create_hamster_armature()
    body = bpy.data.objects["ham_body"]
    _skin_body_to_armature(body, arm_obj)
    _add_body_shape_keys(body)

    part_bone_map = {
        "ham_ear_L": "ear_L_1",
        "ham_ear_R": "ear_R_1",
        "ham_eye_L": "eye_L",
        "ham_eye_R": "eye_R",
        "ham_nose": "head",
        "ham_paw_fl": "paw_fl",
        "ham_paw_fr": "paw_fr",
        "ham_paw_bl": "paw_bl",
        "ham_paw_br": "paw_br",
        "ham_tail": "tail_1",
    }
    for pname, bname in part_bone_map.items():
        obj = bpy.data.objects.get(pname)
        if obj:
            _bind_part_to_bone(obj, arm_obj, bname)

    body_lod0 = body
    body_lod0.name = "ham_body_LOD0"
    _create_lod_copy(body_lod0, arm_obj, "ham_body_LOD1", 0.50)
    _create_lod_copy(body_lod0, arm_obj, "ham_body_LOD2", 0.22)

    os.makedirs(ASSETS_DIR, exist_ok=True)
    out_path = os.path.join(ASSETS_DIR, "hamster.glb")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_skins=True,
        export_morph=True,
        export_morph_normal=True,
        export_materials="EXPORT",
    )
    print(f"Exported {out_path}")


def export_cage_glb():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(BLENDER_DIR, "scene.blend"))

    # Remove HAMSTER, CAMERAS, LIGHTS so Three.js drives the hamster, cameras, and day/night lighting
    remove_cols = {"HAMSTER", "CAMERAS", "LIGHTS"}
    for cname in remove_cols:
        col = bpy.data.collections.get(cname)
        if col:
            for obj in list(col.objects):
                bpy.data.objects.remove(obj, do_unlink=True)

    os.makedirs(ASSETS_DIR, exist_ok=True)
    out_path = os.path.join(ASSETS_DIR, "cage.glb")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_materials="EXPORT",
    )
    print(f"Exported {out_path}")


def copy_hdri():
    if os.path.exists(HDRI_SRC):
        os.makedirs(os.path.dirname(HDRI_DST), exist_ok=True)
        shutil.copy2(HDRI_SRC, HDRI_DST)
        print(f"Copied HDRI to {HDRI_DST}")


if __name__ == "__main__":
    export_hamster_glb()
    export_cage_glb()
    copy_hdri()
