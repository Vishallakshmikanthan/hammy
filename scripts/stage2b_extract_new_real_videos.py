"""Stage 2b: Extract poses, real flat-ground gait statistics, and MJCF reference clips from newly added videos."""

from __future__ import annotations

import glob
import json
from pathlib import Path

import cv2
import deeplabcut
import imageio.v2 as imageio
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

from scripts.stage2_clean_retarget_and_render import (
    clean_keypoint_csv,
    render_keypoint_overlay,
    render_mujoco_reference,
    retarget_side_video_to_mjcf,
)
from scripts.stage2_extract_poses import QUADRUPED_MAP, TOPVIEWMOUSE_MAP, convert_h5_to_canonical_csv
from training.reference_library import save_reference_clip

RAW_DIR = Path("data/raw_video")
CLIPS_DIR = Path("data/clips")
DLC_OUT_DIR = Path("data/keypoints/dlc_raw")
KP_DIR = Path("data/keypoints")
REF_DIR = Path("data/reference_motion")
RENDER_DIR = Path("renders/stage2b")


def convert_to_mp4(src: Path, dst: Path, max_frames: int = 450) -> dict:
    """Convert .webm/.mp4 to clean H264/mp4v .mp4 for DeepLabCut compatibility."""
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out_w = (w // 2) * 2
    out_h = (h // 2) * 2
    dst.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"), fps, (out_w, out_h))
    written = 0
    while written < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        if frame.shape[1] != out_w or frame.shape[0] != out_h:
            frame = cv2.resize(frame, (out_w, out_h))
        writer.write(frame)
        written += 1
    writer.release()
    cap.release()
    return {"src": src.name, "dst": str(dst), "fps": round(fps, 3), "frames": written, "duration_s": round(written / fps, 2)}


def analyze_flat_walk_stats(clean_df: pd.DataFrame, fps: float, syrian_body_len_m: float = 0.145) -> dict:
    """Extract real flat-ground walking speed, stride frequency, stride length, and stop-start bouts."""
    cx = clean_df["body_cx"].to_numpy(dtype=float)
    cy = clean_df["body_cy"].to_numpy(dtype=float)
    body_px = float(
        np.nanmedian(
            np.hypot(
                clean_df["nose_x"] - clean_df["tail_base_x"],
                clean_df["nose_y"] - clean_df["tail_base_y"],
            )
        )
    )
    if not np.isfinite(body_px) or body_px < 15.0:
        body_px = 100.0

    # Smooth centroid velocity in body-lengths/s -> scaled Syrian m/s
    vx_px = np.gradient(cx) * fps
    vy_px = np.gradient(cy) * fps
    speed_bl_s = np.hypot(vx_px, vy_px) / body_px
    win = max(5, int(round(0.35 * fps)) | 1)
    if len(speed_bl_s) >= win:
        speed_bl_s = np.maximum(0.0, savgol_filter(speed_bl_s, win, 2))
    speed_m_s = speed_bl_s * syrian_body_len_m

    moving = speed_bl_s > 0.20
    move_bouts, stop_bouts = [], []
    cur, cnt = bool(moving[0]), 1
    for m in moving[1:]:
        if bool(m) == cur:
            cnt += 1
        else:
            (move_bouts if cur else stop_bouts).append(cnt / fps)
            cur, cnt = bool(m), 1
    (move_bouts if cur else stop_bouts).append(cnt / fps)

    # Stride frequency from best-tracked paw during moving frames
    best_paw = max(("fl_paw", "fr_paw", "bl_paw", "br_paw"), key=lambda p: float(np.nanmean(clean_df[f"{p}_conf"])))
    paw_rel_x = pd.Series(clean_df[f"{best_paw}_x"].to_numpy() - cx).interpolate(limit_direction="both").to_numpy()
    paw_rel_x = paw_rel_x - np.mean(paw_rel_x)
    n = len(paw_rel_x)
    freqs = np.fft.rfftfreq(n, d=1.0 / fps)
    spec = np.abs(np.fft.rfft(paw_rel_x * np.hanning(n)))
    band = (freqs >= 1.2) & (freqs <= 6.5)
    dom_freq = float(freqs[band][np.argmax(spec[band])]) if np.any(band) else 2.5

    mean_walk_speed = float(np.mean(speed_m_s[moving])) if np.any(moving) else float(np.mean(speed_m_s))
    est_stride_len = mean_walk_speed / max(dom_freq, 0.5)

    return {
        "source_type": "REAL_VIDEO",
        "median_body_px": round(body_px, 1),
        "moving_fraction": round(float(np.mean(moving)), 3),
        "mean_moving_speed_m_s": round(mean_walk_speed, 3),
        "peak_speed_m_s": round(float(np.percentile(speed_m_s, 95)), 3),
        "stride_freq_hz": round(dom_freq, 2),
        "est_stride_length_m": round(est_stride_len, 4),
        "mean_move_bout_s": round(float(np.mean(move_bouts)), 2) if move_bouts else 0.0,
        "mean_stop_bout_s": round(float(np.mean(stop_bouts)), 2) if stop_bouts else 0.0,
    }


def main() -> None:
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    DLC_OUT_DIR.mkdir(parents=True, exist_ok=True)
    KP_DIR.mkdir(parents=True, exist_ok=True)
    REF_DIR.mkdir(parents=True, exist_ok=True)

    new_specs = [
        {
            "name": "grass_walk_sniff",
            "src": RAW_DIR / "stock-footage-european-hamster-walks-into-view-sniffs-then-moves-away-in-grass.webm",
            "superanimal": "superanimal_quadruped",
            "bp_map": QUADRUPED_MAP,
            "retarget_behaviour": "flat_walk_sniff",
        },
        {
            "name": "flat_mat_eat_walk",
            "src": RAW_DIR / "stock-footage-mouse-eating-a-piece-of-carrot-hamster-eating-little-white-hamster-eating-carrot-held-in-a-child.webm",
            "superanimal": "superanimal_quadruped",
            "bp_map": QUADRUPED_MAP,
            "retarget_behaviour": "flat_eat_walk",
        },
        {
            "name": "rear_sniff_enclosure",
            "src": RAW_DIR / "stock-footage-curious-white-dwarf-hamster-standing-on-hind-legs-and-sniffing-inside-a-pet-enclosure.webm",
            "superanimal": "superanimal_quadruped",
            "bp_map": QUADRUPED_MAP,
            "retarget_behaviour": "rear_sniff",
        },
        {
            "name": "hand_taming_walk",
            "src": RAW_DIR / "stock-footage-a-small-pet-hamster-running-across-a-child-s-hands.webm",
            "superanimal": "superanimal_quadruped",
            "bp_map": QUADRUPED_MAP,
            "retarget_behaviour": "hand_walk",
        },
        {
            "name": "topdown_enclosure_explore",
            "src": RAW_DIR / "stock-footage-hamster-cute-little-animal-pet (4).webm",
            "superanimal": "superanimal_topviewmouse",
            "bp_map": TOPVIEWMOUSE_MAP,
            "retarget_behaviour": None,  # Top-down trajectory & stop-start timing only
        },
    ]

    summary = {}
    overlay_snaps = []

    for spec in new_specs:
        name = spec["name"]
        clip_mp4 = CLIPS_DIR / f"clip_{name}.mp4"
        meta = convert_to_mp4(spec["src"], clip_mp4, max_frames=450)
        print(f"[CONVERT] {name}: {meta}")

        out_sub = DLC_OUT_DIR / f"{name}_{spec['superanimal']}"
        out_sub.mkdir(parents=True, exist_ok=True)
        existing_h5 = sorted(glob.glob(str(out_sub / "*.h5")))
        if not existing_h5:
            print(f"[DLC] Running {spec['superanimal']} on {clip_mp4} ...")
            deeplabcut.video_inference_superanimal(
                videos=[str(clip_mp4)],
                superanimal_name=spec["superanimal"],
                model_name="hrnet_w32",
                detector_name="fasterrcnn_resnet50_fpn_v2",
                dest_folder=str(out_sub),
                batch_size=8,
                detector_batch_size=8,
                max_individuals=1,
                bbox_threshold=0.25,
                pcutoff=0.1,
                device="cuda",
                plot_bboxes=False,
                create_labeled_video=False,
            )
            existing_h5 = sorted(glob.glob(str(out_sub / "*.h5")))

        h5_path = Path(existing_h5[-1])
        raw_csv = KP_DIR / f"{name}_raw.csv"
        clean_csv = KP_DIR / f"{name}_clean.csv"
        ext_info = convert_h5_to_canonical_csv(h5_path, raw_csv, meta["fps"], spec["bp_map"])
        clean_df, clean_met = clean_keypoint_csv(raw_csv, clean_csv)
        walk_stats = analyze_flat_walk_stats(clean_df, meta["fps"])

        retarget_info = None
        if spec["retarget_behaviour"] is not None:
            clip_id = f"real_{name}_REAL"
            ref_clip, ret_met = retarget_side_video_to_mjcf(
                clean_df,
                clip_id=clip_id,
                behaviour_label=spec["retarget_behaviour"],
                source_video=spec["src"].name,
                src_fps=meta["fps"],
                nominal_vx=max(0.08, min(0.22, walk_stats["mean_moving_speed_m_s"])) if "walk" in spec["retarget_behaviour"] else 0.0,
            )
            save_reference_clip(ref_clip, REF_DIR / f"{clip_id}.npz")
            render_mujoco_reference(ref_clip, RENDER_DIR / f"mujoco_ref_{clip_id}.mp4")
            retarget_info = ret_met

        snap = render_keypoint_overlay(
            clip_mp4,
            clean_df,
            RENDER_DIR / f"overlay_{name}_keypoints.mp4",
            f"REAL: {name}",
            max_frames=min(200, len(clean_df)),
        )
        overlay_snaps.append(cv2.resize(snap, (480, 270)))

        summary[name] = {
            "clip": meta,
            "superanimal": spec["superanimal"],
            "cleaning": clean_met,
            "gait_stats": walk_stats,
            "retargeting": retarget_info,
        }

    # Save combined preview sheet
    if len(overlay_snaps) >= 4:
        row1 = np.hstack(overlay_snaps[0:2])
        row2 = np.hstack(overlay_snaps[2:4])
        imageio.imwrite(RENDER_DIR / "new_real_videos_overlays_preview.png", np.vstack([row1, row2]))

    # Merge into gait_statistics.json
    stats_p = REF_DIR / "gait_statistics.json"
    existing_stats = json.loads(stats_p.read_text(encoding="utf-8")) if stats_p.exists() else {}
    existing_stats["real_video_batch2_flat_and_behaviours"] = summary
    stats_p.write_text(json.dumps(existing_stats, indent=2), encoding="utf-8")

    print("\n=== STAGE 2b NEW REAL VIDEOS SUMMARY ===")
    for k, v in summary.items():
        gs = v["gait_stats"]
        cl = v["cleaning"]
        print(f"  {k}: jitter {cl['raw_jitter_px_per_f2']} -> {cl['clean_jitter_px_per_f2']} | speed={gs['mean_moving_speed_m_s']}m/s | freq={gs['stride_freq_hz']}Hz | stride={gs['est_stride_length_m']}m | move_bout={gs['mean_move_bout_s']}s | stop_bout={gs['mean_stop_bout_s']}s")


if __name__ == "__main__":
    main()
