"""Stage 3 Gymnasium environment for HAMSTER 16-DoF MuJoCo locomotion with imitation RL.

Uses versioned contracts (`contracts/locomotion_contracts.py`), source-agnostic
`ReferenceMotionLibrary` (`training/reference_library.py`), success-gated curriculum,
plausible domain randomization, and per-term reward logging.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gymnasium as gym
import mujoco
import numpy as np
from gymnasium import spaces

from contracts.locomotion_contracts import (
    ACTION_DIM,
    ACTUATED_JOINT_NAMES,
    DEFAULT_STAND_JOINTS,
    JOINT_LIMITS_HIGH,
    JOINT_LIMITS_LOW,
    MODEL_VERSION,
    NUM_ACTUATED_JOINTS,
    OBS_DIM,
    clamp_joint_targets,
)
from training.reference_library import ReferenceClip, ReferenceMotionLibrary, SourceFilter

MODEL_PATH = Path("simulation/models/hamster/hamster.xml")

CURRICULUM_STAGES = (
    "stand",
    "perturb",
    "walk",
    "turn",
    "stop",
    "target",
)


@dataclass
class RewardWeights:
    imitation_joint: float = 1.80
    imitation_vel: float = 0.90
    imitation_contact: float = 0.55
    upright: float = 0.35
    command: float = 3.40
    smoothness: float = 0.28
    energy: float = 0.015
    fall_penalty: float = 3.0


class HamsterLocomotionEnv(gym.Env):
    """50 Hz MuJoCo Gymnasium environment for Syrian hamster locomotion."""

    metadata = {"render_modes": ["rgb_array"], "render_fps": 50}

    def __init__(
        self,
        model_path: str | Path = MODEL_PATH,
        ref_dir: str | Path = "data/reference_motion",
        source_filter: SourceFilter = "mixed",
        use_imitation: bool = True,
        curriculum_stage: int = 2,
        auto_curriculum: bool = False,
        domain_randomization: bool = True,
        episode_length_s: float = 6.0,
        render_mode: str | None = None,
        reward_weights: RewardWeights | None = None,
    ) -> None:
        super().__init__()
        self.model_path = Path(model_path)
        self.model = mujoco.MjModel.from_xml_path(str(self.model_path))
        self.data = mujoco.MjData(self.model)
        self.stand_key_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_KEY, "stand")

        # Cache original physics parameters for domain randomization resets
        self._base_body_mass = self.model.body_mass.copy()
        self._base_geom_friction = self.model.geom_friction.copy()
        self._base_gainprm = self.model.actuator_gainprm.copy()

        # Cache joint & sensor addresses
        self._jnt_qposadr = np.array(
            [self.model.jnt_qposadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, jn)] for jn in ACTUATED_JOINT_NAMES],
            dtype=int,
        )
        self._jnt_qveladr = np.array(
            [self.model.jnt_dofadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, jn)] for jn in ACTUATED_JOINT_NAMES],
            dtype=int,
        )
        self._quat_adr = self.model.sensor_adr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SENSOR, "pelvis_quat")]
        self._gyro_adr = self.model.sensor_adr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SENSOR, "pelvis_gyro")]
        self._linvel_adr = self.model.sensor_adr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SENSOR, "pelvis_linvel")]
        self._touch_adrs = np.array(
            [self.model.sensor_adr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SENSOR, n)] for n in ("fl_touch", "fr_touch", "bl_touch", "br_touch")],
            dtype=int,
        )

        self.control_dt = 0.02  # 50 Hz
        self.n_substeps = int(round(self.control_dt / self.model.opt.timestep))  # 10
        self.max_steps = int(round(episode_length_s / self.control_dt))

        self.use_imitation = use_imitation
        self.source_filter = source_filter
        self.ref_lib = ReferenceMotionLibrary(ref_dir, source_filter=source_filter) if use_imitation else None
        self.active_clip: ReferenceClip | None = None

        self.curriculum_stage = int(np.clip(curriculum_stage, 0, len(CURRICULUM_STAGES) - 1))
        self.auto_curriculum = auto_curriculum
        self._success_window: deque[float] = deque(maxlen=12)

        self.domain_randomization = domain_randomization
        self.weights = reward_weights or RewardWeights()
        self.render_mode = render_mode
        self._renderer: mujoco.Renderer | None = None

        # Action space: normalized [-1, 1]^16 residual around DEFAULT_STAND_JOINTS
        self._action_scale = 0.45 * (JOINT_LIMITS_HIGH - JOINT_LIMITS_LOW)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(ACTION_DIM,), dtype=np.float32)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(OBS_DIM,), dtype=np.float32)

        # Episode state
        self._step_count = 0
        self._sim_time = 0.0
        self._command = np.zeros(3, dtype=np.float32)  # [vx, vy, yaw_rate]
        self._fixed_command: np.ndarray | None = None
        self._target_xy = np.array([0.6, 0.0], dtype=np.float32)
        self._prev_action = DEFAULT_STAND_JOINTS.copy()
        self._prev_prev_action = DEFAULT_STAND_JOINTS.copy()
        self._prev_contacts_bin = np.ones(4, dtype=np.float32)
        self._contact_age_s = np.full(4, 0.5, dtype=np.float32)
        self._action_delay_steps = 0
        self._action_queue: deque[np.ndarray] = deque(maxlen=3)
        self._next_push_step = 75
        self._obs_noise_scale = 1.0 if domain_randomization else 0.0

    def set_fixed_command(self, vx: float, vy: float = 0.0, yaw_rate: float = 0.0) -> None:
        """Override command sampling for deterministic evaluation / rendering."""
        self._fixed_command = np.array([vx, vy, yaw_rate], dtype=np.float32)

    def clear_fixed_command(self) -> None:
        self._fixed_command = None

    def set_curriculum_stage(self, stage: int) -> None:
        self.curriculum_stage = int(np.clip(stage, 0, len(CURRICULUM_STAGES) - 1))

    def _apply_domain_randomization(self) -> None:
        if not self.domain_randomization:
            self.model.body_mass[:] = self._base_body_mass
            self.model.geom_friction[:] = self._base_geom_friction
            self.model.actuator_gainprm[:] = self._base_gainprm
            self._action_delay_steps = 0
            return

        rng = self.np_random
        mass_scale = float(rng.uniform(0.88, 1.12))
        fric_scale = float(rng.uniform(0.75, 1.25))
        kp_scale = float(rng.uniform(0.85, 1.15))

        self.model.body_mass[:] = self._base_body_mass * mass_scale
        self.model.geom_friction[:] = self._base_geom_friction * fric_scale
        self.model.actuator_gainprm[:] = self._base_gainprm * kp_scale
        self._action_delay_steps = int(rng.integers(0, 2))  # 0 or 1 control step (0-20 ms)

    def _sample_command(self) -> None:
        if self._fixed_command is not None:
            self._command = self._fixed_command.copy()
            return

        rng = self.np_random
        stage_name = CURRICULUM_STAGES[self.curriculum_stage]
        if stage_name in ("stand", "perturb"):
            self._command[:] = [0.0, 0.0, 0.0]
        elif stage_name == "walk":
            vx = float(rng.uniform(0.08, 0.22))
            self._command[:] = [vx, 0.0, 0.0]
        elif stage_name == "turn":
            vx = float(rng.uniform(0.08, 0.20))
            yaw = float(rng.uniform(-0.85, 0.85))
            self._command[:] = [vx, 0.0, yaw]
        elif stage_name == "stop":
            # Episode starts walking; mid-episode switches to stop then resumes
            self._command[:] = [float(rng.uniform(0.10, 0.18)), 0.0, 0.0]
        else:  # target
            angle = float(rng.uniform(-1.0, 1.0))
            dist = float(rng.uniform(0.35, 0.75))
            self._target_xy = np.array([dist * np.cos(angle), dist * np.sin(angle)], dtype=np.float32)
            self._update_target_command()

    def _update_target_command(self) -> None:
        pos = self.data.qpos[0:2]
        w, x, y, z = self.data.qpos[3:7]
        yaw = float(np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))
        diff = self._target_xy - pos
        dist = float(np.linalg.norm(diff))
        if dist < 0.05:
            self._command[:] = [0.0, 0.0, 0.0]
            return
        des_yaw = float(np.arctan2(diff[1], diff[0]))
        yaw_err = float(np.arctan2(np.sin(des_yaw - yaw), np.cos(des_yaw - yaw)))
        vx = float(np.clip(0.35 * dist * max(0.2, np.cos(yaw_err)), 0.0, 0.20))
        yaw_cmd = float(np.clip(1.6 * yaw_err, -0.9, 0.9))
        self._command[:] = [vx, 0.0, yaw_cmd]

    def _get_ref_state(self) -> dict[str, np.ndarray] | None:
        if not self.use_imitation or self.active_clip is None:
            return None
        return self.active_clip.sample_at_time(self._sim_time)

    def _get_obs(self, ref_state: dict[str, np.ndarray] | None) -> np.ndarray:
        qpos = self.data.qpos[self._jnt_qposadr].astype(np.float32)
        qvel = self.data.qvel[self._jnt_qveladr].astype(np.float32)
        quat_raw = self.data.sensordata[self._quat_adr : self._quat_adr + 4].astype(np.float32)
        qnorm = float(np.linalg.norm(quat_raw))
        quat_raw = quat_raw / qnorm if qnorm > 1e-6 else np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        # Yaw-invariant tilt quaternion so policy generalizes natively to any heading in the habitat
        w, x, y, z = [float(v) for v in quat_raw]
        yaw = float(np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))
        cy, sy = float(np.cos(-yaw / 2.0)), float(np.sin(-yaw / 2.0))
        quat = np.array(
            [cy * w - sy * z, cy * x - sy * y, cy * y + sy * x, cy * z + sy * w],
            dtype=np.float32,
        )
        if quat[0] < 0.0:
            quat = -quat
        gyro = self.data.sensordata[self._gyro_adr : self._gyro_adr + 3].astype(np.float32)
        raw_touch = self.data.sensordata[self._touch_adrs].astype(np.float32)
        contacts = np.clip(raw_touch / 0.20, 0.0, 1.0)

        if self._obs_noise_scale > 0.0:
            rng = self.np_random
            qpos = qpos + rng.normal(0.0, 0.01 * self._obs_noise_scale, size=qpos.shape).astype(np.float32)
            qvel = qvel + rng.normal(0.0, 0.05 * self._obs_noise_scale, size=qvel.shape).astype(np.float32)
            gyro = gyro + rng.normal(0.0, 0.02 * self._obs_noise_scale, size=gyro.shape).astype(np.float32)

        ref_phase = ref_state["ref_phase"] if ref_state is not None else np.zeros(2, dtype=np.float32)

        obs = np.concatenate(
            [qpos, qvel, quat, gyro, contacts, self._command, self._prev_action, ref_phase]
        ).astype(np.float32)
        return obs

    def _body_frame_linvel(self) -> np.ndarray:
        return self.data.sensordata[self._linvel_adr : self._linvel_adr + 3].astype(np.float32)

    def _tilt_rad(self) -> float:
        w, x, y, z = self.data.qpos[3:7]
        up_z = 1.0 - 2.0 * (x * x + y * y)
        return float(np.arccos(np.clip(up_z, -1.0, 1.0)))

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        self._apply_domain_randomization()

        mujoco.mj_resetDataKeyframe(self.model, self.data, self.stand_key_id)
        # Small initial joint perturbation for robustness
        if self.domain_randomization:
            self.data.qpos[self._jnt_qposadr] += self.np_random.uniform(-0.03, 0.03, size=NUM_ACTUATED_JOINTS)
            self.data.qpos[self._jnt_qposadr] = np.clip(
                self.data.qpos[self._jnt_qposadr], JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH
            )
        mujoco.mj_forward(self.model, self.data)

        self._step_count = 0
        self._sim_time = 0.0
        self._prev_action = DEFAULT_STAND_JOINTS.copy()
        self._prev_prev_action = DEFAULT_STAND_JOINTS.copy()
        self._prev_contacts_bin = np.ones(4, dtype=np.float32)
        self._contact_age_s = np.full(4, 0.5, dtype=np.float32)
        self._action_queue.clear()
        for _ in range(3):
            self._action_queue.append(DEFAULT_STAND_JOINTS.copy())
        self._next_push_step = int(self.np_random.integers(50, 100))

        self._sample_command()
        if self.use_imitation and self.ref_lib is not None and len(self.ref_lib) > 0:
            self.active_clip = self.ref_lib.select_for_command(
                float(self._command[0]), float(self._command[2]), rng=self.np_random
            )
            # DeepMimic Reference State Initialization (RSI) on walking/turning episodes
            if self.active_clip is not None and float(np.hypot(self._command[0], self._command[2])) > 0.02 and self._fixed_command is None:
                self._sim_time = float(self.np_random.uniform(0.0, max(self.active_clip.duration_s, 0.1)))
                ref0 = self.active_clip.sample_at_time(self._sim_time)
                self.data.qpos[self._jnt_qposadr] = np.clip(ref0["joint_angles"], JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH)
                mujoco.mj_forward(self.model, self.data)
        else:
            self.active_clip = None

        ref = self._get_ref_state()
        obs = self._get_obs(ref)
        return obs, {"curriculum_stage": CURRICULUM_STAGES[self.curriculum_stage], "model_version": MODEL_VERSION}

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        act_norm = np.clip(np.asarray(action, dtype=np.float32), -1.0, 1.0)
        joint_target = clamp_joint_targets(DEFAULT_STAND_JOINTS + act_norm * self._action_scale)

        self._action_queue.append(joint_target)
        applied_target = self._action_queue[-1 - self._action_delay_steps] if self._action_delay_steps > 0 else joint_target

        # Dynamic command schedules for stop & target stages
        stage_name = CURRICULUM_STAGES[self.curriculum_stage]
        if self._fixed_command is None:
            if stage_name == "stop":
                if 75 <= self._step_count < 140:
                    self._command[:] = [0.0, 0.0, 0.0]
                elif self._step_count == 140:
                    self._command[:] = [0.15, 0.0, 0.0]
            elif stage_name == "target":
                self._update_target_command()

        # Perturbation impulses in perturb stage (and occasionally in later stages)
        self.data.xfrc_applied[:] = 0.0
        if stage_name == "perturb" and self._step_count == self._next_push_step:
            fx = float(self.np_random.uniform(-0.14, 0.14))
            fy = float(self.np_random.uniform(-0.14, 0.14))
            self.data.xfrc_applied[1, 0:3] = [fx, fy, 0.0]
            self._next_push_step += int(self.np_random.integers(60, 110))

        # Step physics
        for _ in range(self.n_substeps):
            self.data.ctrl[:] = applied_target
            mujoco.mj_step(self.model, self.data)
        self.data.xfrc_applied[:] = 0.0

        self._step_count += 1
        self._sim_time += self.control_dt

        # State readouts
        qpos = self.data.qpos[self._jnt_qposadr].astype(np.float32)
        qvel = self.data.qvel[self._jnt_qveladr].astype(np.float32)
        linvel = self._body_frame_linvel()
        gyro = self.data.sensordata[self._gyro_adr : self._gyro_adr + 3].astype(np.float32)
        contacts = np.clip(self.data.sensordata[self._touch_adrs].astype(np.float32) / 0.20, 0.0, 1.0)
        z = float(self.data.qpos[2])
        tilt = self._tilt_rad()

        # Fall / numerical termination check
        non_finite = not (np.all(np.isfinite(self.data.qpos)) and np.all(np.isfinite(self.data.qvel)))
        fell = non_finite or (tilt > np.radians(55.0)) or (z < 0.022) or (z > 0.12)
        terminated = bool(fell)
        truncated = bool(self._step_count >= self.max_steps and not terminated)

        # Reward decomposition (logged separately!)
        ref = self._get_ref_state()
        w = self.weights

        r_upright = float(w.upright * np.exp(-4.0 * tilt * tilt) * np.exp(-400.0 * (z - 0.048) ** 2))

        vx_err = float(linvel[0] - self._command[0])
        vy_err = float(linvel[1] - self._command[1])
        yaw_err = float(gyro[2] - self._command[2])
        vel_track = float(np.exp(-40.0 * (vx_err * vx_err + vy_err * vy_err)))
        yaw_track = float(np.exp(-4.0 * yaw_err * yaw_err))
        # Sharp progress + tracking reward; standing still during walk command yields ~0
        if self._command[0] > 0.03:
            progress = float(np.clip(linvel[0] / self._command[0], -0.5, 1.15))
            r_command = float(w.command * (0.40 * vel_track + 0.50 * progress + 0.35 * yaw_track) - 1.2)
        else:
            r_command = float(w.command * (0.65 * vel_track + 0.35 * yaw_track))

        # Imitation terms (zero when use_imitation=False or stationary stand command)
        cmd_mag = float(np.hypot(self._command[0], self._command[2]))
        if self.use_imitation and ref is not None and cmd_mag > 0.02:
            q_diff = qpos - ref["joint_angles"]
            r_track_joint = float(w.imitation_joint * np.exp(-18.0 * float(np.mean(q_diff * q_diff))))
            v_diff = float(np.linalg.norm(linvel[:2] - ref["root_vel"][:2]))
            r_track_vel = float(w.imitation_vel * np.exp(-35.0 * v_diff * v_diff))
            c_diff = float(np.mean(np.abs(contacts - ref["foot_contacts"])))
            r_track_contact = float(w.imitation_contact * (1.0 - c_diff))
            joint_track_rmse = float(np.sqrt(np.mean(q_diff * q_diff)))
        else:
            r_track_joint = 0.0
            r_track_vel = 0.0
            r_track_contact = 0.0
            joint_track_rmse = 0.0

        # Smoothness: 1st-order velocity + 2nd-order jerk + anti-chatter paw micro-bounce penalty
        act_delta = joint_target - self._prev_action
        act_jerk = joint_target - 2.0 * self._prev_action + self._prev_prev_action
        c_bin = (contacts > 0.3).astype(np.float32)
        toggled = np.abs(c_bin - self._prev_contacts_bin) > 0.5
        chatter_pen = float(np.sum(toggled & (self._contact_age_s < 0.12))) * 0.06
        self._contact_age_s = np.where(toggled, 0.0, self._contact_age_s + self.control_dt)
        self._prev_contacts_bin = c_bin

        r_smooth = float(
            -w.smoothness * (float(np.mean(act_delta * act_delta)) + 0.5 * float(np.mean(act_jerk * act_jerk)))
            - chatter_pen
        )

        tau = self.data.actuator_force.astype(np.float32)
        power = tau * qvel
        r_energy = float(-w.energy * float(np.mean(power * power)))

        r_fall = float(-w.fall_penalty) if fell else 0.0

        total_reward = r_upright + r_command + r_track_joint + r_track_vel + r_track_contact + r_smooth + r_energy + r_fall

        self._prev_prev_action = self._prev_action.copy()
        self._prev_action = joint_target.copy()
        obs = self._get_obs(ref) if not non_finite else np.zeros(OBS_DIM, dtype=np.float32)

        # Auto-curriculum advancement based on measured non-fall success
        if (terminated or truncated) and self.auto_curriculum:
            self._success_window.append(0.0 if fell else 1.0)
            if len(self._success_window) >= 8 and float(np.mean(self._success_window)) >= 0.85:
                if self.curriculum_stage < len(CURRICULUM_STAGES) - 1:
                    self.curriculum_stage += 1
                    self._success_window.clear()

        info = {
            "fell": fell,
            "tilt_deg": float(np.degrees(tilt)),
            "pelvis_z": z,
            "vx": float(linvel[0]),
            "vy": float(linvel[1]),
            "yaw_rate": float(gyro[2]),
            "vx_cmd": float(self._command[0]),
            "yaw_cmd": float(self._command[2]),
            "contacts": contacts.copy(),
            "joint_track_rmse": joint_track_rmse,
            "curriculum_stage": CURRICULUM_STAGES[self.curriculum_stage],
            "reward_terms": {
                "r_track_joint": r_track_joint,
                "r_track_vel": r_track_vel,
                "r_track_contact": r_track_contact,
                "r_upright": r_upright,
                "r_command": r_command,
                "r_smooth": r_smooth,
                "r_energy": r_energy,
                "r_fall": r_fall,
            },
        }
        return obs, float(total_reward), terminated, truncated, info

    def render(self, camera: str = "track_three_quarter") -> np.ndarray:
        if self._renderer is None:
            self._renderer = mujoco.Renderer(self.model, height=360, width=640)
        scene_opt = mujoco.MjvOption()
        scene_opt.geomgroup[2] = 1
        scene_opt.geomgroup[3] = 0
        self._renderer.update_scene(self.data, camera=camera, scene_option=scene_opt)
        return self._renderer.render().copy()

    def close(self) -> None:
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
