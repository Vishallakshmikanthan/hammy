"""
Vectorized 12-DOF (quadruped stand-in) and 14-DOF (hamster_v1) locomotion environment.
- Observation: joint_pos, joint_vel, body_orientation (roll, pitch, yaw_rate_proxy/tilt),
  angular_velocity (3), previous_action, command [vx, vy, yaw_rate].
- Action: joint position targets with symmetric joint limits.
- Supports both native MuJoCo (when OS permits) and vectorized NumPy articulated PD dynamics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import numpy as np

from training.locomotion.contracts import (
    LocomotionContractSpec,
    spec_for_hamster,
    spec_for_quadruped,
)
from training.locomotion.curriculum import CurriculumState
from training.locomotion.domain_randomization import (
    DomainRandomizationRanges,
    RandomizedEnvParams,
    sample_domain_randomization,
)
from training.locomotion.rewards import RewardWeights, compute_locomotion_rewards

QUADRUPED_XML_PATH = Path(__file__).resolve().parents[2] / "simulation" / "models" / "quadruped_standin" / "quadruped.xml"
HAMSTER_XML_PATH = Path(__file__).resolve().parents[2] / "simulation" / "models" / "hamster_v1" / "hamster.xml"


class VectorizedLeggedEnv:
    """
    Fast vectorized legged locomotion environment for stand/walk/turn/stop training.
    Supports `morphology="quadruped"` (12 joints, 45-dim obs) and
    `morphology="hamster"` (14 joints: 2 spine + 12 legs, 51-dim obs).
    """

    def __init__(
        self,
        num_envs: int = 256,
        morphology: str = "quadruped",
        episode_length: int = 250,
        dt: float = 0.02,
        seed: int = 42,
        domain_randomization: bool = True,
        dr_ranges: DomainRandomizationRanges = DomainRandomizationRanges(),
        reward_weights: RewardWeights = RewardWeights(),
    ) -> None:
        self.num_envs = num_envs
        self.morphology = morphology
        self.episode_length = episode_length
        self.dt = dt
        self.rng = np.random.default_rng(seed)
        self.domain_randomization = domain_randomization
        self.dr_ranges = dr_ranges
        self.reward_weights = reward_weights

        if morphology == "hamster":
            self.spec: LocomotionContractSpec = spec_for_hamster()
            self.nominal_height = 0.055
            self.fall_height = 0.022
            self.max_speed = 0.45
            self.joint_limit = 0.85
            self.kp = 6.5
            self.kd = 0.45
        else:
            self.spec = spec_for_quadruped()
            self.nominal_height = 0.14
            self.fall_height = 0.06
            self.max_speed = 0.55
            self.joint_limit = 0.80
            self.kp = 8.0
            self.kd = 0.50

        self.num_joints = self.spec.num_joints
        self.obs_dim = self.spec.obs_dim
        self.action_dim = self.spec.action_dim

        self.curriculum = CurriculumState()
        self.dr_params: RandomizedEnvParams = sample_domain_randomization(
            num_envs, self.rng, self.dr_ranges, enabled=domain_randomization
        )

        # State buffers [N, ...]
        self.q = np.zeros((num_envs, self.num_joints), dtype=np.float32)
        self.qd = np.zeros((num_envs, self.num_joints), dtype=np.float32)
        self.pos = np.zeros((num_envs, 3), dtype=np.float32)
        self.lin_vel = np.zeros((num_envs, 3), dtype=np.float32)
        self.rpy = np.zeros((num_envs, 3), dtype=np.float32)
        self.ang_vel = np.zeros((num_envs, 3), dtype=np.float32)
        self.prev_action = np.zeros((num_envs, self.action_dim), dtype=np.float32)
        self.action_history = np.zeros((num_envs, 3, self.action_dim), dtype=np.float32)
        self.commands = np.zeros((num_envs, 3), dtype=np.float32)
        self.perturbation_scale = 0.0
        self.steps = np.zeros(num_envs, dtype=np.int32)
        self.gait_phase = np.zeros(num_envs, dtype=np.float32)
        self.foot_contacts = np.ones((num_envs, 4), dtype=np.float32)

    def reset(self, seed: Optional[int] = None) -> np.ndarray:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.dr_params = sample_domain_randomization(
            self.num_envs, self.rng, self.dr_ranges, enabled=self.domain_randomization
        )
        self.q.fill(0.0)
        self.qd.fill(0.0)
        self.pos[:, :2] = 0.0
        self.pos[:, 2] = self.nominal_height
        self.lin_vel.fill(0.0)
        self.rpy[:, :2] = self.rng.uniform(-0.04, 0.04, size=(self.num_envs, 2))
        self.rpy[:, 2] = 0.0
        self.ang_vel.fill(0.0)
        self.prev_action.fill(0.0)
        self.action_history.fill(0.0)
        self.steps.fill(0)
        self.gait_phase = self.rng.uniform(0, 2 * np.pi, size=self.num_envs).astype(np.float32)
        self.foot_contacts.fill(1.0)
        self.commands, self.perturbation_scale = self.curriculum.sample_commands(self.num_envs, self.rng)
        return self._get_obs()

    def _get_obs(self) -> np.ndarray:
        if self.domain_randomization:
            q_obs = self.q + self.rng.normal(0, self.dr_ranges.pos_noise_std, size=self.q.shape).astype(np.float32)
            qd_obs = self.qd + self.rng.normal(0, self.dr_ranges.vel_noise_std, size=self.qd.shape).astype(np.float32)
            rpy_obs = self.rpy + self.rng.normal(0, self.dr_ranges.imu_noise_std, size=self.rpy.shape).astype(np.float32)
            ang_obs = self.ang_vel + self.rng.normal(0, self.dr_ranges.imu_noise_std, size=self.ang_vel.shape).astype(np.float32)
        else:
            q_obs, qd_obs, rpy_obs, ang_obs = self.q, self.qd, self.rpy, self.ang_vel

        return np.concatenate(
            [q_obs, qd_obs, rpy_obs, ang_obs, self.prev_action, self.commands],
            axis=-1,
        ).astype(np.float32)

    def step(self, action: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
        action = np.clip(np.asarray(action, dtype=np.float32), -self.joint_limit, self.joint_limit)

        # Action latency buffer
        self.action_history = np.roll(self.action_history, shift=1, axis=1)
        self.action_history[:, 0, :] = action
        idx = np.arange(self.num_envs)
        delayed_action = self.action_history[idx, self.dr_params.latency_steps, :]

        # Joint PD control -> torques & joint integration
        torques = self.dr_params.actuator_strength[:, None] * (
            self.kp * (delayed_action - self.q) - self.kd * self.qd
        )
        torques = np.clip(torques, -2.5, 2.5)
        qdd = torques / np.maximum(0.05 * self.dr_params.mass_scale[:, None], 0.02)
        self.qd = np.clip(self.qd + qdd * self.dt, -12.0, 12.0)
        self.q = np.clip(self.q + self.qd * self.dt, -self.joint_limit, self.joint_limit)

        # Map leg joint velocities/targets to planar propulsion + balance dynamics
        # Leg joints occupy the last 12 indices (for hamster: indices 2..14; for quadruped: 0..12)
        leg_start = self.num_joints - 12
        hip_pitch = self.q[:, leg_start + 1 :: 3]   # [N, 4] FL, FR, BL, BR
        knee = self.q[:, leg_start + 2 :: 3]        # [N, 4]
        hip_vel = self.qd[:, leg_start + 1 :: 3]    # [N, 4]
        abd = self.q[:, leg_start :: 3]             # [N, 4]

        # Foot contacts modulated by knee extension and gait phase
        self.gait_phase = (self.gait_phase + self.dt * 12.0) % (2 * np.pi)
        stance_score = 0.35 - knee + 0.15 * np.sin(self.gait_phase[:, None] + np.array([0, np.pi, np.pi, 0]))
        self.foot_contacts = (stance_score > 0.0).astype(np.float32)
        num_contacts = np.sum(self.foot_contacts, axis=-1)

        # Forward/lateral acceleration from stance leg push-off and friction
        push_x = np.mean(self.foot_contacts * (-hip_vel * 0.18 + hip_pitch * 0.45), axis=-1)
        push_y = np.mean(self.foot_contacts * (abd * 0.35), axis=-1)
        yaw_torque = (
            (hip_pitch[:, 0] + hip_pitch[:, 2]) - (hip_pitch[:, 1] + hip_pitch[:, 3])
        ) * 1.4

        grip = self.dr_params.friction * np.clip(num_contacts / 4.0, 0.1, 1.0)
        mass = self.dr_params.mass_scale

        # Optional random push perturbation in perturbation_recovery / later stages
        perturb = np.zeros((self.num_envs, 2), dtype=np.float32)
        if self.perturbation_scale > 0.0:
            push_mask = (self.steps % 60 == 30)
            perturb[push_mask] = self.rng.normal(0, 0.18 * self.perturbation_scale, size=(int(np.sum(push_mask)), 2))

        ax = (grip * push_x * 6.0 - 2.2 * self.lin_vel[:, 0]) / mass + perturb[:, 0]
        ay = (grip * push_y * 4.5 - 2.4 * self.lin_vel[:, 1]) / mass + perturb[:, 1]
        self.lin_vel[:, 0] = np.clip(self.lin_vel[:, 0] + ax * self.dt, -1.2, 1.2)
        self.lin_vel[:, 1] = np.clip(self.lin_vel[:, 1] + ay * self.dt, -0.8, 0.8)

        # Roll / pitch balance & height
        roll_restore = -6.0 * self.rpy[:, 0] - 1.5 * self.ang_vel[:, 0] + np.mean(abd, axis=-1) * 0.8 + perturb[:, 1] * 1.5
        pitch_restore = -6.0 * self.rpy[:, 1] - 1.5 * self.ang_vel[:, 1] + (hip_pitch[:, 0] - hip_pitch[:, 2]) * 0.6 + perturb[:, 0] * 1.5
        yaw_acc = yaw_torque - 2.0 * self.ang_vel[:, 2]

        self.ang_vel[:, 0] += roll_restore * self.dt
        self.ang_vel[:, 1] += pitch_restore * self.dt
        self.ang_vel[:, 2] += yaw_acc * self.dt
        self.rpy += self.ang_vel * self.dt

        # Height drops if < 2 feet in contact or large tilt
        tilt_mag = np.hypot(self.rpy[:, 0], self.rpy[:, 1])
        target_z = self.nominal_height * np.clip(1.0 - 0.35 * tilt_mag, 0.2, 1.1) * np.where(num_contacts >= 2, 1.0, 0.72)
        self.pos[:, 2] += (target_z - self.pos[:, 2]) * 0.25
        self.pos[:, 0] += self.lin_vel[:, 0] * self.dt
        self.pos[:, 1] += self.lin_vel[:, 1] * self.dt

        fallen = (tilt_mag > 0.65) | (self.pos[:, 2] < self.fall_height)
        self.steps += 1
        timeout = self.steps >= self.episode_length
        dones = fallen | timeout

        foot_xy_speeds = np.abs(hip_vel) * 0.08
        rewards, reward_terms = compute_locomotion_rewards(
            lin_vel_xy=self.lin_vel[:, :2],
            yaw_rate=self.ang_vel[:, 2],
            cmd_vel_xy_yaw=self.commands,
            roll_pitch=self.rpy[:, :2],
            torques=torques,
            action=action,
            prev_action=self.prev_action,
            foot_contacts=self.foot_contacts,
            foot_xy_speeds=foot_xy_speeds,
            fallen=fallen,
            weights=self.reward_weights,
        )

        self.prev_action = action.copy()

        # Auto-reset finished environments
        if np.any(dones):
            done_idx = np.where(dones)[0]
            self.q[done_idx] = 0.0
            self.qd[done_idx] = 0.0
            self.pos[done_idx, :2] = 0.0
            self.pos[done_idx, 2] = self.nominal_height
            self.lin_vel[done_idx] = 0.0
            self.rpy[done_idx, :2] = self.rng.uniform(-0.04, 0.04, size=(len(done_idx), 2))
            self.rpy[done_idx, 2] = 0.0
            self.ang_vel[done_idx] = 0.0
            self.prev_action[done_idx] = 0.0
            self.action_history[done_idx] = 0.0
            self.steps[done_idx] = 0

        info = {
            "reward_terms": reward_terms,
            "fallen": fallen,
            "timeout": timeout,
            "lin_vel_xy": self.lin_vel[:, :2].copy(),
            "yaw_rate": self.ang_vel[:, 2].copy(),
            "commands": self.commands.copy(),
            "foot_contacts": self.foot_contacts.copy(),
        }
        return self._get_obs(), rewards, dones, info

