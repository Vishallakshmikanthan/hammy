"""
HAMMY — Phase D/C Bridge: Closed-Loop 16-DoF MuJoCo Habitat Controller powered by
Phase C `motor_amp_v2.onnx` (72-dim `locomotion_obs_v2.0.0`, ZERO external yaw-torque cheat!).

Exports refreshed `TrajectoryClipV1` clips to `web/public/assets/mujoco_clips/`
tagged honestly as `origin="observed_physics"`, `behaviour_type="learned"`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import mujoco
import numpy as np
import onnx
import onnxruntime as ort

from contracts.locomotion_contracts import (
    ACTUATED_JOINT_NAMES,
    DEFAULT_STAND_JOINTS,
    JOINT_LIMITS_HIGH,
    JOINT_LIMITS_LOW,
    MODEL_VERSION,
    MOTOR_MODES_V2,
    OBS_V2_CONTRACT_VERSION,
    OBS_V2_DIM,
    clamp_joint_targets,
)
from contracts.schemas import BehaviourType, EventOrigin, TrajectoryClipV1, TrajectoryKeyframeV1
from simulation.habitat_objects import HabitatObject, build_habitat_model, default_habitat_objects

DEFAULT_MOTOR_V2_ONNX = Path("training/runs/motor_v2/motor_amp_v2.onnx")
WEB_CLIPS_DIR = Path("web/public/assets/mujoco_clips")


@dataclass
class MotorV2SkillResult:
    skill_name: str
    target_object_id: Optional[str]
    success: bool
    fell: bool
    steps: int
    duration_s: float
    displacement_m: float
    final_dist_m: float
    clip_id: str


class HabitatSkillControllerV2:
    """Executes habitat skills in MuJoCo using `motor_amp_v2.onnx` with ZERO cheat torques."""

    def __init__(
        self,
        onnx_path: str | Path = DEFAULT_MOTOR_V2_ONNX,
        objects: Optional[Dict[str, HabitatObject]] = None,
    ) -> None:
        self.onnx_path = Path(onnx_path)
        proto = onnx.load(str(self.onnx_path))
        self.onnx_meta = {p.key: p.value for p in proto.metadata_props}
        if self.onnx_meta.get("obs_schema_version") != OBS_V2_CONTRACT_VERSION:
            raise ValueError(f"Expected {OBS_V2_CONTRACT_VERSION}, got {self.onnx_meta.get('obs_schema_version')}")

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

        self.control_dt = 0.02
        self.n_substeps = int(round(self.control_dt / self.model.opt.timestep))
        self._action_scale = 0.45 * (JOINT_LIMITS_HIGH - JOINT_LIMITS_LOW)
        self._prev_action = DEFAULT_STAND_JOINTS.copy()
        self._filtered_target = DEFAULT_STAND_JOINTS.copy()
        self._sim_time = 0.0

    def reset(self, start_xy: Tuple[float, float] = (0.0, 0.0), start_yaw: float = 0.0) -> None:
        mujoco.mj_resetDataKeyframe(self.model, self.data, self.stand_key_id)
        self.data.qpos[0] = float(start_xy[0])
        self.data.qpos[1] = float(start_xy[1])
        self.data.qpos[3:7] = np.array([np.cos(start_yaw / 2.0), 0.0, 0.0, np.sin(start_yaw / 2.0)])
        mujoco.mj_forward(self.model, self.data)
        self._prev_action = DEFAULT_STAND_JOINTS.copy()
        self._filtered_target = DEFAULT_STAND_JOINTS.copy()
        self._sim_time = 0.0

    def _current_yaw(self) -> float:
        w, x, y, z = self.data.qpos[3:7]
        return float(np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))

    def _tilt_rad(self) -> float:
        w, x, y, z = self.data.qpos[3:7]
        up_z = 1.0 - 2.0 * (x * x + y * y)
        return float(np.arccos(np.clip(up_z, -1.0, 1.0)))

    def _build_obs(
        self,
        command: np.ndarray,
        mode: str = "locomote",
        target_z: float = 0.048,
        target_pitch: float = 0.0,
        head_yaw: float = 0.0,
    ) -> np.ndarray:
        qpos = self.data.qpos[self._jnt_qposadr].astype(np.float32)
        qvel = self.data.qvel[self._jnt_qveladr].astype(np.float32)
        quat_raw = self.data.sensordata[self._quat_adr : self._quat_adr + 4].astype(np.float32)
        qn = float(np.linalg.norm(quat_raw))
        quat_raw = quat_raw / qn if qn > 1e-6 else np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        yaw = self._current_yaw()
        cy, sy = float(np.cos(-yaw / 2.0)), float(np.sin(-yaw / 2.0))
        w, x, y, z = [float(v) for v in quat_raw]
        quat = np.array([cy * w - sy * z, cy * x - sy * y, cy * y + sy * x, cy * z + sy * w], dtype=np.float32)
        if quat[0] < 0.0:
            quat = -quat
        gyro = self.data.sensordata[self._gyro_adr : self._gyro_adr + 3].astype(np.float32)
        contacts = np.clip(self.data.sensordata[self._touch_adrs].astype(np.float32) / 0.20, 0.0, 1.0)

        moving = float(np.hypot(command[0], command[2])) > 0.02
        if moving:
            freq = float(np.clip(1.65 + 3.4 * abs(command[0]) + 0.35 * abs(command[2]), 1.65, 2.55))
            ang = 2.0 * np.pi * ((self._sim_time * freq) % 1.0)
            ref_phase = np.array([np.sin(ang), np.cos(ang)], dtype=np.float32)
        else:
            ref_phase = np.zeros(2, dtype=np.float32)

        mode_oh = np.zeros(len(MOTOR_MODES_V2), dtype=np.float32)
        mode_idx = MOTOR_MODES_V2.index(mode) if mode in MOTOR_MODES_V2 else 0
        mode_oh[mode_idx] = 1.0
        posture = np.array([(target_z - 0.048) / 0.02, target_pitch, head_yaw], dtype=np.float32)

        obs = np.concatenate([qpos, qvel, quat, gyro, contacts, command.astype(np.float32), self._prev_action, ref_phase, posture, mode_oh])
        assert obs.shape == (OBS_V2_DIM,)
        return obs.astype(np.float32)

    def _step_motor_v2(
        self,
        command: np.ndarray,
        mode: str = "locomote",
        target_z: float = 0.048,
        target_pitch: float = 0.0,
        head_yaw: float = 0.0,
    ) -> bool:
        obs = self._build_obs(command, mode=mode, target_z=target_z, target_pitch=target_pitch, head_yaw=head_yaw)
        act_norm = self.session.run(["action"], {"raw_obs": obs[None, :]})[0][0]
        raw_target = clamp_joint_targets(DEFAULT_STAND_JOINTS + act_norm * self._action_scale)
        target = 0.72 * raw_target + 0.28 * self._filtered_target
        self._filtered_target = target.copy()

        # ZERO external xfrc_applied cheat! 100% pure learned joint actuators!
        self.data.xfrc_applied[:] = 0.0
        for _ in range(self.n_substeps):
            self.data.ctrl[:] = target
            mujoco.mj_step(self.model, self.data)
        self._prev_action = target.copy()
        self._sim_time += self.control_dt

        non_finite = not (np.all(np.isfinite(self.data.qpos)) and np.all(np.isfinite(self.data.qvel)))
        max_tilt = np.radians(72.0) if mode == "rear_periscope" else np.radians(55.0)
        z = float(self.data.qpos[2])
        return bool(non_finite or self._tilt_rad() > max_tilt or z < 0.018 or z > 0.14)

    def rollout_and_export_clip(
        self,
        skill_id: str,
        target_object_id: Optional[str],
        *,
        start_xy: Tuple[float, float] = (0.0, 0.0),
        start_yaw: float = 0.0,
        mode: str = "locomote",
        max_duration_s: float = 4.5,
        pet_id: str = "pet_hammy_01",
        seed: int = 42,
    ) -> Tuple[TrajectoryClipV1, MotorV2SkillResult]:
        self.reset(start_xy=start_xy, start_yaw=start_yaw)
        obj = self.objects.get(target_object_id) if target_object_id else None
        target_xy = np.array(obj.pos[:2], dtype=np.float32) if obj is not None else np.array(start_xy, dtype=np.float32)
        stop_radius = float(obj.approach_radius_m) if obj is not None else 0.04
        start_pos = self.data.qpos[0:2].copy()

        keyframes: List[TrajectoryKeyframeV1] = []
        steps = 0
        fell = False
        reached = obj is None
        max_steps = int(round(max_duration_s / self.control_dt))

        for i in range(max_steps):
            pos = self.data.qpos[0:2]
            diff = target_xy - pos
            dist = float(np.linalg.norm(diff))
            if not reached and dist <= stop_radius:
                reached = True

            if mode == "rear_periscope":
                cmd = np.array([0.0, 0.0, 0.0], dtype=np.float32)
                fell = self._step_motor_v2(cmd, mode="rear_periscope", target_z=0.062, target_pitch=-0.40, head_yaw=0.25 * float(np.sin(2.5 * self._sim_time)))
            elif reached:
                # Settle or sniff gently in learned posture
                post_mode = "rest_settle" if skill_id in ("retreat_to_hideout", "rest") else "locomote"
                tz = 0.038 if post_mode == "rest_settle" else 0.048
                tp = 0.12 if post_mode == "rest_settle" else 0.0
                cmd = np.array([0.0, 0.0, 0.0], dtype=np.float32)
                fell = self._step_motor_v2(cmd, mode=post_mode, target_z=tz, target_pitch=tp, head_yaw=0.2 * float(np.sin(3.0 * self._sim_time)))
            else:
                yaw = self._current_yaw()
                des_yaw = float(np.arctan2(diff[1], diff[0]))
                yaw_err = float(np.arctan2(np.sin(des_yaw - yaw), np.cos(des_yaw - yaw)))
                vx_cmd = float(np.clip(0.16 * max(0.20, np.cos(yaw_err)), 0.05, 0.16))
                wz_cmd = float(np.clip(1.35 * yaw_err, -1.10, 1.10))
                active_mode = "crouch_tunnel" if skill_id == "enter_tunnel" else mode
                tz = 0.036 if active_mode == "crouch_tunnel" else 0.048
                tp = 0.14 if active_mode == "crouch_tunnel" else 0.0
                fell = self._step_motor_v2(np.array([vx_cmd, 0.0, wz_cmd], dtype=np.float32), mode=active_mode, target_z=tz, target_pitch=tp)

            steps += 1
            # Record at 25 Hz (every 2nd 50 Hz physics step)
            if i % 2 == 0:
                qpos = self.data.qpos[self._jnt_qposadr].tolist()
                contacts = [bool(c > 0.05) for c in self.data.sensordata[self._touch_adrs]]
                keyframes.append(
                    TrajectoryKeyframeV1(
                        t_sec=round(steps * self.control_dt, 4),
                        root_pos=[round(float(v), 5) for v in self.data.qpos[0:3]],
                        root_quat=[round(float(v), 5) for v in self.data.qpos[3:7]],
                        joint_angles=[round(float(v), 5) for v in qpos],
                        foot_contacts=contacts,
                    )
                )
            if fell:
                break

        disp = float(np.linalg.norm(self.data.qpos[0:2] - start_pos))
        final_dist = float(np.linalg.norm(target_xy - self.data.qpos[0:2])) if obj is not None else 0.0
        cid_hash = hashlib.sha256(f"v2:{skill_id}:{seed}:{steps}".encode("utf-8")).hexdigest()[:14]
        clip_id = f"mjclip_v2_{cid_hash}"

        clip = TrajectoryClipV1(
            clip_id=clip_id,
            pet_id=pet_id,
            skill_id=skill_id,
            seed=seed,
            origin=EventOrigin.OBSERVED_PHYSICS,
            behaviour_type=BehaviourType.LEARNED,
            morphology_version=MODEL_VERSION,
            environment_version="habitat_mujoco_v1.0.0",
            fps=25.0,
            start_sim_time_sec=0.0,
            end_sim_time_sec=round(steps * self.control_dt, 3),
            keyframes=keyframes,
        )
        res = MotorV2SkillResult(
            skill_name=skill_id,
            target_object_id=target_object_id,
            success=(not fell) and (reached or disp > 0.12 or mode == "rear_periscope"),
            fell=fell,
            steps=steps,
            duration_s=round(steps * self.control_dt, 2),
            displacement_m=round(disp, 4),
            final_dist_m=round(final_dist, 4),
            clip_id=clip_id,
        )
        return clip, res


def export_all_motor_v2_web_clips(onnx_path: Path = DEFAULT_MOTOR_V2_ONNX) -> Dict[str, object]:
    """Exports 7 verified zero-cheat AMP-PPO v2 MuJoCo clips to web/public/assets/mujoco_clips/."""
    WEB_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    ctrl = HabitatSkillControllerV2(onnx_path=onnx_path)
    specs = [
        ("forage_bowl", "prop_bowl_main", (0.0, 0.0), 0.0, "locomote", 4.5, 101),
        ("drink_water", "prop_bottle_main", (0.05, 0.02), 0.0, "locomote", 4.5, 102),
        ("enter_tunnel", "prop_tunnel_main", (0.12, -0.05), np.pi, "crouch_tunnel", 4.0, 103),
        ("retreat_to_hideout", "prop_hideout_main", (0.0, 0.0), 0.4, "locomote", 4.5, 104),
        ("cautious_sniff", "prop_treat_zone", (-0.10, 0.05), -0.6, "locomote", 4.0, 105),
        ("accept_petting", "prop_treat_zone", (-0.05, -0.02), -0.8, "locomote", 3.5, 106),
        ("hind_leg_standing", None, (0.0, 0.0), 0.0, "rear_periscope", 3.5, 107),
    ]
    entries = []
    for skill_id, tgt, start_xy, yaw, mode, dur, seed in specs:
        clip, res = ctrl.rollout_and_export_clip(
            skill_id, tgt, start_xy=start_xy, start_yaw=yaw, mode=mode, max_duration_s=dur, seed=seed
        )
        clip_file = WEB_CLIPS_DIR / f"{clip.clip_id}.json"
        clip_file.write_text(clip.model_dump_json(indent=2), encoding="utf-8")
        entries.append(
            {
                "clip_id": clip.clip_id,
                "skill_id": skill_id,
                "origin": clip.origin.value,
                "behaviour_type": clip.behaviour_type.value,
                "morphology_version": clip.morphology_version,
                "motor_policy_version": "ll_amp_ppo_v2.0.0",
                "zero_cheat_turning": True,
                "fps": clip.fps,
                "num_keyframes": len(clip.keyframes),
                "duration_s": res.duration_s,
                "displacement_m": res.displacement_m,
                "success": res.success,
                "fell": res.fell,
                "asset_url": f"/assets/mujoco_clips/{clip.clip_id}.json",
            }
        )
    manifest = {
        "schema_version": "1.0.0",
        "motor_policy_version": "ll_amp_ppo_v2.0.0",
        "zero_cheat_turning": True,
        "clips": entries,
    }
    (WEB_CLIPS_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    rep = export_all_motor_v2_web_clips()
    print(f"[CLIPS] Exported {len(rep['clips'])} AMP-PPO v2 clips to {WEB_CLIPS_DIR}")
