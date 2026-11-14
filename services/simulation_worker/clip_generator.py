"""
Deterministic simulation-worker job that rolls out a bounded episode using the
learned hamster locomotion policy (or explicit scripted fallback) and produces a
`TrajectoryClipV1` ready for object storage upload and browser replay.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

from contracts.schemas import (
    BehaviourType,
    EventOrigin,
    TrajectoryClipV1,
    TrajectoryKeyframeV1,
)
from training.locomotion.policy import MLPActorCritic
from training.locomotion.quadruped_env import VectorizedLeggedEnv

DEFAULT_HAMSTER_CKPT = Path(__file__).resolve().parents[2] / "training" / "experiments" / "p4_2_hamster" / "policy.npz"


def _euler_to_quat(roll: float, pitch: float, yaw: float) -> list[float]:
    cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return [round(x, 6), round(y, 6), round(z, 6), round(w, 6)]


def make_deterministic_clip_id(pet_id: str, skill_id: str, start_sim_time_sec: float, seed: int) -> str:
    raw = f"{pet_id}:{skill_id}:{start_sim_time_sec:.3f}:{seed}".encode("utf-8")
    return "clip_" + hashlib.sha256(raw).hexdigest()[:16]


def generate_episode_clip(
    pet_id: str,
    skill_id: str,
    seed: int,
    start_sim_time_sec: float = 0.0,
    duration_sec: float = 4.0,
    fps: float = 20.0,
    initial_pos: Optional[Tuple[float, float, float]] = None,
    initial_yaw: float = 0.0,
    checkpoint_path: Path = DEFAULT_HAMSTER_CKPT,
) -> TrajectoryClipV1:
    """
    Generate a deterministic, fixed-rate `TrajectoryClipV1` from `seed` and `start_sim_time_sec`.
    """
    env = VectorizedLeggedEnv(
        num_envs=1,
        morphology="hamster",
        episode_length=max(500, int(duration_sec / 0.02) + 10),
        dt=0.02,
        seed=seed,
        domain_randomization=False,
    )
    env.curriculum.stage_idx = 2
    obs = env.reset(seed=seed)

    if initial_pos is not None:
        env.pos[0, 0] = initial_pos[0]
        env.pos[0, 1] = initial_pos[1]
        env.pos[0, 2] = initial_pos[2]
    env.rpy[0, 2] = initial_yaw

    # Skill-conditioned velocity command
    skill_cmds = {
        "explore_area": [0.22, 0.0, 0.35],
        "approach_food": [0.24, 0.0, -0.15],
        "rest": [0.0, 0.0, 0.0],
        "hide": [0.18, 0.0, 0.25],
    }
    cmd = skill_cmds.get(skill_id, [0.20, 0.0, 0.15])
    env.commands[0] = np.array(cmd, dtype=np.float32)

    policy: Optional[MLPActorCritic] = None
    behaviour_type = BehaviourType.SCRIPTED
    if checkpoint_path.exists():
        policy, _ = MLPActorCritic.load(checkpoint_path)
        behaviour_type = BehaviourType.LEARNED

    total_frames = max(2, int(round(duration_sec * fps)))
    sim_steps_per_frame = max(1, int(round((1.0 / fps) / env.dt)))
    keyframes: list[TrajectoryKeyframeV1] = []

    for frame_idx in range(total_frames):
        t_rel = round(frame_idx / fps, 4)
        p = env.pos[0]
        r = env.rpy[0]
        # Map MuJoCo (x, y, z_up) -> Three.js (x, y_up, z)
        kf = TrajectoryKeyframeV1(
            t_sec=t_rel,
            root_pos=[round(float(p[0]), 5), round(float(p[2]), 5), round(float(-p[1]), 5)],
            root_quat=_euler_to_quat(float(r[0]), float(r[2]), float(r[1])),
            joint_angles=[round(float(v), 5) for v in env.q[0].tolist()],
            foot_contacts=[bool(c > 0.5) for c in env.foot_contacts[0].tolist()],
        )
        keyframes.append(kf)

        for _ in range(sim_steps_per_frame):
            if policy is not None:
                act = policy.forward_deterministic(obs)
            else:
                act = np.zeros((1, env.action_dim), dtype=np.float32)
            obs, _, _, _ = env.step(act)
            env.commands[0] = np.array(cmd, dtype=np.float32)

    clip_id = make_deterministic_clip_id(pet_id, skill_id, start_sim_time_sec, seed)
    return TrajectoryClipV1(
        clip_id=clip_id,
        pet_id=pet_id,
        skill_id=skill_id,
        seed=seed,
        origin=EventOrigin.OBSERVED_PHYSICS,
        behaviour_type=behaviour_type,
        fps=fps,
        start_sim_time_sec=start_sim_time_sec,
        end_sim_time_sec=round(start_sim_time_sec + duration_sec, 4),
        keyframes=keyframes,
    )

