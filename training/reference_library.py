"""Unified, source-agnostic reference motion library for HAMSTER Stage 2 & Stage 3.

Supports drop-in replacement or blending of REAL_VIDEO and SYNTHETIC reference clips
without modifying Stage 3 RL training code. Every clip carries explicit provenance
(`source_type` in {"REAL_VIDEO", "SYNTHETIC"}) and morphology version checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from contracts.locomotion_contracts import (
    ACTUATED_JOINT_NAMES,
    JOINT_LIMITS_HIGH,
    JOINT_LIMITS_LOW,
    MODEL_VERSION,
    NUM_ACTUATED_JOINTS,
    REF_CLIP_SCHEMA_VERSION,
)

SourceType = Literal["REAL_VIDEO", "SYNTHETIC"]
SourceFilter = Literal["all", "mixed", "synthetic", "real"]


@dataclass
class ReferenceClip:
    clip_id: str
    schema_version: str
    model_version: str
    source_type: SourceType
    behaviour_label: str
    source_video: str
    fps: float
    joint_names: tuple[str, ...]
    joint_angles: np.ndarray     # [T, 16] float32, rad
    root_pos: np.ndarray         # [T, 3] float32, m
    root_vel: np.ndarray         # [T, 3] float32, m/s
    root_yaw_rate: np.ndarray    # [T] float32, rad/s
    foot_contacts: np.ndarray    # [T, 4] float32, [fl, fr, bl, br] in [0, 1]
    phase: np.ndarray            # [T] float32 in [0, 1)
    is_cyclic: bool = True

    @property
    def num_frames(self) -> int:
        return int(self.joint_angles.shape[0])

    @property
    def duration_s(self) -> float:
        return float(self.num_frames / max(self.fps, 1e-6))

    @property
    def mean_speed_m_s(self) -> float:
        return float(np.mean(np.linalg.norm(self.root_vel[:, :2], axis=1)))

    @property
    def mean_yaw_rate_rad_s(self) -> float:
        return float(np.mean(self.root_yaw_rate))

    def validate(self) -> None:
        if self.schema_version != REF_CLIP_SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema_version: {self.schema_version}")
        if self.model_version != MODEL_VERSION:
            raise ValueError(f"Model version mismatch: {self.model_version} != {MODEL_VERSION}")
        if self.source_type not in ("REAL_VIDEO", "SYNTHETIC"):
            raise ValueError(f"Invalid source_type: {self.source_type}")
        if tuple(self.joint_names) != ACTUATED_JOINT_NAMES:
            raise ValueError("joint_names do not match canonical ACTUATED_JOINT_NAMES")
        t = self.num_frames
        if t < 2:
            raise ValueError("Clip must contain at least 2 frames")
        if self.joint_angles.shape != (t, NUM_ACTUATED_JOINTS):
            raise ValueError(f"Bad joint_angles shape: {self.joint_angles.shape}")
        if self.root_pos.shape != (t, 3) or self.root_vel.shape != (t, 3):
            raise ValueError("Bad root_pos or root_vel shape")
        if self.root_yaw_rate.shape != (t,):
            raise ValueError("Bad root_yaw_rate shape")
        if self.foot_contacts.shape != (t, 4) or self.phase.shape != (t,):
            raise ValueError("Bad foot_contacts or phase shape")
        for arr_name, arr in (
            ("joint_angles", self.joint_angles),
            ("root_pos", self.root_pos),
            ("root_vel", self.root_vel),
            ("root_yaw_rate", self.root_yaw_rate),
            ("foot_contacts", self.foot_contacts),
            ("phase", self.phase),
        ):
            if not np.all(np.isfinite(arr)):
                raise ValueError(f"{arr_name} contains non-finite values")
        eps = 1e-4
        if np.any(self.joint_angles < JOINT_LIMITS_LOW - eps) or np.any(
            self.joint_angles > JOINT_LIMITS_HIGH + eps
        ):
            raise ValueError("joint_angles exceed MJCF joint limits")

    def sample_at_time(self, t_sec: float) -> dict[str, np.ndarray]:
        """Linearly interpolate reference state at time t_sec."""
        if self.is_cyclic and self.duration_s > 0:
            t_mod = float(t_sec % self.duration_s)
        else:
            t_mod = float(np.clip(t_sec, 0.0, max(self.duration_s - 1.0 / self.fps, 0.0)))
        f_float = t_mod * self.fps
        i0 = int(np.floor(f_float)) % self.num_frames
        i1 = (i0 + 1) % self.num_frames if self.is_cyclic else min(i0 + 1, self.num_frames - 1)
        alpha = float(f_float - np.floor(f_float))

        q = (1.0 - alpha) * self.joint_angles[i0] + alpha * self.joint_angles[i1]
        rvel = (1.0 - alpha) * self.root_vel[i0] + alpha * self.root_vel[i1]
        ryaw = float((1.0 - alpha) * self.root_yaw_rate[i0] + alpha * self.root_yaw_rate[i1])
        fc = (1.0 - alpha) * self.foot_contacts[i0] + alpha * self.foot_contacts[i1]
        # Circular phase interpolation
        p0 = 2.0 * np.pi * self.phase[i0]
        p1 = 2.0 * np.pi * self.phase[i1]
        sin_p = (1.0 - alpha) * np.sin(p0) + alpha * np.sin(p1)
        cos_p = (1.0 - alpha) * np.cos(p0) + alpha * np.cos(p1)
        norm = float(np.hypot(sin_p, cos_p))
        if norm > 1e-6:
            sin_p /= norm
            cos_p /= norm

        return {
            "joint_angles": q.astype(np.float32),
            "root_vel": rvel.astype(np.float32),
            "root_yaw_rate": np.float32(ryaw),
            "foot_contacts": fc.astype(np.float32),
            "ref_phase": np.array([sin_p, cos_p], dtype=np.float32),
        }


def save_reference_clip(clip: ReferenceClip, path: Path) -> Path:
    clip.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Enforce explicit SYNTHETIC filename tagging per project rules
    if clip.source_type == "SYNTHETIC" and "SYNTHETIC" not in path.stem:
        raise ValueError(f"SYNTHETIC clip filename must include 'SYNTHETIC': {path.name}")
    np.savez_compressed(
        str(path),
        clip_id=np.array(clip.clip_id),
        schema_version=np.array(clip.schema_version),
        model_version=np.array(clip.model_version),
        source_type=np.array(clip.source_type),
        behaviour_label=np.array(clip.behaviour_label),
        source_video=np.array(clip.source_video),
        fps=np.array(clip.fps, dtype=np.float32),
        joint_names=np.array(clip.joint_names),
        joint_angles=clip.joint_angles.astype(np.float32),
        root_pos=clip.root_pos.astype(np.float32),
        root_vel=clip.root_vel.astype(np.float32),
        root_yaw_rate=clip.root_yaw_rate.astype(np.float32),
        foot_contacts=clip.foot_contacts.astype(np.float32),
        phase=clip.phase.astype(np.float32),
        is_cyclic=np.array(clip.is_cyclic, dtype=bool),
    )
    return path


def load_reference_clip(path: Path) -> ReferenceClip:
    d = np.load(str(path), allow_pickle=False)
    clip = ReferenceClip(
        clip_id=str(d["clip_id"]),
        schema_version=str(d["schema_version"]),
        model_version=str(d["model_version"]),
        source_type=str(d["source_type"]),  # type: ignore[arg-type]
        behaviour_label=str(d["behaviour_label"]),
        source_video=str(d["source_video"]),
        fps=float(d["fps"]),
        joint_names=tuple(str(x) for x in d["joint_names"]),
        joint_angles=np.asarray(d["joint_angles"], dtype=np.float32),
        root_pos=np.asarray(d["root_pos"], dtype=np.float32),
        root_vel=np.asarray(d["root_vel"], dtype=np.float32),
        root_yaw_rate=np.asarray(d["root_yaw_rate"], dtype=np.float32),
        foot_contacts=np.asarray(d["foot_contacts"], dtype=np.float32),
        phase=np.asarray(d["phase"], dtype=np.float32),
        is_cyclic=bool(d["is_cyclic"]),
    )
    clip.validate()
    return clip


class ReferenceMotionLibrary:
    """Source-agnostic loader for Stage 3 imitation RL.

    Filtering modes:
      - "synthetic": load only SYNTHETIC clips
      - "real":      load only REAL_VIDEO clips
      - "mixed"/"all": load both REAL_VIDEO and SYNTHETIC clips
    """

    def __init__(
        self,
        ref_dir: str | Path = "data/reference_motion",
        source_filter: SourceFilter = "mixed",
        behaviours: list[str] | None = None,
    ) -> None:
        self.ref_dir = Path(ref_dir)
        self.source_filter = source_filter
        self.clips: list[ReferenceClip] = []

        if not self.ref_dir.exists():
            return

        for npz_path in sorted(self.ref_dir.glob("*.npz")):
            clip = load_reference_clip(npz_path)
            if source_filter == "synthetic" and clip.source_type != "SYNTHETIC":
                continue
            if source_filter == "real" and clip.source_type != "REAL_VIDEO":
                continue
            if behaviours is not None and clip.behaviour_label not in behaviours:
                continue
            self.clips.append(clip)

    def __len__(self) -> int:
        return len(self.clips)

    @property
    def source_counts(self) -> dict[str, int]:
        counts = {"REAL_VIDEO": 0, "SYNTHETIC": 0}
        for c in self.clips:
            counts[c.source_type] += 1
        return counts

    def select_for_command(
        self,
        vx_cmd: float,
        yaw_cmd: float,
        rng: np.random.Generator | None = None,
    ) -> ReferenceClip | None:
        """Select the closest matching reference clip for a target (vx, yaw_rate) command."""
        if not self.clips:
            return None
        scores = []
        for c in self.clips:
            dv = abs(c.mean_speed_m_s - abs(vx_cmd))
            dy = 0.25 * abs(c.mean_yaw_rate_rad_s - yaw_cmd)
            scores.append(dv + dy)
        best_idx = int(np.argmin(scores))
        if rng is not None and len(self.clips) > 1 and rng.random() < 0.15:
            best_idx = int(rng.integers(0, len(self.clips)))
        return self.clips[best_idx]
