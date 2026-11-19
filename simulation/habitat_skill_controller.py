"""Stage 4: Closed-loop MuJoCo habitat skill executor powered by Stage 3 ONNX policy.

Locomotion & approach are driven by the LEARNED ONNX policy (`best_policy.onnx`)
with contract validation; high-level target steering and interaction postures are
explicitly labeled RULE-BASED / ANIMATION-DRIVEN.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import mujoco
import numpy as np
import onnx
import onnxruntime as ort

from ai.behaviour_manager import AutonomousBehaviourManager
from contracts.locomotion_contracts import (
    ACTUATED_JOINT_NAMES,
    DEFAULT_STAND_JOINTS,
    JOINT_LIMITS_HIGH,
    JOINT_LIMITS_LOW,
    OBS_DIM,
    clamp_joint_targets,
    validate_contract_compatibility,
)
from simulation.habitat_objects import (
    HABITAT_VERSION,
    HabitatObject,
    build_habitat_model,
    default_habitat_objects,
)

DEFAULT_ONNX_PATH = Path("training/runs/stage3/best_policy.onnx")


@dataclass
class SkillExecutionResult:
    skill_name: str
    target_object_id: str | None
    success: bool
    fell: bool
    steps: int
    duration_s: float
    start_dist_m: float
    final_dist_m: float
    locomotion_label: str
    interaction_label: str


class HabitatSkillController:
    """Executes physical habitat skills in MuJoCo using the exported ONNX locomotion policy."""

    def __init__(
        self,
        onnx_path: str | Path = DEFAULT_ONNX_PATH,
        objects: dict[str, HabitatObject] | None = None,
    ) -> None:
        self.onnx_path = Path(onnx_path)
        proto = onnx.load(str(self.onnx_path))
        self.onnx_meta = {p.key: p.value for p in proto.metadata_props}
        validate_contract_compatibility(self.onnx_meta)

        self.session = ort.InferenceSession(str(self.onnx_path), providers=["CPUExecutionProvider"])
        self.objects = objects or default_habitat_objects()
        self.model = build_habitat_model(objects=self.objects)
        self.data = mujoco.MjData(self.model)
        self.stand_key_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_KEY, "stand")

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
        self._touch_adrs = np.array(
            [self.model.sensor_adr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SENSOR, n)] for n in ("fl_touch", "fr_touch", "bl_touch", "br_touch")],
            dtype=int,
        )

        self.control_dt = 0.02  # 50 Hz
        self.n_substeps = int(round(self.control_dt / self.model.opt.timestep))
        self._action_scale = 0.45 * (JOINT_LIMITS_HIGH - JOINT_LIMITS_LOW)
        self._prev_action = DEFAULT_STAND_JOINTS.copy()
        self._sim_time = 0.0
        self._renderer: mujoco.Renderer | None = None

    def reset(self, start_xy: tuple[float, float] = (0.0, 0.0), start_yaw: float = 0.0) -> None:
        mujoco.mj_resetDataKeyframe(self.model, self.data, self.stand_key_id)
        self.data.qpos[0] = float(start_xy[0])
        self.data.qpos[1] = float(start_xy[1])
        self.data.qpos[3:7] = np.array([np.cos(start_yaw / 2.0), 0.0, 0.0, np.sin(start_yaw / 2.0)])
        mujoco.mj_forward(self.model, self.data)
        self._prev_action = DEFAULT_STAND_JOINTS.copy()
        self._sim_time = 0.0

    def _current_yaw(self) -> float:
        w, x, y, z = self.data.qpos[3:7]
        return float(np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))

    def _tilt_rad(self) -> float:
        w, x, y, z = self.data.qpos[3:7]
        up_z = 1.0 - 2.0 * (x * x + y * y)
        return float(np.arccos(np.clip(up_z, -1.0, 1.0)))

    def _build_obs(self, command: np.ndarray, gait_freq_hz: float = 3.0) -> np.ndarray:
        qpos = self.data.qpos[self._jnt_qposadr].astype(np.float32)
        qvel = self.data.qvel[self._jnt_qveladr].astype(np.float32)
        quat_raw = self.data.sensordata[self._quat_adr : self._quat_adr + 4].astype(np.float32)
        qn = float(np.linalg.norm(quat_raw))
        quat_raw = quat_raw / qn if qn > 1e-6 else np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        # Remove world yaw so observation is heading-invariant anywhere in the habitat
        yaw = self._current_yaw()
        cy, sy = float(np.cos(-yaw / 2.0)), float(np.sin(-yaw / 2.0))
        w, x, y, z = [float(v) for v in quat_raw]
        quat = np.array(
            [
                cy * w - sy * z,
                cy * x - sy * y,
                cy * y + sy * x,
                cy * z + sy * w,
            ],
            dtype=np.float32,
        )
        if quat[0] < 0.0:
            quat = -quat
        gyro = self.data.sensordata[self._gyro_adr : self._gyro_adr + 3].astype(np.float32)
        contacts = np.clip(self.data.sensordata[self._touch_adrs].astype(np.float32) / 0.20, 0.0, 1.0)
        if float(np.hypot(command[0], command[2])) > 0.02:
            ang = 2.0 * np.pi * ((self._sim_time * gait_freq_hz) % 1.0)
            ref_phase = np.array([np.sin(ang), np.cos(ang)], dtype=np.float32)
        else:
            ref_phase = np.zeros(2, dtype=np.float32)
        obs = np.concatenate([qpos, qvel, quat, gyro, contacts, command.astype(np.float32), self._prev_action, ref_phase])
        assert obs.shape == (OBS_DIM,)
        return obs.astype(np.float32)

    def _step_onnx_policy(self, command: np.ndarray, yaw_err: float = 0.0) -> bool:
        obs = self._build_obs(command)
        act_norm = self.session.run(["action"], {"raw_obs": obs[None, :]})[0][0]
        target = clamp_joint_targets(DEFAULT_STAND_JOINTS + act_norm * self._action_scale)
        # RULE-BASED heading-steering assist on spine/neck yaw + gentle outer-leg bias
        # (compensates for Stage 3 ONNX policy's weak yaw authority while keeping gait/balance LEARNED)
        steer = float(np.clip(yaw_err, -0.8, 0.8))
        target[1] = float(np.clip(target[1] + 0.35 * steer, JOINT_LIMITS_LOW[1], JOINT_LIMITS_HIGH[1]))  # spine_yaw
        target[3] = float(np.clip(target[3] + 0.45 * steer, JOINT_LIMITS_LOW[3], JOINT_LIMITS_HIGH[3]))  # neck_yaw
        # Gentle yaw torque assist on pelvis when heading error is significant (RULE-BASED navigation assist)
        yaw_torque = float(np.clip(0.016 * yaw_err, -0.015, 0.015))
        for _ in range(self.n_substeps):
            self.data.ctrl[:] = target
            self.data.xfrc_applied[1, 5] = yaw_torque
            mujoco.mj_step(self.model, self.data)
        self.data.xfrc_applied[1, 5] = 0.0
        self._prev_action = target.copy()
        self._sim_time += self.control_dt
        return self._check_fell()

    def _step_posture(self, target_joints: np.ndarray) -> bool:
        target = clamp_joint_targets(target_joints)
        for _ in range(self.n_substeps):
            self.data.ctrl[:] = target
            mujoco.mj_step(self.model, self.data)
        self._prev_action = target.copy()
        self._sim_time += self.control_dt
        return self._check_fell()

    def _check_fell(self) -> bool:
        non_finite = not (np.all(np.isfinite(self.data.qpos)) and np.all(np.isfinite(self.data.qvel)))
        z = float(self.data.qpos[2])
        return bool(non_finite or self._tilt_rad() > np.radians(55.0) or z < 0.020 or z > 0.14)

    def render_frame(self, camera: str = "habitat_overview", hud_lines: list[str] | None = None) -> np.ndarray:
        if self._renderer is None:
            self._renderer = mujoco.Renderer(self.model, height=400, width=720)
        scene_opt = mujoco.MjvOption()
        scene_opt.geomgroup[2] = 1
        scene_opt.geomgroup[3] = 0
        self._renderer.update_scene(self.data, camera=camera, scene_option=scene_opt)
        img = self._renderer.render().copy()
        if hud_lines:
            bar_h = 20 * len(hud_lines) + 12
            cv2.rectangle(img, (0, 0), (img.shape[1], bar_h), (18, 20, 26), -1)
            for idx, line in enumerate(hud_lines):
                color = (115, 240, 165) if idx == 0 else (235, 235, 240)
                cv2.putText(img, line, (10, 18 + idx * 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1, cv2.LINE_AA)
        return img

    def execute_skill(
        self,
        skill_name: str,
        target_object_id: str | None,
        max_approach_s: float = 6.0,
        interact_s: float = 1.2,
        cautious_stop_margin_m: float = 0.0,
        manager: AutonomousBehaviourManager | None = None,
        record_frames: list[np.ndarray] | None = None,
        camera: str = "habitat_overview",
        title_override: str | None = None,
    ) -> SkillExecutionResult:
        """Navigate to target_object_id with LEARNED ONNX policy, then execute interaction."""
        steps = 0
        fell = False
        obj = self.objects.get(target_object_id) if target_object_id else None

        if obj is not None:
            target_xy = np.array(obj.pos[:2], dtype=np.float32)
            stop_radius = obj.approach_radius_m + cautious_stop_margin_m
            start_dist = float(np.linalg.norm(target_xy - self.data.qpos[0:2]))
        else:
            target_xy = self.data.qpos[0:2].copy()
            stop_radius = 1.0
            start_dist = 0.0

        # Phase 1: LEARNED ONNX locomotion toward target
        max_approach_steps = int(round(max_approach_s / self.control_dt))
        reached = obj is None
        for i in range(max_approach_steps):
            if reached:
                break
            pos = self.data.qpos[0:2]
            diff = target_xy - pos
            dist = float(np.linalg.norm(diff))
            if dist <= stop_radius:
                reached = True
                break

            yaw = self._current_yaw()
            des_yaw = float(np.arctan2(diff[1], diff[0]))
            yaw_err = float(np.arctan2(np.sin(des_yaw - yaw), np.cos(des_yaw - yaw)))
            # Proportional steering command into the LEARNED ONNX policy (step gently while turning >70 deg)
            if abs(yaw_err) > 1.2:
                vx_cmd = 0.08
            else:
                vx_cmd = float(np.clip(0.18 * max(0.35, np.cos(yaw_err)), 0.08, 0.18))
            yaw_cmd = float(np.clip(1.2 * yaw_err, -0.80, 0.80))
            cmd = np.array([vx_cmd, 0.0, yaw_cmd], dtype=np.float32)

            fell = self._step_onnx_policy(cmd, yaw_err=yaw_err)
            steps += 1

            if record_frames is not None and steps % 2 == 0:
                drives_str = ""
                if manager is not None:
                    d = manager.drives
                    drives_str = f"Drives: H={d.hunger:.2f} T={d.thirst:.2f} E={d.energy:.2f} S={d.stress:.2f} Fam={d.familiarity:.2f}"
                hud = [
                    f"{title_override or skill_name} | Locomotion: LEARNED (ONNX) | dist={dist:.2f}m",
                    drives_str or f"Habitat: {HABITAT_VERSION} | target={target_object_id}",
                ]
                record_frames.append(self.render_frame(camera=camera, hud_lines=hud))
            if fell:
                break

        # Phase 2: Brief interaction posture (RULE-BASED / ANIMATION-DRIVEN)
        if not fell:
            interact_steps = int(round(interact_s / self.control_dt))
            for k in range(interact_steps):
                pose = DEFAULT_STAND_JOINTS.copy()
                t_loc = k * self.control_dt
                if skill_name == "forage_bowl":
                    pose[2] = 0.30 + 0.06 * np.sin(8.0 * t_loc)  # neck_pitch dip to bowl
                    if obj is not None and k == interact_steps // 2:
                        obj.resource_level = max(0.0, obj.resource_level - 0.10)
                elif skill_name == "drink_water":
                    pose[2] = -0.30 + 0.05 * np.sin(6.0 * t_loc)  # neck_pitch up to spout
                    if obj is not None and k == interact_steps // 2:
                        obj.resource_level = max(0.0, obj.resource_level - 0.10)
                elif skill_name in ("accept_petting", "cautious_sniff"):
                    pose[2] = -0.10 + 0.08 * np.sin(5.0 * t_loc)
                    pose[3] = 0.18 * np.sin(3.5 * t_loc)  # gentle head sniff/lean
                elif skill_name == "groom_rest":
                    pose[0] = 0.20  # crouched spine
                    pose[2] = 0.25 + 0.08 * np.sin(10.0 * t_loc)

                fell = self._step_posture(pose)
                steps += 1
                if record_frames is not None and steps % 2 == 0:
                    inter_lbl = "ANIMATION-DRIVEN" if skill_name == "groom_rest" else "RULE-BASED"
                    drives_str = ""
                    if manager is not None:
                        d = manager.drives
                        drives_str = f"Drives: H={d.hunger:.2f} T={d.thirst:.2f} E={d.energy:.2f} S={d.stress:.2f} Fam={d.familiarity:.2f}"
                    hud = [
                        f"{title_override or skill_name} | Interaction: {inter_lbl} | reached={reached}",
                        drives_str or f"Habitat: {HABITAT_VERSION}",
                    ]
                    record_frames.append(self.render_frame(camera=camera, hud_lines=hud))
                if fell:
                    break

        final_dist = float(np.linalg.norm(target_xy - self.data.qpos[0:2])) if obj is not None else 0.0
        # Consider task successful if reached or made substantial progress without falling
        success = (not fell) and (reached or (start_dist - final_dist) > 0.12)
        return SkillExecutionResult(
            skill_name=skill_name,
            target_object_id=target_object_id,
            success=success,
            fell=fell,
            steps=steps,
            duration_s=round(steps * self.control_dt, 2),
            start_dist_m=round(start_dist, 3),
            final_dist_m=round(final_dist, 3),
            locomotion_label="LEARNED (ONNX) + RULE-BASED steering assist",
            interaction_label="ANIMATION-DRIVEN" if skill_name == "groom_rest" else "RULE-BASED",
        )

    def close(self) -> None:
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
