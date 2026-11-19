"""Stage 2.7 Fallback: Generate explicitly marked SYNTHETIC procedural Syrian hamster gait clips.

All outputs carry:
  - Filename suffix `_SYNTHETIC.npz`
  - Metadata `source_type = "SYNTHETIC"`
  - Behaviour label (`walk_slow`, `trot_medium`, `turn_left`, `turn_right`, `stop_start`)
  - Joint angles strictly within `hamster_mjcf_v1.0.0` limits.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from contracts.locomotion_contracts import (
    ACTUATED_JOINT_NAMES,
    DEFAULT_STAND_JOINTS,
    JOINT_LIMITS_HIGH,
    JOINT_LIMITS_LOW,
    MODEL_VERSION,
    REF_CLIP_SCHEMA_VERSION,
)
from training.reference_library import ReferenceClip, save_reference_clip

OUT_DIR = Path("data/reference_motion")


def _leg_cycle(
    phi: np.ndarray,
    duty_factor: float,
    hip_amp: float,
    knee_lift: float,
    hip_base: float,
    knee_base: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate smooth stance/swing hip_pitch, knee_pitch, and foot contact for one leg."""
    p = phi % 1.0
    in_stance = p < duty_factor
    hip = np.zeros_like(p, dtype=np.float32)
    knee = np.zeros_like(p, dtype=np.float32)
    contact = in_stance.astype(np.float32)

    # Right-hand rule around +Y axis on downward leg (0,0,-L):
    #   -hip_pitch swings paw FORWARD (+X); +hip_pitch pushes paw BACKWARD (-X).
    # Stance phase: paw sweeps front (-amp) -> rear (+amp) to propel body +X forward!
    s = np.where(in_stance, p / max(duty_factor, 1e-6), 0.0)
    # Swing phase: knee lifts paw while hip returns rear (+amp) -> front (-amp)
    w = np.where(~in_stance, (p - duty_factor) / max(1.0 - duty_factor, 1e-6), 0.0)

    hip_stance = hip_base - hip_amp * np.cos(np.pi * s)
    hip_swing = hip_base + hip_amp * np.cos(np.pi * w)
    hip = np.where(in_stance, hip_stance, hip_swing).astype(np.float32)

    knee_stance = knee_base + 0.06 * np.sin(np.pi * s)
    knee_swing = knee_base - knee_lift * np.sin(np.pi * w)
    knee = np.where(in_stance, knee_stance, knee_swing).astype(np.float32)
    return hip, knee, contact


def build_gait_clip(
    clip_id: str,
    behaviour_label: str,
    fps: float,
    duration_s: float,
    vx_m_s: float,
    yaw_rate_rad_s: float,
    freq_hz: float,
    duty_factor: float,
    phase_offsets: tuple[float, float, float, float],  # (fl, fr, bl, br)
    hip_amp: float,
    knee_lift: float,
    speed_envelope: np.ndarray | None = None,
    is_cyclic: bool = True,
) -> ReferenceClip:
    n = int(round(duration_s * fps))
    t = np.arange(n, dtype=np.float32) / fps
    if speed_envelope is None:
        env = np.ones(n, dtype=np.float32)
    else:
        env = speed_envelope.astype(np.float32)

    # Integrate phase according to speed envelope so legs freeze cleanly when stopped
    dphi = (freq_hz / fps) * env
    phase = np.cumsum(dphi) % 1.0

    q = np.tile(DEFAULT_STAND_JOINTS, (n, 1)).astype(np.float32)
    contacts = np.ones((n, 4), dtype=np.float32)

    # Spine & neck coordination (subtle natural lateral bend + pitch bob)
    q[:, 0] = 0.04 * env * np.sin(4.0 * np.pi * phase)  # spine_pitch
    q[:, 1] = (0.14 * np.clip(yaw_rate_rad_s, -1.0, 1.0) + 0.06 * env * np.sin(2.0 * np.pi * phase))  # spine_yaw
    q[:, 2] = -0.05 - 0.03 * env * np.sin(4.0 * np.pi * phase)  # neck_pitch
    q[:, 3] = 0.22 * np.clip(yaw_rate_rad_s, -1.0, 1.0)  # neck_yaw (looks into turn)

    # Turn asymmetry: outer legs take slightly longer strides
    left_scale = 1.0 - 0.25 * np.clip(yaw_rate_rad_s, -1.0, 1.0)
    right_scale = 1.0 + 0.25 * np.clip(yaw_rate_rad_s, -1.0, 1.0)
    leg_scales = (left_scale, right_scale, left_scale, right_scale)
    leg_bases = (
        (0.25, -0.50),  # FL
        (0.25, -0.50),  # FR
        (0.28, -0.55),  # BL
        (0.28, -0.55),  # BR
    )

    for leg_i, (off, sc, (hb, kb)) in enumerate(zip(phase_offsets, leg_scales, leg_bases)):
        hp, kp, fc = _leg_cycle(
            phase + off,
            duty_factor=duty_factor,
            hip_amp=hip_amp * sc,
            knee_lift=knee_lift,
            hip_base=hb,
            knee_base=kb,
        )
        # Blend smoothly to standing pose when env -> 0
        hip_col = 4 + leg_i * 3
        q[:, hip_col] = 0.04 * np.clip(yaw_rate_rad_s, -1.0, 1.0) * env  # hip_abd
        q[:, hip_col + 1] = (1.0 - env) * hb + env * hp
        q[:, hip_col + 2] = (1.0 - env) * kb + env * kp
        contacts[:, leg_i] = np.where(env < 0.15, 1.0, fc)

    q = np.clip(q, JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH)

    # Integrate root trajectory
    yaw_hist = np.cumsum((yaw_rate_rad_s * env) / fps)
    vx_t = vx_m_s * env * np.cos(yaw_hist)
    vy_t = vx_m_s * env * np.sin(yaw_hist)
    vz_t = np.zeros(n, dtype=np.float32)
    root_vel = np.stack([vx_t, vy_t, vz_t], axis=1).astype(np.float32)
    root_pos = np.zeros((n, 3), dtype=np.float32)
    root_pos[:, 0] = np.cumsum(vx_t / fps)
    root_pos[:, 1] = np.cumsum(vy_t / fps)
    root_pos[:, 2] = 0.048 + 0.002 * env * np.sin(4.0 * np.pi * phase)
    root_yaw_rate = (yaw_rate_rad_s * env).astype(np.float32)

    return ReferenceClip(
        clip_id=clip_id,
        schema_version=REF_CLIP_SCHEMA_VERSION,
        model_version=MODEL_VERSION,
        source_type="SYNTHETIC",
        behaviour_label=behaviour_label,
        source_video="PROCEDURAL_GAIT_GENERATOR_SYNTHETIC",
        fps=fps,
        joint_names=ACTUATED_JOINT_NAMES,
        joint_angles=q,
        root_pos=root_pos,
        root_vel=root_vel,
        root_yaw_rate=root_yaw_rate,
        foot_contacts=contacts,
        phase=phase.astype(np.float32),
        is_cyclic=is_cyclic,
    )


def generate_all_synthetic_clips() -> list[dict]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fps = 50.0

    # Stop-start smooth envelope: 0-1.4s walk -> 1.4-2.6s pause -> 2.6-4.0s walk
    n_ss = int(round(4.0 * fps))
    t_ss = np.arange(n_ss, dtype=np.float32) / fps
    env_ss = np.ones(n_ss, dtype=np.float32)
    # Smooth cosine ramp down [1.2, 1.5], hold 0 [1.5, 2.5], ramp up [2.5, 2.8]
    down = (t_ss >= 1.2) & (t_ss < 1.5)
    hold = (t_ss >= 1.5) & (t_ss < 2.5)
    up = (t_ss >= 2.5) & (t_ss < 2.8)
    env_ss[down] = 0.5 * (1.0 + np.cos(np.pi * (t_ss[down] - 1.2) / 0.3))
    env_ss[hold] = 0.0
    env_ss[up] = 0.5 * (1.0 - np.cos(np.pi * (t_ss[up] - 2.5) / 0.3))

    specs = [
        # Lateral-sequence walk (FL=0.0, BR=0.25, FR=0.50, BL=0.75)
        build_gait_clip(
            clip_id="walk_slow_SYNTHETIC",
            behaviour_label="walk_slow",
            fps=fps,
            duration_s=3.0,
            vx_m_s=0.12,
            yaw_rate_rad_s=0.0,
            freq_hz=2.6,
            duty_factor=0.68,
            phase_offsets=(0.0, 0.50, 0.75, 0.25),
            hip_amp=0.30,
            knee_lift=0.32,
        ),
        # Diagonal-pair trot (FL+BR in phase, FR+BL half-cycle out of phase)
        build_gait_clip(
            clip_id="trot_medium_SYNTHETIC",
            behaviour_label="trot_medium",
            fps=fps,
            duration_s=3.0,
            vx_m_s=0.22,
            yaw_rate_rad_s=0.0,
            freq_hz=4.0,
            duty_factor=0.55,
            phase_offsets=(0.0, 0.50, 0.50, 0.0),
            hip_amp=0.40,
            knee_lift=0.40,
        ),
        # Turning left while walking
        build_gait_clip(
            clip_id="turn_left_SYNTHETIC",
            behaviour_label="turn_left",
            fps=fps,
            duration_s=3.0,
            vx_m_s=0.14,
            yaw_rate_rad_s=0.80,
            freq_hz=3.0,
            duty_factor=0.62,
            phase_offsets=(0.0, 0.50, 0.50, 0.0),
            hip_amp=0.32,
            knee_lift=0.34,
        ),
        # Turning right while walking
        build_gait_clip(
            clip_id="turn_right_SYNTHETIC",
            behaviour_label="turn_right",
            fps=fps,
            duration_s=3.0,
            vx_m_s=0.14,
            yaw_rate_rad_s=-0.80,
            freq_hz=3.0,
            duty_factor=0.62,
            phase_offsets=(0.0, 0.50, 0.50, 0.0),
            hip_amp=0.32,
            knee_lift=0.34,
        ),
        # Intermittent stop-start locomotion
        build_gait_clip(
            clip_id="stop_start_SYNTHETIC",
            behaviour_label="stop_start",
            fps=fps,
            duration_s=4.0,
            vx_m_s=0.15,
            yaw_rate_rad_s=0.0,
            freq_hz=3.0,
            duty_factor=0.65,
            phase_offsets=(0.0, 0.50, 0.75, 0.25),
            hip_amp=0.32,
            knee_lift=0.34,
            speed_envelope=env_ss,
            is_cyclic=False,
        ),
    ]

    summary = []
    for clip in specs:
        out_path = OUT_DIR / f"{clip.clip_id}.npz"
        save_reference_clip(clip, out_path)
        summary.append(
            {
                "clip_id": clip.clip_id,
                "path": str(out_path),
                "source_type": clip.source_type,
                "behaviour_label": clip.behaviour_label,
                "fps": clip.fps,
                "frames": clip.num_frames,
                "duration_s": clip.duration_s,
                "mean_speed_m_s": round(clip.mean_speed_m_s, 3),
                "mean_yaw_rate_rad_s": round(clip.mean_yaw_rate_rad_s, 3),
            }
        )
    return summary


if __name__ == "__main__":
    res = generate_all_synthetic_clips()
    print(json.dumps(res, indent=2))
