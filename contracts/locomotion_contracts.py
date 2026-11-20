"""Versioned observation, action, and reference-motion contracts for HAMSTER locomotion.

Follows HAMSTER_Technical_Blueprint.md Section 15.1 (Shared observation and action contracts)
and adopts the fixed-dimension zero-padded contract pattern from pollen-robotics/microduck_rl.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Sequence

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator

MODEL_VERSION = "hamster_mjcf_v1.0.0"
OBS_CONTRACT_VERSION = "locomotion_obs_v1.0.0"
ACTION_CONTRACT_VERSION = "locomotion_act_v1.0.0"
REF_CLIP_SCHEMA_VERSION = "reference_clip_v1.0.0"

ACTUATED_JOINT_NAMES: tuple[str, ...] = (
    "spine_pitch",
    "spine_yaw",
    "neck_pitch",
    "neck_yaw",
    "fl_hip_abd",
    "fl_hip_pitch",
    "fl_knee_pitch",
    "fr_hip_abd",
    "fr_hip_pitch",
    "fr_knee_pitch",
    "bl_hip_abd",
    "bl_hip_pitch",
    "bl_knee_pitch",
    "br_hip_abd",
    "br_hip_pitch",
    "br_knee_pitch",
)

NUM_ACTUATED_JOINTS = len(ACTUATED_JOINT_NAMES)  # 16

JOINT_LIMITS_LOW = np.array(
    [
        -0.45, -0.45, -0.50, -0.60,
        -0.40, -0.85, -1.10,
        -0.40, -0.85, -1.10,
        -0.40, -0.85, -1.10,
        -0.40, -0.85, -1.10,
    ],
    dtype=np.float32,
)

JOINT_LIMITS_HIGH = np.array(
    [
        0.45, 0.45, 0.50, 0.60,
        0.40, 0.85, 0.60,
        0.40, 0.85, 0.60,
        0.40, 0.85, 0.60,
        0.40, 0.85, 0.60,
    ],
    dtype=np.float32,
)

DEFAULT_STAND_JOINTS = np.array(
    [
        0.0, 0.0, -0.05, 0.0,
        0.0, 0.25, -0.50,
        0.0, 0.25, -0.50,
        0.0, 0.28, -0.55,
        0.0, 0.28, -0.55,
    ],
    dtype=np.float32,
)

# Fixed 64-dim observation vector layout:
# [joint_pos(16), joint_vel(16), body_quat(4), body_ang_vel(3),
#  foot_contacts(4), command(3), prev_action(16), ref_phase(2)]
OBS_DIM = 16 + 16 + 4 + 3 + 4 + 3 + 16 + 2  # 64
ACTION_DIM = NUM_ACTUATED_JOINTS  # 16

# Phase C v2 Multi-Skill AMP Motor Contract (72 dims: v1 64-dim core + 8-dim posture/mode cmd)
OBS_V2_CONTRACT_VERSION = "locomotion_obs_v2.0.0"
MOTOR_MODES_V2: tuple[str, ...] = (
    "locomote",
    "rear_periscope",
    "crouch_tunnel",
    "wheel_run",
    "rest_settle",
)
OBS_V2_DIM = OBS_DIM + 3 + len(MOTOR_MODES_V2)  # 64 + 3 (target_z, target_pitch, head_yaw) + 5 = 72


def _check_finite_list(values: Sequence[float], expected_len: int, name: str) -> list[float]:
    arr = [float(v) for v in values]
    if len(arr) != expected_len:
        raise ValueError(f"{name} must have length {expected_len}, got {len(arr)}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite values")
    return arr


class LocomotionObservationV1(BaseModel):
    """Versioned locomotion observation contract (64-dim flat vector)."""

    schema_version: Literal["locomotion_obs_v1.0.0"] = OBS_CONTRACT_VERSION
    model_version: str = MODEL_VERSION
    joint_pos: list[float] = Field(..., description="16 actuated joint positions (rad)")
    joint_vel: list[float] = Field(..., description="16 actuated joint velocities (rad/s)")
    body_quat: list[float] = Field(..., description="Pelvis orientation quaternion [w, x, y, z]")
    body_ang_vel: list[float] = Field(..., description="Pelvis angular velocity [wx, wy, wz] (rad/s)")
    foot_contacts: list[float] = Field(..., description="Normalized paw contacts [fl, fr, bl, br] in [0, 1]")
    command: list[float] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0],
        description="Commanded [vx_m_s, vy_m_s, yaw_rate_rad_s] (zero-padded when unused)",
    )
    prev_action: list[float] = Field(
        default_factory=lambda: DEFAULT_STAND_JOINTS.tolist(),
        description="Previous 16-dim joint target action (rad)",
    )
    ref_phase: list[float] = Field(
        default_factory=lambda: [0.0, 0.0],
        description="Reference gait phase [sin(2pi*phi), cos(2pi*phi)] (zero-padded if none)",
    )

    @field_validator("joint_pos")
    @classmethod
    def _v_qpos(cls, v: list[float]) -> list[float]:
        return _check_finite_list(v, NUM_ACTUATED_JOINTS, "joint_pos")

    @field_validator("joint_vel")
    @classmethod
    def _v_qvel(cls, v: list[float]) -> list[float]:
        return _check_finite_list(v, NUM_ACTUATED_JOINTS, "joint_vel")

    @field_validator("body_quat")
    @classmethod
    def _v_quat(cls, v: list[float]) -> list[float]:
        q = _check_finite_list(v, 4, "body_quat")
        norm = float(np.linalg.norm(q))
        if not (0.5 <= norm <= 1.5):
            raise ValueError(f"body_quat norm {norm:.4f} is invalid")
        return q

    @field_validator("body_ang_vel")
    @classmethod
    def _v_ang_vel(cls, v: list[float]) -> list[float]:
        return _check_finite_list(v, 3, "body_ang_vel")

    @field_validator("foot_contacts")
    @classmethod
    def _v_contacts(cls, v: list[float]) -> list[float]:
        c = _check_finite_list(v, 4, "foot_contacts")
        if any(x < 0.0 or x > 1.0 for x in c):
            raise ValueError("foot_contacts must lie in [0.0, 1.0]")
        return c

    @field_validator("command")
    @classmethod
    def _v_cmd(cls, v: list[float]) -> list[float]:
        return _check_finite_list(v, 3, "command")

    @field_validator("prev_action")
    @classmethod
    def _v_prev(cls, v: list[float]) -> list[float]:
        return _check_finite_list(v, NUM_ACTUATED_JOINTS, "prev_action")

    @field_validator("ref_phase")
    @classmethod
    def _v_phase(cls, v: list[float]) -> list[float]:
        return _check_finite_list(v, 2, "ref_phase")

    def to_vector(self) -> np.ndarray:
        vec = np.concatenate(
            [
                np.asarray(self.joint_pos, dtype=np.float32),
                np.asarray(self.joint_vel, dtype=np.float32),
                np.asarray(self.body_quat, dtype=np.float32),
                np.asarray(self.body_ang_vel, dtype=np.float32),
                np.asarray(self.foot_contacts, dtype=np.float32),
                np.asarray(self.command, dtype=np.float32),
                np.asarray(self.prev_action, dtype=np.float32),
                np.asarray(self.ref_phase, dtype=np.float32),
            ]
        )
        assert vec.shape == (OBS_DIM,)
        return vec

    @classmethod
    def from_vector(
        cls,
        vec: np.ndarray,
        model_version: str = MODEL_VERSION,
    ) -> "LocomotionObservationV1":
        arr = np.asarray(vec, dtype=np.float32).reshape(-1)
        if arr.shape != (OBS_DIM,):
            raise ValueError(f"Expected obs vector of shape ({OBS_DIM},), got {arr.shape}")
        return cls(
            model_version=model_version,
            joint_pos=arr[0:16].tolist(),
            joint_vel=arr[16:32].tolist(),
            body_quat=arr[32:36].tolist(),
            body_ang_vel=arr[36:39].tolist(),
            foot_contacts=arr[39:43].tolist(),
            command=arr[43:46].tolist(),
            prev_action=arr[46:62].tolist(),
            ref_phase=arr[62:64].tolist(),
        )


class LocomotionActionV1(BaseModel):
    """Versioned locomotion action contract (16-dim joint position targets)."""

    schema_version: Literal["locomotion_act_v1.0.0"] = ACTION_CONTRACT_VERSION
    model_version: str = MODEL_VERSION
    control_mode: Literal["position"] = "position"
    joint_targets: list[float] = Field(..., description="16 actuated joint position targets (rad)")

    @field_validator("joint_targets")
    @classmethod
    def _v_targets(cls, v: list[float]) -> list[float]:
        return _check_finite_list(v, NUM_ACTUATED_JOINTS, "joint_targets")

    @model_validator(mode="after")
    def _check_within_limits(self) -> "LocomotionActionV1":
        arr = np.asarray(self.joint_targets, dtype=np.float32)
        eps = 1e-5
        if np.any(arr < JOINT_LIMITS_LOW - eps) or np.any(arr > JOINT_LIMITS_HIGH + eps):
            raise ValueError("joint_targets exceed MJCF joint limits; clamp via clamp_joint_targets() first")
        return self

    def to_vector(self) -> np.ndarray:
        return np.asarray(self.joint_targets, dtype=np.float32)


def clamp_joint_targets(targets: np.ndarray) -> np.ndarray:
    """Safety clamp mapping arbitrary float vectors into valid MJCF joint limits."""
    arr = np.asarray(targets, dtype=np.float32)
    if arr.shape != (NUM_ACTUATED_JOINTS,):
        raise ValueError(f"Expected action shape ({NUM_ACTUATED_JOINTS},), got {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("Action contains non-finite values")
    return np.clip(arr, JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH)


def validate_contract_compatibility(
    checkpoint_meta: dict[str, str],
    expected_model_version: str = MODEL_VERSION,
    expected_obs_version: str = OBS_CONTRACT_VERSION,
    expected_act_version: str = ACTION_CONTRACT_VERSION,
) -> None:
    """Raise ValueError if a policy checkpoint does not match morphology/contract versions."""
    checks = [
        ("model_version", expected_model_version),
        ("obs_schema_version", expected_obs_version),
        ("act_schema_version", expected_act_version),
    ]
    for key, expected in checks:
        actual = checkpoint_meta.get(key)
        if actual != expected:
            raise ValueError(f"Contract mismatch for {key}: checkpoint={actual!r}, expected={expected!r}")


def export_locomotion_json_schemas(out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    obs_path = out_dir / "locomotion_obs_v1.schema.json"
    act_path = out_dir / "locomotion_act_v1.schema.json"
    obs_path.write_text(json.dumps(LocomotionObservationV1.model_json_schema(), indent=2), encoding="utf-8")
    act_path.write_text(json.dumps(LocomotionActionV1.model_json_schema(), indent=2), encoding="utf-8")
    return obs_path, act_path
