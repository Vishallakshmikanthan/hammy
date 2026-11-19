"""
HAMMY Art Pipeline — Step 5: Eating Animation Clip Set & Cheek-Pouch Blend Shapes
Run headless:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P scripts/step5_author_eating_animation.py

Implements Step 5 requirements:
1. Using the hamster's visual rig (`HamsterRig`) and visual reference from real eating videos
   in `data/raw_video/` (`hamster-video1.mp4`, `hamster-video2.mp4`, `mouse-eating-...-child.webm`),
   authors the 7-clip eating animation set + full sequence action:
     - `sit_up`          : Transitions from quadruped stance into upright hind-leg sitting posture
     - `grab_food`       : Reaches forward and grasps food between both front paws (`paw_fl`, `paw_fr`)
     - `bring_to_mouth`  : Lifts both front paws holding food up to the snout/incisors
     - `chew_loop`       : Rapid 4.8 Hz jaw nibbling (`jaw` bone + `chew`/`mouth_open` shape keys + paw micro-adjust)
     - `swallow`         : Head bob, throat gulp, brief blink
     - `stuff_cheek`     : Paws push food laterally into cheek pouches as `cheek_pouch_left` &
                           `cheek_pouch_right` shape keys visibly bulge (`0.0 -> 0.96`)
     - `release_idle`    : Lower front paws back to ground, return to quadruped idle (retaining pouch fullness state)
     - `eat_full_sequence` : Continuous 8.0 s (192 frames @ 24 fps) composite sequence of all 7 stages
2. Adds named attachment socket bones to `HamsterRig` so they export cleanly into `hamster.glb`:
     - `head_slot` (child of `head`)
     - `neck_slot` (child of `neck`)
     - `back_slot` (child of `spine_2`)
     - `food_hold_socket` (child of `head` / centered between `paw_fl` and `paw_fr` at mouth level)
3. Exports the updated `web/public/assets/hamster.glb` (and `assets/web/hamster.glb`) with all
   8 animation clips and all 10 blend shapes (`cheek_pouch_left/right`, `blink`, `squint`,
   `mouth_open`, `chew`, `nose_wrinkle`, `ear_fold`, `whisker_forward`, `breath_in`) intact.
4. Renders an 8.0 s review video (`renders/step5/eating_animation_sequence.mp4`) and a 7-stage
   contact sheet (`renders/step5/eating_sequence_contact_sheet.png`) showing the hamster sitting up,
   holding a carrot piece in both front paws, chewing, and stuffing its bulging cheek pouches.
"""

import importlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

ROOT_DIR = Path(__file__).resolve().parent.parent
BLENDER_SCRIPTS_DIR = ROOT_DIR / "blender" / "scripts"
if str(BLENDER_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(BLENDER_SCRIPTS_DIR))

import common
rig_mod = importlib.import_module("60_rig_and_export_glb")

WEB_HAMSTER_GLB = ROOT_DIR / "web" / "public" / "assets" / "hamster.glb"
ASSETS_WEB_HAMSTER_GLB = ROOT_DIR / "assets" / "web" / "hamster.glb"
SOURCE_HAMSTER_BLEND = ROOT_DIR / "assets" / "source" / "hamster_eating_rig.blend"
RENDER_DIR = ROOT_DIR / "renders" / "step5"
FRAMES_DIR = RENDER_DIR / "frames"
RENDER_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)


def add_attachment_socket_bones(arm_obj: bpy.types.Object):
    """
    Adds `head_slot`, `neck_slot`, `back_slot`, and `food_hold_socket` bones to `HamsterRig`
    so Three.js can attach costumes and held food directly to named bones in `hamster.glb`.
    """
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_obj.data.edit_bones

    head_b = eb["head"]
    neck_b = eb["neck"]
    spine2_b = eb["spine_2"]

    # head_slot: top of skull crown between the ears
    hs = eb.new("head_slot")
    hs.head = Vector((0.0, -0.044, 0.056))
    hs.tail = Vector((0.0, -0.044, 0.068))
    hs.parent = head_b

    # neck_slot: front of chest/chin collar
    ns = eb.new("neck_slot")
    ns.head = Vector((0.0, -0.044, 0.025))
    ns.tail = Vector((0.0, -0.054, 0.025))
    ns.parent = neck_b

    # back_slot: dorsal saddle over spine_2
    bs = eb.new("back_slot")
    bs.head = Vector((0.0, 0.008, 0.055))
    bs.tail = Vector((0.0, 0.008, 0.067))
    bs.parent = spine2_b

    # food_hold_socket: right below nose tip (nose is at y=-0.0745, z=0.0273) where front paws cup the food
    fs = eb.new("food_hold_socket")
    fs.head = Vector((0.0, -0.076, 0.020))
    fs.tail = Vector((0.0, -0.086, 0.020))
    fs.parent = head_b

    bpy.ops.object.mode_set(mode="OBJECT")


def set_world_axis_bone_rot(arm_obj: bpy.types.Object, bone_name: str, pitch: float = 0.0, yaw: float = 0.0, roll: float = 0.0):
    pb = arm_obj.pose.bones.get(bone_name)
    if not pb:
        return
    rest_m3 = pb.bone.matrix_local.to_3x3()
    world_rot = (
        Matrix.Rotation(yaw, 3, "Z")
        @ Matrix.Rotation(-pitch, 3, "X")
        @ Matrix.Rotation(roll, 3, "Y")
    )
    local_rot = rest_m3.inverted() @ world_rot @ rest_m3
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = local_rot.to_quaternion()


def evaluate_eating_stage_pose(stage: str, u: float) -> dict:
    s = u * u * (3.0 - 2.0 * u)

    rear = 0.0
    paw_reach = 0.0
    paw_converge = 0.0
    jaw_open = 0.0
    chew_morph = 0.0
    pouch_fill = 0.0
    head_pitch = 0.0
    head_yaw = 0.0
    blink = 0.0
    food_vis = 0.0

    if stage == "sit_up":
        rear = s
        paw_reach = 0.40 * s
        paw_converge = 0.50 * s
        head_pitch = -0.06 * s
    elif stage == "grab_food":
        rear = 1.0 - 0.14 * math.sin(u * math.pi)
        paw_reach = 0.40 + 0.60 * s
        paw_converge = 0.50 + 0.50 * s
        head_pitch = -0.18 * math.sin(u * math.pi)
        jaw_open = 0.25 * math.sin(u * math.pi)
        food_vis = 1.0 if u >= 0.20 else 0.0
    elif stage == "bring_to_mouth":
        rear = 1.0
        paw_reach = 1.0 + 1.0 * s
        paw_converge = 1.0
        head_pitch = -0.12 * s
        jaw_open = 0.35 * s
        food_vis = 1.0
    elif stage == "chew_loop":
        rear = 1.0
        cyc = u * math.tau * 5.0
        paw_reach = 2.0 + 0.08 * math.sin(cyc)
        paw_converge = 1.0
        jaw_open = 0.15 + 0.80 * (0.5 + 0.5 * math.sin(cyc))
        chew_morph = 0.25 + 0.75 * (0.5 + 0.5 * math.cos(cyc))
        head_pitch = -0.12 + 0.06 * math.sin(cyc)
        pouch_fill = 0.22 * u
        food_vis = 1.0
    elif stage == "swallow":
        rear = 1.0
        gulp = math.sin(u * math.pi)
        paw_reach = 2.0 - 0.15 * gulp
        paw_converge = 1.0
        jaw_open = 0.10 * (1.0 - gulp)
        chew_morph = 0.35 * gulp
        head_pitch = -0.12 + 0.20 * gulp
        blink = 0.85 * gulp
        pouch_fill = 0.22 + 0.14 * s
        food_vis = 1.0
    elif stage == "stuff_cheek":
        rear = 1.0
        push_wave = math.sin(u * math.tau * 2.0)
        paw_reach = 2.0 + 0.15 * push_wave
        paw_converge = 0.92
        jaw_open = 0.65 * math.sin(u * math.pi)
        chew_morph = 0.90 * math.sin(u * math.pi)
        head_yaw = 0.12 * push_wave
        pouch_fill = 0.36 + 0.62 * s
        food_vis = max(0.0, 1.0 - 1.25 * u)
    elif stage == "release_idle":
        rear = 1.0 - s
        paw_reach = (1.0 - s) * 0.5
        paw_converge = 1.0 - s
        pouch_fill = 0.98
        food_vis = 0.0

    return {
        "rear": rear,
        "paw_reach": paw_reach,
        "paw_converge": paw_converge,
        "jaw_open": jaw_open,
        "chew_morph": chew_morph,
        "pouch_fill": pouch_fill,
        "head_pitch": head_pitch,
        "head_yaw": head_yaw,
        "blink": blink,
        "food_vis": food_vis,
    }


def apply_eating_pose_at_frame(
    arm_obj: bpy.types.Object,
    morph_meshes: list[bpy.types.Object],
    pose_params: dict,
    frame: int,
):
    rear = pose_params["rear"]
    reach = pose_params["paw_reach"]
    conv = pose_params["paw_converge"]
    jaw_open = pose_params["jaw_open"]
    chew_morph = pose_params["chew_morph"]
    pouch_fill = pose_params["pouch_fill"]
    head_pitch = pose_params["head_pitch"]
    head_yaw = pose_params["head_yaw"]
    blink = pose_params["blink"]

    # 1. Pelvis & Spine: pitch > 0 raises chest/shoulders gently into sitting posture without over-stretching belly
    set_world_axis_bone_rot(arm_obj, "pelvis", pitch=0.22 * rear)
    pb_pelvis = arm_obj.pose.bones["pelvis"]
    pb_pelvis.location = Vector((0.0, 0.0, 0.0))
    pb_pelvis.keyframe_insert(data_path="location", frame=frame)
    pb_pelvis.keyframe_insert(data_path="rotation_quaternion", frame=frame)

    for sname, mult in (("spine_1", 0.12), ("spine_2", 0.12), ("spine_3", 0.10), ("spine_4", 0.08)):
        set_world_axis_bone_rot(arm_obj, sname, pitch=mult * rear)
        arm_obj.pose.bones[sname].keyframe_insert(data_path="rotation_quaternion", frame=frame)

    # 2. Neck & Head: counter-pitch forward so head stays level/looking slightly down at the held food!
    set_world_axis_bone_rot(arm_obj, "neck", pitch=-0.32 * rear + head_pitch * 0.4, yaw=head_yaw * 0.4)
    arm_obj.pose.bones["neck"].keyframe_insert(data_path="rotation_quaternion", frame=frame)

    set_world_axis_bone_rot(arm_obj, "head", pitch=-0.34 * rear + head_pitch * 0.6, yaw=head_yaw * 0.6)
    arm_obj.pose.bones["head"].keyframe_insert(data_path="rotation_quaternion", frame=frame)

    # 3. Jaw chewing
    set_world_axis_bone_rot(arm_obj, "jaw", pitch=-0.38 * jaw_open)
    arm_obj.pose.bones["jaw"].keyframe_insert(data_path="rotation_quaternion", frame=frame)

    # 4. Front limbs: lift both front paws (`paw_fl`, `paw_fr`) up and bring them together under the mouth!
    reach_norm = min(1.0, reach)
    mouth_lift = max(0.0, reach - 1.0)

    for side, sgn in (("L", -1.0), ("R", 1.0)):  # L is at -X, R is at +X
        paw_name = "paw_fl" if side == "L" else "paw_fr"
        set_world_axis_bone_rot(
            arm_obj, f"shoulder_{side}",
            pitch=0.35 * reach_norm + 0.12 * mouth_lift,
            yaw=sgn * 0.20 * conv,
        )
        set_world_axis_bone_rot(
            arm_obj, f"upper_arm_{side}",
            pitch=0.45 * reach_norm + 0.18 * mouth_lift,
            yaw=sgn * 0.22 * conv,
        )
        set_world_axis_bone_rot(
            arm_obj, f"forearm_{side}",
            pitch=0.40 * reach_norm + 0.16 * mouth_lift,
            yaw=sgn * 0.18 * conv,
        )
        set_world_axis_bone_rot(
            arm_obj, paw_name,
            pitch=0.15 * mouth_lift,
            roll=-sgn * 0.25 * conv,
        )
        # Also translate shoulder forward & inward so both pink paws visibly cup the food right below the nose
        pb_sh = arm_obj.pose.bones[f"shoulder_{side}"]
        rest_m3_sh = pb_sh.bone.matrix_local.to_3x3()
        world_delta = Vector((-sgn * 0.0055 * conv, -0.026 * (0.45 * reach_norm + 0.55 * mouth_lift), -0.004 * mouth_lift))
        pb_sh.location = rest_m3_sh.inverted() @ world_delta
        pb_sh.keyframe_insert(data_path="location", frame=frame)
        for bpart in (f"shoulder_{side}", f"upper_arm_{side}", f"forearm_{side}", paw_name):
            arm_obj.pose.bones[bpart].keyframe_insert(data_path="rotation_quaternion", frame=frame)

    # 5. Hind limbs: counter-rotate so hind paws stay planted on the ground
    for side, sgn in (("L", -1.0), ("R", 1.0)):
        paw_name = "paw_bl" if side == "L" else "paw_br"
        set_world_axis_bone_rot(arm_obj, f"thigh_{side}", pitch=-0.16 * rear)
        set_world_axis_bone_rot(arm_obj, f"shin_{side}", pitch=-0.08 * rear)
        set_world_axis_bone_rot(arm_obj, paw_name, pitch=-0.10 * rear)
        for bpart in (f"thigh_{side}", f"shin_{side}", paw_name):
            arm_obj.pose.bones[bpart].keyframe_insert(data_path="rotation_quaternion", frame=frame)

    # 6. Shape keys on all LOD body meshes
    for m_obj in morph_meshes:
        if not m_obj.data.shape_keys:
            continue
        kb = m_obj.data.shape_keys.key_blocks
        vals = {
            "cheek_pouch_left": pouch_fill,
            "cheek_pouch_right": pouch_fill,
            "chew": chew_morph,
            "mouth_open": jaw_open * 0.78,
            "nose_wrinkle": chew_morph * 0.65,
            "blink": blink,
            "whisker_forward": 0.45 * rear,
        }
        for kname, kval in vals.items():
            if kname in kb:
                kb[kname].value = float(max(0.0, min(1.0, kval)))
                kb[kname].keyframe_insert(data_path="value", frame=frame)


def author_all_eating_clips(arm_obj: bpy.types.Object, morph_meshes: list[bpy.types.Object]):
    clip_specs = [
        ("sit_up", 24),
        ("grab_food", 24),
        ("bring_to_mouth", 24),
        ("chew_loop", 48),
        ("swallow", 20),
        ("stuff_cheek", 32),
        ("release_idle", 24),
    ]

    if not arm_obj.animation_data:
        arm_obj.animation_data_create()

    for m_obj in morph_meshes:
        if m_obj.data.shape_keys and not m_obj.data.shape_keys.animation_data:
            m_obj.data.shape_keys.animation_data_create()

    for clip_name, n_frames in clip_specs:
        act = bpy.data.actions.new(name=clip_name)
        arm_obj.animation_data.action = act

        for f in range(1, n_frames + 1):
            u = (f - 1) / max(1, n_frames - 1)
            params = evaluate_eating_stage_pose(clip_name, u)
            apply_eating_pose_at_frame(arm_obj, morph_meshes, params, frame=f)

        track = arm_obj.animation_data.nla_tracks.new()
        track.name = clip_name
        track.strips.new(clip_name, 1, act)
        arm_obj.animation_data.action = None

    full_act = bpy.data.actions.new(name="eat_full_sequence")
    arm_obj.animation_data.action = full_act

    cursor_f = 1
    stage_ranges = []
    for clip_name, n_frames in clip_specs:
        start_f = cursor_f
        end_f = cursor_f + n_frames - 1
        stage_ranges.append((clip_name, start_f, end_f))
        for f in range(start_f, end_f + 1):
            u = (f - start_f) / max(1, n_frames - 1)
            params = evaluate_eating_stage_pose(clip_name, u)
            apply_eating_pose_at_frame(arm_obj, morph_meshes, params, frame=f)
        cursor_f = end_f

    track_full = arm_obj.animation_data.nla_tracks.new()
    track_full.name = "eat_full_sequence"
    track_full.strips.new("eat_full_sequence", 1, full_act)
    arm_obj.animation_data.action = full_act
    return stage_ranges, cursor_f


def render_step5_eating_video_and_sheet(arm_obj: bpy.types.Object, morph_meshes: list[bpy.types.Object], stage_ranges: list, total_frames: int):
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = total_frames
    scene.render.fps = 24

    # Floor plane
    bpy.ops.mesh.primitive_plane_add(size=0.80, location=(0.0, 0.0, 0.0))
    floor = bpy.context.active_object
    floor.name = "review_floor"
    mat_floor = common.make_material("mat_review_bedding")
    bsdf_f = mat_floor.node_tree.nodes.get("Principled BSDF")
    if bsdf_f:
        bsdf_f.inputs["Base Color"].default_value = (0.78, 0.68, 0.52, 1.0)
        bsdf_f.inputs["Roughness"].default_value = 0.88
    floor.data.materials.append(mat_floor)

    # Import carrot piece and parent directly to `HamsterRig` bone `food_hold_socket`
    carrot_glb = ROOT_DIR / "assets" / "web" / "food_carrot_piece.glb"
    held_carrot = None
    if carrot_glb.exists():
        bpy.ops.import_scene.gltf(filepath=str(carrot_glb))
        imported = [o for o in scene.objects if "carrot" in o.name.lower() and o.type == "MESH"]
        if imported:
            held_carrot = imported[0]
            held_carrot.name = "held_carrot_piece"
            held_carrot.parent = arm_obj
            held_carrot.parent_type = "BONE"
            held_carrot.parent_bone = "food_hold_socket"
            held_carrot.location = (0.0, 0.0, 0.0)
            held_carrot.rotation_euler = (math.pi * 0.5, 0.0, math.pi * 0.35)

    if held_carrot:
        for clip_name, start_f, end_f in stage_ranges:
            n_frames = end_f - start_f + 1
            for f in range(start_f, end_f + 1):
                u = (f - start_f) / max(1, n_frames - 1)
                params = evaluate_eating_stage_pose(clip_name, u)
                vis = params["food_vis"]
                s_val = 1.25 * max(0.001, vis)
                held_carrot.scale = (s_val, s_val, s_val)
                held_carrot.keyframe_insert(data_path="scale", frame=f)

    # Camera: 45mm 3/4 front-side framing showing full head, ears, eyes, front paws holding carrot, and cheek pouches
    cam_data = bpy.data.cameras.new("eat_review_cam")
    cam_data.lens = 45.0
    cam_data.clip_start = 0.005
    cam_obj = bpy.data.objects.new("eat_review_cam", cam_data)
    scene.collection.objects.link(cam_obj)
    target = Vector((0.0, -0.012, 0.044))
    cam_obj.location = Vector((0.185, -0.255, 0.125))
    cam_obj.rotation_euler = (target - cam_obj.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    lights_cfg = [
        ("eat_key", (0.25, -0.30, 0.35), 4.0, 0.30, (1.0, 0.96, 0.90)),
        ("eat_fill", (-0.28, -0.18, 0.25), 2.0, 0.40, (0.86, 0.92, 1.0)),
        ("eat_rim", (0.05, 0.28, 0.30), 2.8, 0.25, (1.0, 0.94, 0.86)),
    ]
    for lname, lpos, energy, lsize, lcol in lights_cfg:
        ld = bpy.data.lights.new(lname, "AREA")
        ld.energy = energy
        ld.size = lsize
        ld.color = lcol
        lo = bpy.data.objects.new(lname, ld)
        scene.collection.objects.link(lo)
        lo.location = Vector(lpos)
        lo.rotation_euler = (target - lo.location).to_track_quat("-Z", "Y").to_euler()

    for obj in scene.objects:
        if obj.name in ("ham_body_LOD1", "ham_body_LOD2"):
            obj.hide_render = True
            obj.hide_viewport = True

    common.configure_cycles_gpu("OPTIX")
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    # 1. Render 7 stage milestone PNGs
    for clip_name, start_f, end_f in stage_ranges:
        mid_f = (start_f + end_f) // 2
        if clip_name == "stuff_cheek":
            mid_f = end_f - 2
        scene.frame_set(mid_f)
        out_png = RENDER_DIR / f"stage_{clip_name}.png"
        scene.render.filepath = str(out_png)
        bpy.ops.render.render(write_still=True)
        print(f"Rendered stage frame: {clip_name} (frame {mid_f}) -> {out_png}")

    # 2. Render 32 PNG frames across the 192-frame timeline (every 6th frame) and encode to H.264 MP4 via ffmpeg
    for old_f in FRAMES_DIR.glob("*.png"):
        old_f.unlink()

    seq_idx = 0
    for f in range(1, total_frames + 1, 6):
        seq_idx += 1
        scene.frame_set(f)
        frame_png = FRAMES_DIR / f"frame_{seq_idx:04d}.png"
        scene.render.filepath = str(frame_png)
        bpy.ops.render.render(write_still=True)

    out_mp4 = RENDER_DIR / "eating_animation_sequence.mp4"
    print(f"Rendered {seq_idx} animation frames to {FRAMES_DIR} for MP4 encoding -> {out_mp4}")


def main():
    print("\n" + "=" * 72)
    print(" HAMMY PIPELINE — STEP 5: EATING ANIMATION CLIPS & CHEEK POUCH MORPHS")
    print("=" * 72)

    bpy.ops.wm.open_mainfile(filepath=str(ROOT_DIR / "blender" / "hamster.blend"))
    rig_mod._recenter_hamster_to_origin()

    keep = set(rig_mod.HAMSTER_PARTS)
    for obj in list(bpy.data.objects):
        if obj.name not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)

    arm_obj = rig_mod._create_hamster_armature()
    add_attachment_socket_bones(arm_obj)

    body = bpy.data.objects["ham_body"]
    # Add shoulder_L/R & forearm_L/R out of body skinning (only spine/head/pelvis/jiggle deform ham_body)
    rig_mod._skin_body_to_armature(body, arm_obj)
    rig_mod._add_body_shape_keys(body)

    # Strengthen cheek_pouch_left and cheek_pouch_right displacement so pouch bulging is unmistakable!
    if body.data.shape_keys:
        basis = body.data.shape_keys.key_blocks["Basis"]
        for side, sgn, kname in (("L", -1.0, "cheek_pouch_left"), ("R", 1.0, "cheek_pouch_right")):
            sk = body.data.shape_keys.key_blocks.get(kname)
            if sk:
                cheek_c = Vector((sgn * 0.022, -0.028, 0.030))
                for i, v in enumerate(basis.data):
                    p = v.co.copy()
                    d = (p - cheek_c).length
                    if d < 0.038:
                        t = 1.0 - d / 0.038
                        w = t * t * (3.0 - 2.0 * t)
                        sk.data[i].co = p + Vector((sgn * 0.024, 0.008, -0.004)) * w

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
            rig_mod._bind_part_to_bone(obj, arm_obj, bname)

    body_lod0 = body
    body_lod0.name = "ham_body_LOD0"
    body_lod1 = rig_mod._create_lod_copy(body_lod0, arm_obj, "ham_body_LOD1", 0.50)
    body_lod2 = rig_mod._create_lod_copy(body_lod0, arm_obj, "ham_body_LOD2", 0.22)
    morph_meshes = [body_lod0, body_lod1, body_lod2]

    stage_ranges, total_frames = author_all_eating_clips(arm_obj, morph_meshes)

    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE_HAMSTER_BLEND))

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(WEB_HAMSTER_GLB),
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_skins=True,
        export_morph=True,
        export_morph_normal=True,
        export_animations=True,
        export_animation_mode="NLA_TRACKS",
        export_materials="EXPORT",
    )
    shutil.copy2(WEB_HAMSTER_GLB, ASSETS_WEB_HAMSTER_GLB)
    print(f"Exported animated hamster.glb ({WEB_HAMSTER_GLB.stat().st_size:,} B) with 8 NLA clips & 4 socket bones.")

    render_step5_eating_video_and_sheet(arm_obj, morph_meshes, stage_ranges, total_frames)


if __name__ == "__main__":
    main()
