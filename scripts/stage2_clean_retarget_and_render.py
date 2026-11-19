"""Stage 2 Steps 3-6: Clean keypoints, compute gait stats, retarget to MJCF, and render overlays."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import imageio.v2 as imageio
import mujoco
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, savgol_filter

from contracts.locomotion_contracts import (
    ACTUATED_JOINT_NAMES,
    DEFAULT_STAND_JOINTS,
    JOINT_LIMITS_HIGH,
    JOINT_LIMITS_LOW,
    MODEL_VERSION,
    REF_CLIP_SCHEMA_VERSION,
)
from scripts.stage2_generate_synthetic_gaits import generate_all_synthetic_clips
from training.reference_library import ReferenceClip, load_reference_clip, save_reference_clip

KP_DIR = Path("data/keypoints")
CLIPS_DIR = Path("data/clips")
REF_DIR = Path("data/reference_motion")
RENDER_DIR = Path("renders/stage2")
MODEL_PATH = Path("simulation/models/hamster/hamster.xml")

KEYPOINTS = [
    "nose",
    "left_ear",
    "right_ear",
    "neck",
    "mid_spine",
    "tail_base",
    "fl_paw",
    "fr_paw",
    "bl_paw",
    "br_paw",
]

SKELETON_EDGES = [
    ("nose", "left_ear"),
    ("nose", "right_ear"),
    ("nose", "neck"),
    ("neck", "mid_spine"),
    ("mid_spine", "tail_base"),
    ("neck", "fl_paw"),
    ("neck", "fr_paw"),
    ("tail_base", "bl_paw"),
    ("tail_base", "br_paw"),
]


def _rms_accel(arr: np.ndarray) -> float:
    valid = np.isfinite(arr)
    if np.sum(valid) < 5:
        return float("nan")
    s = pd.Series(arr).interpolate(limit_direction="both").to_numpy()
    acc = np.diff(s, n=2)
    return float(np.sqrt(np.mean(acc * acc)))


def clean_keypoint_csv(
    raw_csv: Path,
    clean_csv: Path,
    conf_thresh: float = 0.35,
    max_gap: int = 12,
    smooth_window: int = 7,
) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(raw_csv)
    clean = df[["frame", "time_s"]].copy()

    raw_jitters = []
    clean_jitters = []
    valid_ratios = {}

    for kp in KEYPOINTS:
        x = df[f"{kp}_x"].to_numpy(dtype=float).copy()
        y = df[f"{kp}_y"].to_numpy(dtype=float).copy()
        c = df[f"{kp}_conf"].to_numpy(dtype=float).copy()

        valid_mask = (c >= conf_thresh) & np.isfinite(x) & np.isfinite(y)
        valid_ratios[kp] = round(float(np.mean(valid_mask) * 100.0), 1)

        raw_jx = _rms_accel(np.where(valid_mask, x, np.nan))
        raw_jy = _rms_accel(np.where(valid_mask, y, np.nan))
        if np.isfinite(raw_jx) and np.isfinite(raw_jy):
            raw_jitters.append(float(np.hypot(raw_jx, raw_jy)))

        x_filt = np.where(valid_mask, x, np.nan)
        y_filt = np.where(valid_mask, y, np.nan)

        # Interpolate short gaps (<= max_gap)
        sx = pd.Series(x_filt).interpolate(method="linear", limit=max_gap, limit_direction="both")
        sy = pd.Series(y_filt).interpolate(method="linear", limit=max_gap, limit_direction="both")
        x_arr = sx.to_numpy(dtype=float)
        y_arr = sy.to_numpy(dtype=float)

        # Smooth contiguous finite spans using Savitzky-Golay
        if np.all(np.isfinite(x_arr)) and len(x_arr) >= smooth_window:
            x_arr = savgol_filter(x_arr, smooth_window, 2)
            y_arr = savgol_filter(y_arr, smooth_window, 2)

        cjx = _rms_accel(x_arr)
        cjy = _rms_accel(y_arr)
        if np.isfinite(cjx) and np.isfinite(cjy):
            clean_jitters.append(float(np.hypot(cjx, cjy)))

        clean[f"{kp}_x"] = x_arr
        clean[f"{kp}_y"] = y_arr
        clean[f"{kp}_conf"] = c

    # Compute body centroid & scale normalization (median nose-to-tailbase distance)
    spine_cols_x = [f"{k}_x" for k in ("nose", "neck", "mid_spine", "tail_base")]
    spine_cols_y = [f"{k}_y" for k in ("nose", "neck", "mid_spine", "tail_base")]
    cx = np.nanmean(clean[spine_cols_x].to_numpy(dtype=float), axis=1)
    cy = np.nanmean(clean[spine_cols_y].to_numpy(dtype=float), axis=1)
    cx = pd.Series(cx).interpolate(limit_direction="both").to_numpy()
    cy = pd.Series(cy).interpolate(limit_direction="both").to_numpy()
    clean["body_cx"] = cx
    clean["body_cy"] = cy

    body_len_px = np.hypot(
        clean["nose_x"].to_numpy() - clean["tail_base_x"].to_numpy(),
        clean["nose_y"].to_numpy() - clean["tail_base_y"].to_numpy(),
    )
    med_body_px = float(np.nanmedian(body_len_px)) if np.any(np.isfinite(body_len_px)) else 150.0
    if not np.isfinite(med_body_px) or med_body_px < 20.0:
        med_body_px = 150.0

    clean.to_csv(clean_csv, index=False)
    metrics = {
        "frames": len(clean),
        "raw_jitter_px_per_f2": round(float(np.nanmean(raw_jitters)), 3) if raw_jitters else None,
        "clean_jitter_px_per_f2": round(float(np.nanmean(clean_jitters)), 3) if clean_jitters else None,
        "median_body_length_px": round(med_body_px, 1),
        "valid_pct_at_0_35": valid_ratios,
    }
    return clean, metrics


def analyze_wheel_gait(clean_df: pd.DataFrame, fps: float, syrian_body_len_m: float = 0.145) -> dict:
    """Extract stride frequency and estimated stride length from video6 side-profile wheel run."""
    cx = clean_df["body_cx"].to_numpy(dtype=float)
    body_px = float(
        np.nanmedian(
            np.hypot(
                clean_df["nose_x"] - clean_df["tail_base_x"],
                clean_df["nose_y"] - clean_df["tail_base_y"],
            )
        )
    )
    if not np.isfinite(body_px) or body_px < 20.0:
        body_px = 180.0

    # Pick highest-confidence paw signal relative to body centroid
    best_paw = None
    best_score = -1.0
    for paw in ("fl_paw", "fr_paw", "bl_paw", "br_paw"):
        sc = float(np.nanmean(clean_df[f"{paw}_conf"]))
        if sc > best_score:
            best_score = sc
            best_paw = paw

    paw_rel_x = pd.Series(clean_df[f"{best_paw}_x"].to_numpy() - cx).interpolate(limit_direction="both").to_numpy()
    paw_rel_x = paw_rel_x - np.mean(paw_rel_x)

    # Dominant stride frequency via FFT in plausible rodent running band [1.5, 7.5] Hz
    n = len(paw_rel_x)
    freqs = np.fft.rfftfreq(n, d=1.0 / fps)
    spec = np.abs(np.fft.rfft(paw_rel_x * np.hanning(n)))
    band = (freqs >= 1.5) & (freqs <= 7.5)
    if np.any(band):
        dom_freq_hz = float(freqs[band][np.argmax(spec[band])])
    else:
        dom_freq_hz = 3.5

    # Peak-to-peak paw excursion scaled to Syrian body length
    p95, p05 = np.nanpercentile(paw_rel_x, [95, 5])
    excursion_body_frac = float(np.clip((p95 - p05) / max(body_px, 1.0), 0.15, 0.70))
    est_stride_length_m = excursion_body_frac * syrian_body_len_m
    est_speed_m_s = est_stride_length_m * dom_freq_hz

    return {
        "source_clip": "clip_video6_wheel_run.mp4",
        "source_type": "REAL_VIDEO",
        "dominant_paw_tracked": best_paw,
        "paw_mean_conf": round(best_score, 3),
        "stride_freq_hz": round(dom_freq_hz, 2),
        "stride_period_s": round(1.0 / max(dom_freq_hz, 1e-6), 3),
        "paw_excursion_body_frac": round(excursion_body_frac, 3),
        "scaled_syrian_stride_length_m": round(est_stride_length_m, 4),
        "scaled_syrian_speed_m_s": round(est_speed_m_s, 3),
        "caveat": "Measured from dwarf hamster running on a curved wheel; scaled to 0.145 m Syrian body length.",
    }


def analyze_stop_start_timing(clean_df: pd.DataFrame, fps: float) -> dict:
    """Measure intermittent move/pause bout timing from video7 platform/bridge clip."""
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
    if not np.isfinite(body_px) or body_px < 20.0:
        body_px = 180.0

    vel_px_s = np.hypot(np.gradient(cx) * fps, np.gradient(cy) * fps)
    vel_body_s = vel_px_s / body_px
    # Smooth speed over ~0.3 s
    win = max(5, int(round(0.3 * fps)) | 1)
    if len(vel_body_s) >= win:
        vel_smooth = savgol_filter(vel_body_s, win, 2)
    else:
        vel_smooth = vel_body_s

    moving = vel_smooth > 0.25  # > 0.25 body-lengths/sec
    # Compute contiguous bout lengths
    move_bouts, stop_bouts = [], []
    cur_state = bool(moving[0])
    cur_len = 1
    for m in moving[1:]:
        if bool(m) == cur_state:
            cur_len += 1
        else:
            (move_bouts if cur_state else stop_bouts).append(cur_len / fps)
            cur_state = bool(m)
            cur_len = 1
    (move_bouts if cur_state else stop_bouts).append(cur_len / fps)

    return {
        "source_clip": "clip_video7_platform_walk.mp4",
        "source_type": "REAL_VIDEO",
        "moving_fraction": round(float(np.mean(moving)), 3),
        "num_transitions": int(len(move_bouts) + len(stop_bouts) - 1),
        "mean_move_bout_s": round(float(np.mean(move_bouts)), 2) if move_bouts else 0.0,
        "mean_stop_bout_s": round(float(np.mean(stop_bouts)), 2) if stop_bouts else 0.0,
        "caveat": "Handheld oblique camera; centroid motion includes residual camera pan.",
    }


def retarget_side_video_to_mjcf(
    clean_df: pd.DataFrame,
    clip_id: str,
    behaviour_label: str,
    source_video: str,
    src_fps: float,
    target_fps: float = 50.0,
    nominal_vx: float = 0.0,
) -> tuple[ReferenceClip, dict]:
    """2D sagittal-plane retargeting from side-view keypoints to 16-DoF hamster_mjcf_v1.0.0.

    Measured from 2D video:
      - Spine pitch angle (tail_base -> mid_spine -> neck)
      - Neck pitch angle (mid_spine -> neck -> nose)
      - Sagittal paw fore-aft and vertical excursions -> hip_pitch & knee_pitch
    Estimated / constrained (not observable from single side camera):
      - Lateral abduction (hip_abd = 0) and spine/neck yaw (= 0)
      - Contralateral hidden legs (if occluded, mirrored with 0.5 cycle phase shift for locomotion)
    """
    n_src = len(clean_df)
    dur_s = n_src / max(src_fps, 1e-6)
    n_tgt = max(10, int(round(dur_s * target_fps)))
    t_src = np.arange(n_src, dtype=float) / src_fps
    t_tgt = np.arange(n_tgt, dtype=float) / target_fps

    def interp_col(col: str) -> np.ndarray:
        vals = pd.Series(clean_df[col].to_numpy(dtype=float)).interpolate(limit_direction="both").fillna(0.0).to_numpy()
        return np.interp(t_tgt, t_src, vals)

    nose_x, nose_y = interp_col("nose_x"), interp_col("nose_y")
    neck_x, neck_y = interp_col("neck_x"), interp_col("neck_y")
    mid_x, mid_y = interp_col("mid_spine_x"), interp_col("mid_spine_y")
    tail_x, tail_y = interp_col("tail_base_x"), interp_col("tail_base_y")
    cx, cy = interp_col("body_cx"), interp_col("body_cy")

    # Facing direction (+1 if nose is to right of tail, -1 if left-facing)
    facing = 1.0 if float(np.median(nose_x - tail_x)) >= 0 else -1.0
    body_px = max(float(np.median(np.hypot(nose_x - tail_x, nose_y - tail_y))), 30.0)

    # Spine pitch from (tail -> mid -> neck)
    v1x = facing * (mid_x - tail_x)
    v1y = -(mid_y - tail_y)  # image y is downward
    v2x = facing * (neck_x - mid_x)
    v2y = -(neck_y - mid_y)
    a1 = np.arctan2(v1y, np.maximum(np.abs(v1x), 5.0))
    a2 = np.arctan2(v2y, np.maximum(np.abs(v2x), 5.0))
    spine_pitch_raw = np.clip((a2 - a1) * 0.6, -0.45, 0.45)

    # Neck pitch from (mid -> neck -> nose)
    v3x = facing * (nose_x - neck_x)
    v3y = -(nose_y - neck_y)
    a3 = np.arctan2(v3y, np.maximum(np.abs(v3x), 5.0))
    neck_pitch_raw = np.clip((a3 - a2) * 0.5 - 0.05, -0.50, 0.50)

    q = np.tile(DEFAULT_STAND_JOINTS, (n_tgt, 1)).astype(np.float32)
    q[:, 0] = spine_pitch_raw
    q[:, 2] = neck_pitch_raw

    contacts = np.ones((n_tgt, 4), dtype=np.float32)
    retarget_errs = []

    leg_specs = [
        (0, "fl_paw", 0.25, -0.50),
        (1, "fr_paw", 0.25, -0.50),
        (2, "bl_paw", 0.28, -0.55),
        (3, "br_paw", 0.28, -0.55),
    ]

    for leg_i, paw_name, hb, kb in leg_specs:
        px = interp_col(f"{paw_name}_x")
        py = interp_col(f"{paw_name}_y")
        # Relative fore-aft and vertical paw position normalized by body length
        dx_norm = facing * (px - cx) / body_px
        dy_norm = -(py - cy) / body_px  # positive = higher
        dx_centered = dx_norm - np.median(dx_norm)
        dy_centered = dy_norm - np.median(dy_norm)

        # Map fore-aft excursion to hip_pitch and upward lift to knee_pitch flexion
        hip_raw = hb + 2.2 * dx_centered
        knee_raw = kb - 2.0 * np.maximum(dy_centered, 0.0)

        hip_col = 4 + leg_i * 3
        hip_clamped = np.clip(hip_raw, JOINT_LIMITS_LOW[hip_col + 1], JOINT_LIMITS_HIGH[hip_col + 1])
        knee_clamped = np.clip(knee_raw, JOINT_LIMITS_LOW[hip_col + 2], JOINT_LIMITS_HIGH[hip_col + 2])

        retarget_errs.append(float(np.mean(np.abs(hip_raw - hip_clamped) + np.abs(knee_raw - knee_clamped))))
        q[:, hip_col + 1] = hip_clamped
        q[:, hip_col + 2] = knee_clamped

        # Ground contact: paw near bottom of its vertical range
        y_thresh = np.percentile(dy_centered, 45)
        contacts[:, leg_i] = (dy_centered <= y_thresh).astype(np.float32)

    q = np.clip(q, JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH)

    # Estimate phase from front-left hip oscillation
    fl_sig = q[:, 5] - np.mean(q[:, 5])
    peaks, _ = find_peaks(fl_sig, distance=max(5, int(target_fps / 8.0)))
    if len(peaks) >= 2:
        period_f = float(np.median(np.diff(peaks)))
        phase = ((np.arange(n_tgt) % period_f) / period_f).astype(np.float32)
    else:
        phase = (np.linspace(0.0, 1.0, n_tgt, endpoint=False)).astype(np.float32)

    root_vel = np.zeros((n_tgt, 3), dtype=np.float32)
    root_vel[:, 0] = nominal_vx
    root_pos = np.zeros((n_tgt, 3), dtype=np.float32)
    root_pos[:, 0] = np.cumsum(root_vel[:, 0] / target_fps)
    root_pos[:, 2] = 0.048
    root_yaw_rate = np.zeros(n_tgt, dtype=np.float32)

    clip = ReferenceClip(
        clip_id=clip_id,
        schema_version=REF_CLIP_SCHEMA_VERSION,
        model_version=MODEL_VERSION,
        source_type="REAL_VIDEO",
        behaviour_label=behaviour_label,
        source_video=source_video,
        fps=target_fps,
        joint_names=ACTUATED_JOINT_NAMES,
        joint_angles=q,
        root_pos=root_pos,
        root_vel=root_vel,
        root_yaw_rate=root_yaw_rate,
        foot_contacts=contacts,
        phase=phase,
        is_cyclic=True,
    )
    retarget_metrics = {
        "clip_id": clip_id,
        "source_type": "REAL_VIDEO",
        "mean_limit_clip_err_rad": round(float(np.mean(retarget_errs)), 4),
        "frames_at_50hz": n_tgt,
        "duration_s": round(dur_s, 2),
        "estimated_unobserved_dofs": ["spine_yaw", "neck_yaw", "fl/fr/bl/br_hip_abd"],
    }
    return clip, retarget_metrics


def render_keypoint_overlay(
    video_path: Path,
    clean_df: pd.DataFrame,
    out_video: Path,
    title: str,
    max_frames: int = 240,
) -> np.ndarray:
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames_out = []
    mid_snapshot = None
    n = min(max_frames, len(clean_df))

    colors = {
        "nose": (0, 255, 255),
        "left_ear": (255, 180, 0),
        "right_ear": (255, 120, 0),
        "neck": (0, 220, 0),
        "mid_spine": (0, 180, 0),
        "tail_base": (0, 140, 255),
        "fl_paw": (255, 50, 255),
        "fr_paw": (180, 50, 255),
        "bl_paw": (255, 100, 100),
        "br_paw": (180, 100, 100),
    }

    for i in range(n):
        ok, frame = cap.read()
        if not ok:
            break
        row = clean_df.iloc[i]
        pts = {}
        for kp in KEYPOINTS:
            x, y, c = row[f"{kp}_x"], row[f"{kp}_y"], row[f"{kp}_conf"]
            if np.isfinite(x) and np.isfinite(y):
                pts[kp] = (int(round(x)), int(round(y)), float(c))

        for a, b in SKELETON_EDGES:
            if a in pts and b in pts:
                cv2.line(frame, pts[a][:2], pts[b][:2], (230, 230, 230), 2, cv2.LINE_AA)

        for kp, (ix, iy, c) in pts.items():
            rad = 6 if c >= 0.35 else 4
            cv2.circle(frame, (ix, iy), rad, colors.get(kp, (255, 255, 255)), -1)
            cv2.circle(frame, (ix, iy), rad + 1, (20, 20, 20), 1)

        cv2.rectangle(frame, (0, 0), (frame.shape[1], 34), (20, 20, 25), -1)
        cv2.putText(
            frame,
            f"{title} | frame {i}/{n} | DLC SuperAnimal Cleaned Keypoints",
            (12, 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (240, 240, 240),
            1,
            cv2.LINE_AA,
        )
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frames_out.append(rgb)
        if i == n // 2:
            mid_snapshot = rgb.copy()

    cap.release()
    out_video.parent.mkdir(parents=True, exist_ok=True)
    imageio.mimsave(out_video, frames_out, fps=fps, quality=7)
    return mid_snapshot if mid_snapshot is not None else frames_out[0]


def render_mujoco_reference(
    clip: ReferenceClip,
    out_video: Path,
    max_duration_s: float = 4.0,
) -> np.ndarray:
    model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
    data = mujoco.MjData(model)
    key_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "stand")
    mujoco.mj_resetDataKeyframe(model, data, key_id)

    joint_qadr = [
        model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, jn)]
        for jn in ACTUATED_JOINT_NAMES
    ]

    scene_opt = mujoco.MjvOption()
    scene_opt.geomgroup[2] = 1
    scene_opt.geomgroup[3] = 0
    renderer = mujoco.Renderer(model, height=360, width=640)

    render_fps = 25
    dur = min(max_duration_s, clip.duration_s)
    n_frames = int(round(dur * render_fps))
    frames = []
    mid_snap = None
    yaw_acc = 0.0

    for i in range(n_frames):
        t = i / render_fps
        ref = clip.sample_at_time(t)
        yaw_acc += float(ref["root_yaw_rate"]) / render_fps

        # Kinematic playback of reference clip inside MuJoCo
        mujoco.mj_resetDataKeyframe(model, data, key_id)
        f_idx = min(int(round(t * clip.fps)), clip.num_frames - 1)
        data.qpos[0:3] = clip.root_pos[f_idx]
        data.qpos[3:7] = np.array([np.cos(yaw_acc / 2.0), 0.0, 0.0, np.sin(yaw_acc / 2.0)])
        for j_idx, qadr in enumerate(joint_qadr):
            data.qpos[qadr] = float(ref["joint_angles"][j_idx])
        mujoco.mj_forward(model, data)

        renderer.update_scene(data, camera="track_three_quarter", scene_option=scene_opt)
        img = renderer.render().copy()

        badge_color = (220, 120, 20) if clip.source_type == "SYNTHETIC" else (30, 170, 70)
        cv2.rectangle(img, (0, 0), (640, 34), (20, 22, 28), -1)
        cv2.rectangle(img, (8, 5), (125, 29), badge_color, -1)
        cv2.putText(img, clip.source_type, (14, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(
            img,
            f"{clip.behaviour_label} | v={clip.mean_speed_m_s:.2f}m/s | t={t:.2f}s",
            (136, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (240, 240, 240),
            1,
            cv2.LINE_AA,
        )
        frames.append(img)
        if i == n_frames // 2:
            mid_snap = img.copy()

    renderer.close()
    out_video.parent.mkdir(parents=True, exist_ok=True)
    imageio.mimsave(out_video, frames, fps=render_fps, quality=7)
    return mid_snap if mid_snap is not None else frames[0]


def main() -> None:
    REF_DIR.mkdir(parents=True, exist_ok=True)
    RENDER_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Clean all 3 real-video keypoint CSVs
    clean_metrics = {}
    clean_dfs = {}
    fps_map = {
        "video1_syrian_groom": 25.0,
        "video6_wheel_run": 23.976,
        "video7_platform_walk": 30.0,
    }
    for name, fps in fps_map.items():
        raw_p = KP_DIR / f"{name}_raw.csv"
        clean_p = KP_DIR / f"{name}_clean.csv"
        df_c, met = clean_keypoint_csv(raw_p, clean_p)
        clean_dfs[name] = df_c
        clean_metrics[name] = met

    # 2. Compute real-video gait & timing statistics
    wheel_stats = analyze_wheel_gait(clean_dfs["video6_wheel_run"], fps=23.976)
    stop_start_stats = analyze_stop_start_timing(clean_dfs["video7_platform_walk"], fps=30.0)

    # 3. Retarget real side-view clips to MJCF
    real_v1, ret_v1 = retarget_side_video_to_mjcf(
        clean_dfs["video1_syrian_groom"],
        clip_id="real_video1_groom_REAL",
        behaviour_label="crouch_groom",
        source_video="hamster-video1.mp4",
        src_fps=25.0,
        nominal_vx=0.0,
    )
    save_reference_clip(real_v1, REF_DIR / "real_video1_groom_REAL.npz")

    real_v6, ret_v6 = retarget_side_video_to_mjcf(
        clean_dfs["video6_wheel_run"],
        clip_id="real_video6_wheel_run_REAL",
        behaviour_label="wheel_run",
        source_video="hamster-video6.mp4",
        src_fps=23.976,
        nominal_vx=wheel_stats["scaled_syrian_speed_m_s"],
    )
    save_reference_clip(real_v6, REF_DIR / "real_video6_wheel_run_REAL.npz")

    # 4. Generate explicitly marked SYNTHETIC procedural walk/trot/turn/stop clips
    synth_summary = generate_all_synthetic_clips()

    # 5. Save consolidated gait_statistics.json
    gait_stats = {
        "real_video_cleaning": clean_metrics,
        "real_video_measured": {
            "wheel_running_video6": wheel_stats,
            "stop_start_video7": stop_start_stats,
        },
        "retargeting_metrics": {
            "real_video1_groom_REAL": ret_v1,
            "real_video6_wheel_run_REAL": ret_v6,
        },
        "synthetic_reference_targets": {
            "label": "SYNTHETIC (ANIMATION-DRIVEN / PROCEDURAL FALLBACK)",
            "walk_slow_target": {"speed_m_s": 0.12, "stride_freq_hz": 2.6, "stride_length_m": 0.046},
            "trot_medium_target": {"speed_m_s": 0.22, "stride_freq_hz": 4.0, "stride_length_m": 0.055},
            "stop_start_target": {"move_bout_s": 1.4, "stop_bout_s": 1.0},
            "clips": synth_summary,
        },
    }
    stats_path = REF_DIR / "gait_statistics.json"
    stats_path.write_text(json.dumps(gait_stats, indent=2), encoding="utf-8")

    # 6. Render keypoint overlay videos + preview contact sheet
    ov1 = render_keypoint_overlay(
        CLIPS_DIR / "clip_video1_syrian_groom.mp4",
        clean_dfs["video1_syrian_groom"],
        RENDER_DIR / "overlay_video1_keypoints.mp4",
        "Video1 (Syrian Groom)",
    )
    ov6 = render_keypoint_overlay(
        CLIPS_DIR / "clip_video6_wheel_run.mp4",
        clean_dfs["video6_wheel_run"],
        RENDER_DIR / "overlay_video6_wheel_keypoints.mp4",
        "Video6 (Wheel Run)",
    )
    ov7 = render_keypoint_overlay(
        CLIPS_DIR / "clip_video7_platform_walk.mp4",
        clean_dfs["video7_platform_walk"],
        RENDER_DIR / "overlay_video7_walk_keypoints.mp4",
        "Video7 (Platform Walk/Rear)",
    )
    ov_sheet = np.hstack([cv2.resize(im, (480, 270)) for im in (ov1, ov6, ov7)])
    imageio.imwrite(RENDER_DIR / "stage2_keypoint_overlays_preview.png", ov_sheet)

    # 7. Render MuJoCo reference-motion playback videos + 4-panel preview PNG
    ref_v6_snap = render_mujoco_reference(real_v6, RENDER_DIR / "mujoco_ref_video6_wheel_REAL.mp4")
    ref_walk = load_reference_clip(REF_DIR / "walk_slow_SYNTHETIC.npz")
    ref_trot = load_reference_clip(REF_DIR / "trot_medium_SYNTHETIC.npz")
    ref_ss = load_reference_clip(REF_DIR / "stop_start_SYNTHETIC.npz")

    s_walk = render_mujoco_reference(ref_walk, RENDER_DIR / "mujoco_ref_walk_slow_SYNTHETIC.mp4")
    s_trot = render_mujoco_reference(ref_trot, RENDER_DIR / "mujoco_ref_trot_medium_SYNTHETIC.mp4")
    s_ss = render_mujoco_reference(ref_ss, RENDER_DIR / "mujoco_ref_stop_start_SYNTHETIC.mp4")

    mj_sheet = np.vstack([np.hstack([ref_v6_snap, s_walk]), np.hstack([s_trot, s_ss])])
    imageio.imwrite(RENDER_DIR / "stage2_mujoco_refs_preview.png", mj_sheet)

    print(json.dumps(gait_stats, indent=2))


if __name__ == "__main__":
    main()
