"""
HAMMY — P8.1: Cinematic Moments (Blender Cycles Pipeline) (`blender/scripts/80_render_cinematic_clip.py`).
Loads `blender/hamster.blend` (with full hair-curve groom + cage) and a P5.1 `TrajectoryClipV1`
(`.clip.json` or `.clip.json.gz`), applies the trajectory keyframes, configures camera preset
(`low_macro`, `three_quarter`, `wide`) with automatic framing, and renders to MP4 with Cycles
OptiX denoising and render-budget controls.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

scripts_dir = os.path.dirname(os.path.abspath(__file__))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

import common

ROOT_DIR = Path(__file__).resolve().parents[2]
CAMERA_PRESETS = {
    "low_macro": "cam_macro_85mm",
    "three_quarter": "cam_three_quarter_50mm",
    "wide": "cam_wide_35mm",
}


def load_clip(clip_path: Path) -> dict:
    if clip_path.suffix == ".gz":
        raw = gzip.decompress(clip_path.read_bytes()).decode("utf-8")
    else:
        raw = clip_path.read_text(encoding="utf-8")
    return json.loads(raw)


def apply_clip_keyframes(body_obj: bpy.types.Object, clip: dict, scene_fps: int = 24) -> Vector:
    kfs = clip["keyframes"]
    if not kfs:
        return body_obj.location.copy()

    # Clear existing animation data
    body_obj.animation_data_clear()
    centroid = Vector((0.0, 0.0, 0.0))

    for kf in kfs:
        frame = int(round(kf["t_sec"] * scene_fps)) + 1
        # Map Three.js (x, y_up, z) -> Blender (x, -z, y_up) + cage bedding height
        rp = kf["root_pos"]
        pos = Vector((rp[0], -rp[2], 0.171 + max(0.0, rp[1] - 0.055)))
        centroid += pos

        rq = kf["root_quat"]  # [x, y, z, w]
        q = Quaternion((rq[3], rq[0], -rq[2], rq[1])).normalized()

        body_obj.location = pos
        body_obj.rotation_mode = "QUATERNION"
        body_obj.rotation_quaternion = q
        body_obj.keyframe_insert(data_path="location", frame=frame)
        body_obj.keyframe_insert(data_path="rotation_quaternion", frame=frame)

    centroid /= len(kfs)
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = max(2, int(round(kfs[-1]["t_sec"] * scene_fps)) + 1)
    return centroid


def configure_camera_and_render(
    preset: str,
    target_centroid: Vector,
    out_mp4: Path,
    samples: int = 64,
    res_x: int = 1280,
    res_y: int = 720,
) -> None:
    scene = bpy.context.scene
    cam_name = CAMERA_PRESETS.get(preset, "cam_three_quarter_50mm")
    cam = bpy.data.objects.get(cam_name)
    if cam:
        scene.camera = cam
        direction = target_centroid - cam.location
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    common.configure_cycles_gpu("OPTIX")
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100
    scene.render.fps = 24

    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out_mp4)
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="P8.1 Cinematic Cycles Clip Renderer")
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preset", default="three_quarter", choices=list(CAMERA_PRESETS.keys()))
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--res-x", type=int, default=1280)
    parser.add_argument("--res-y", type=int, default=720)
    parser.add_argument("--render-still", action="store_true", help="Render frame 1 PNG only (fast smoke test)")
    args = parser.parse_args(argv)

    bpy.ops.wm.open_mainfile(filepath=str(ROOT_DIR / "blender" / "hamster.blend"))
    body = bpy.data.objects["ham_body"]
    clip = load_clip(args.clip)
    centroid = apply_clip_keyframes(body, clip)
    configure_camera_and_render(
        preset=args.preset,
        target_centroid=centroid,
        out_mp4=args.out,
        samples=args.samples,
        res_x=args.res_x,
        res_y=args.res_y,
    )

    if args.render_still:
        bpy.context.scene.render.image_settings.file_format = "PNG"
        bpy.context.scene.render.filepath = str(args.out.with_suffix(".png"))
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()

