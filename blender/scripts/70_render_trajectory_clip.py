"""
HAMMY — P1.3: Bridge Simulation Trajectory to Blender Animation (`blender/scripts/70_render_trajectory_clip.py`).
Loads the verified P1.3 learned policy trajectory from `simulation/trajectories/p1_3_learned_trajectory.json`,
parents all hamster anatomical sub-parts and hair curves to `ham_body`, keyframes kinematic locomotion
and wheel rotation across the sequence, and renders milestone test frames using Cycles GPU.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

# Ensure scripts dir is on sys.path
scripts_dir = os.path.dirname(os.path.abspath(__file__))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

import common

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TRAJ_PATH = ROOT_DIR / "simulation" / "trajectories" / "p1_3_learned_trajectory.json"
OUTPUT_DIR = ROOT_DIR / "renders" / "tests"


def parent_hamster_parts(body_obj: bpy.types.Object):
    """
    Ensures all anatomical sub-parts (eyes, ears, paws, nose, tail, fur curves)
    are strictly parented to `ham_body` while preserving world matrices.
    """
    subpart_names = [
        "ham_eye_L", "ham_eye_R",
        "ham_ear_L", "ham_ear_R",
        "ham_nose",
        "ham_paw_fl", "ham_paw_fr", "ham_paw_bl", "ham_paw_br",
        "ham_tail",
        "ham_fur_guard_hairs", "ham_fur_undercoat", "ham_fur_face",
        "ham_whiskers",
    ]

    for name in subpart_names:
        obj = bpy.data.objects.get(name)
        if obj and obj.parent != body_obj:
            orig_world = obj.matrix_world.copy()
            obj.parent = body_obj
            obj.matrix_parent_inverse = body_obj.matrix_world.inverted()
            obj.matrix_world = orig_world


def animate_trajectory():
    print(f"Loading trajectory from: {TRAJ_PATH}")
    if not TRAJ_PATH.exists():
        raise FileNotFoundError(f"Trajectory file not found: {TRAJ_PATH}")

    with open(TRAJ_PATH, "r", encoding="utf-8") as f:
        keyframes = json.load(f)

    print(f">> Loaded {len(keyframes)} trajectory keyframes.")
    if len(keyframes) == 0:
        raise ValueError("Trajectory contains 0 frames.")

    body_obj = bpy.data.objects.get("ham_body")
    if not body_obj:
        raise RuntimeError("Object 'ham_body' not found in Blender scene.")

    wheel_drum = bpy.data.objects.get("prop_wheel_drum")

    # Parent all anatomical subparts to ham_body
    parent_hamster_parts(body_obj)

    # Set up scene animation range
    scene = bpy.context.scene
    fps = 24
    scene.render.fps = fps
    # Subsample keyframes to ~120 frames for smooth playback and rapid evaluation
    stride = max(1, len(keyframes) // 120)
    sampled_kfs = keyframes[::stride]
    print(f">> Sampled {len(sampled_kfs)} keyframes (stride {stride})")

    step_duration_frames = 2
    total_frames = max(len(sampled_kfs) * step_duration_frames, 24)

    scene.frame_start = 1
    scene.frame_end = total_frames

    # Clear existing animation on ham_body and wheel
    if body_obj.animation_data:
        body_obj.animation_data_clear()
    if wheel_drum and wheel_drum.animation_data:
        wheel_drum.animation_data_clear()

    # Base resting height of hamster body
    base_z = 0.171
    accum_wheel_rot = 0.0

    print("Keyframing trajectory onto hamster body and props...")
    for i, kf in enumerate(sampled_kfs):
        frame_idx = 1 + i * step_duration_frames

        pos = kf.get("pos_xyz", [0.145, 0.032, base_z])
        yaw_rad = kf.get("yaw_rad", math.radians(-135.0))
        on_wheel = kf.get("on_wheel", False)

        # Subtle vertical bobbing during locomotion (0.0018 m amplitude)
        is_moving = (i > 0 and not on_wheel and kf.get("skill") in ("approach_food", "explore_area", "run_on_wheel", "enter_tunnel"))
        bob = math.sin(i * 1.8) * 0.0018 if is_moving else 0.0

        # Position and orientation (keyframed directly without slow frame_set)
        body_obj.location = Vector((pos[0], pos[1], pos[2] + bob))
        body_obj.rotation_euler = Euler((0.0, 0.0, yaw_rad), 'XYZ')
        body_obj.keyframe_insert(data_path="location", frame=frame_idx)
        body_obj.keyframe_insert(data_path="rotation_euler", frame=frame_idx)

        # Animate wheel spin if agent is on wheel
        if wheel_drum:
            if on_wheel:
                accum_wheel_rot += 0.65  # ~37 deg rotation per sub-step
            wheel_drum.rotation_euler.x = accum_wheel_rot
            wheel_drum.keyframe_insert(data_path="rotation_euler", frame=frame_idx)

    # Set active scene camera
    cam_tq = bpy.data.objects.get("cam_three_quarter_50mm")
    cam_macro = bpy.data.objects.get("cam_macro_85mm")
    cam_wide = bpy.data.objects.get("cam_wide_35mm")

    active_cam = cam_tq if cam_tq else (cam_macro if cam_macro else cam_wide)
    if active_cam:
        scene.camera = active_cam

    # Setup rendering engine
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'GPU'
    scene.cycles.samples = 64
    scene.cycles.preview_samples = 32
    scene.cycles.use_denoising = True

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    milestones = [
        ("07_trajectory_start", 1),
        ("07_trajectory_mid", max(1, total_frames // 2)),
        ("07_trajectory_end", total_frames),
    ]

    for label, f_num in milestones:
        f_num = min(f_num, total_frames)
        scene.frame_set(f_num)
        out_path = OUTPUT_DIR / f"{label}.png"
        scene.render.filepath = str(out_path)
        print(f"Rendering milestone frame {f_num} ({label}) to: {out_path} ...")
        bpy.ops.render.render(write_still=True)
        print(f">> Rendered: {out_path} ({os.path.getsize(out_path) / 1024:.1f} KB)")

    # Save animated blend file
    save_path = ROOT_DIR / "blender" / "scene.blend"
    bpy.ops.wm.save_mainfile(filepath=str(save_path))
    print(f">> Saved animated Blender scene to {save_path}")


if __name__ == "__main__":
    animate_trajectory()
