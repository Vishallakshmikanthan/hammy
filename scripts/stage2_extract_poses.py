"""Stage 2 Step 1: Trim clean segments and run DeepLabCut 3.0 SuperAnimal pose estimation."""

from __future__ import annotations

import glob
import json
from pathlib import Path

import cv2
import deeplabcut
import numpy as np
import pandas as pd

CLIPS_DIR = Path("data/clips")
DLC_OUT_DIR = Path("data/keypoints/dlc_raw")
KP_DIR = Path("data/keypoints")


def trim_clip(
    src: Path,
    dst: Path,
    start_s: float,
    end_s: float | None,
    target_width: int = 960,
) -> dict:
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    start_f = int(round(start_s * fps))
    end_f = total if end_s is None else min(total, int(round(end_s * fps)))

    scale = min(1.0, target_width / max(w, 1))
    out_w = int(round(w * scale)) // 2 * 2
    out_h = int(round(h * scale)) // 2 * 2

    dst.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(dst),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (out_w, out_h),
    )
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
    written = 0
    for _ in range(start_f, end_f):
        ok, frame = cap.read()
        if not ok:
            break
        if scale < 1.0:
            frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_AREA)
        writer.write(frame)
        written += 1
    writer.release()
    cap.release()
    return {
        "src": str(src),
        "dst": str(dst),
        "fps": round(fps, 3),
        "frames": written,
        "width": out_w,
        "height": out_h,
        "duration_s": round(written / max(fps, 1e-6), 2),
    }


# Map SuperAnimal bodypart names -> canonical HAMSTER 10-keypoint schema
QUADRUPED_MAP = {
    "nose": ["nose"],
    "left_ear": ["left_earbase", "left_earend", "left_ear"],
    "right_ear": ["right_earbase", "right_earend", "right_ear"],
    "neck": ["neck_base", "throat_base", "throat_end"],
    "mid_spine": ["back_middle", "back_base", "withers"],
    "tail_base": ["tail_base", "back_end"],
    "fl_paw": ["front_left_paw", "front_left_knee", "front_left_thai"],
    "fr_paw": ["front_right_paw", "front_right_knee", "front_right_thai"],
    "bl_paw": ["back_left_paw", "back_left_knee", "back_left_thai"],
    "br_paw": ["back_right_paw", "back_right_knee", "back_right_thai"],
}

TOPVIEWMOUSE_MAP = {
    "nose": ["nose"],
    "left_ear": ["left_ear", "left_ear_tip"],
    "right_ear": ["right_ear", "right_ear_tip"],
    "neck": ["neck", "head_midpoint"],
    "mid_spine": ["mid_back", "mid_backend", "mouse_center"],
    "tail_base": ["tail_base", "tail1"],
    "fl_paw": ["left_shoulder", "left_midside"],
    "fr_paw": ["right_shoulder", "right_midside"],
    "bl_paw": ["left_hip", "left_midside"],
    "br_paw": ["right_hip", "right_midside"],
}


def convert_h5_to_canonical_csv(
    h5_path: Path,
    csv_out: Path,
    fps: float,
    bp_map: dict[str, list[str]],
) -> dict:
    df = pd.read_hdf(str(h5_path))
    # Flatten multi-index columns: handle both 3-level (scorer, bodypart, coord) and 4-level (scorer, individual, bodypart, coord)
    n_levels = df.columns.nlevels
    available_bps = set(df.columns.get_level_values(n_levels - 2))

    n_frames = len(df)
    out = pd.DataFrame(
        {
            "frame": np.arange(n_frames, dtype=int),
            "time_s": np.arange(n_frames, dtype=float) / max(fps, 1e-6),
        }
    )

    stats = {}
    for canon, candidates in bp_map.items():
        chosen = None
        for cand in candidates:
            if cand in available_bps:
                chosen = cand
                break
        if chosen is None:
            out[f"{canon}_x"] = np.nan
            out[f"{canon}_y"] = np.nan
            out[f"{canon}_conf"] = 0.0
            stats[canon] = {"matched": None, "mean_conf": 0.0, "valid_pct": 0.0}
            continue

        # Select first individual if multi-animal
        if n_levels == 4:
            scorer = df.columns.get_level_values(0)[0]
            indiv = df.columns.get_level_values(1)[0]
            sub = df[(scorer, indiv, chosen)]
        else:
            scorer = df.columns.get_level_values(0)[0]
            sub = df[(scorer, chosen)]

        x = pd.to_numeric(sub["x"], errors="coerce").to_numpy(dtype=float)
        y = pd.to_numeric(sub["y"], errors="coerce").to_numpy(dtype=float)
        c = pd.to_numeric(sub["likelihood"], errors="coerce").fillna(0.0).to_numpy(dtype=float)

        out[f"{canon}_x"] = x
        out[f"{canon}_y"] = y
        out[f"{canon}_conf"] = c
        stats[canon] = {
            "matched": chosen,
            "mean_conf": round(float(np.nanmean(c)), 3),
            "valid_pct": round(float(np.mean(c >= 0.35) * 100.0), 1),
        }

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(csv_out, index=False)
    return {
        "h5_path": str(h5_path),
        "csv_path": str(csv_out),
        "frames": n_frames,
        "available_bodyparts_count": len(available_bps),
        "keypoints": stats,
    }


def main() -> None:
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    DLC_OUT_DIR.mkdir(parents=True, exist_ok=True)
    KP_DIR.mkdir(parents=True, exist_ok=True)

    clip_specs = [
        {
            "name": "video1_syrian_groom",
            "src": Path("data/raw_video/hamster-video1.mp4"),
            "start_s": 0.0,
            "end_s": None,
            "superanimal": "superanimal_quadruped",
            "bp_map": QUADRUPED_MAP,
        },
        {
            "name": "video6_wheel_run",
            "src": Path("data/raw_video/hamster-video6.mp4"),
            "start_s": 15.0,
            "end_s": 27.0,
            "superanimal": "superanimal_quadruped",
            "bp_map": QUADRUPED_MAP,
        },
        {
            "name": "video7_platform_walk",
            "src": Path("data/raw_video/hamster-video7.mp4"),
            "start_s": 35.0,
            "end_s": 55.0,
            "superanimal": "superanimal_quadruped",
            "bp_map": QUADRUPED_MAP,
        },
    ]

    report = {}
    for spec in clip_specs:
        clip_path = CLIPS_DIR / f"clip_{spec['name']}.mp4"
        if not clip_path.exists():
            meta = trim_clip(spec["src"], clip_path, spec["start_s"], spec["end_s"])
            print(f"[TRIM] {spec['name']}: {meta}")
        else:
            cap = cv2.VideoCapture(str(clip_path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            meta = {"src": str(spec["src"]), "dst": str(clip_path), "fps": round(fps, 3), "frames": frames, "width": w, "height": h, "duration_s": round(frames / max(fps, 1e-6), 2)}

        out_sub = DLC_OUT_DIR / f"{spec['name']}_{spec['superanimal']}"
        out_sub.mkdir(parents=True, exist_ok=True)
        existing_h5 = sorted(glob.glob(str(out_sub / "*.h5")))
        if not existing_h5:
            # Also check legacy folder name without superanimal suffix for video1/video6
            legacy_h5 = sorted(glob.glob(str((DLC_OUT_DIR / spec["name"]) / f"*{spec['superanimal']}*.h5")))
            if legacy_h5:
                existing_h5 = legacy_h5

        if not existing_h5:
            print(f"[DLC] Running {spec['superanimal']} on {clip_path} ...")
            deeplabcut.video_inference_superanimal(
                videos=[str(clip_path)],
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

        if not existing_h5:
            raise RuntimeError(f"No .h5 output produced for {spec['name']} in {out_sub}")
        h5_path = Path(existing_h5[-1])
        csv_path = KP_DIR / f"{spec['name']}_raw.csv"
        conv = convert_h5_to_canonical_csv(h5_path, csv_path, meta["fps"], spec["bp_map"])
        report[spec["name"]] = {"clip": meta, "superanimal": spec["superanimal"], "extraction": conv}

    report_path = KP_DIR / "extraction_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[DONE] Saved report to {report_path}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
