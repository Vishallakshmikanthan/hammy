"""Stage 5: Real MuJoCo + ONNX TrajectoryClipV1 generator for Three.js `hamster.glb` replay.

Runs our verified Stage 3 ONNX policy (`best_policy.onnx`) inside `habitat_mujoco_v1.0.0`
(`hamster_mjcf_v1.0.0`, 16 DoF) and exports schema-validated `TrajectoryClipV1` clips
ready for `LocalObjectStorage` and the browser Three.js `ClipPlayer`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from contracts.locomotion_contracts import MODEL_VERSION
from contracts.schemas import (
    BehaviourType,
    EventOrigin,
    TrajectoryClipV1,
    TrajectoryKeyframeV1,
)
from simulation.habitat_objects import HABITAT_VERSION
from simulation.habitat_skill_controller import DEFAULT_ONNX_PATH, HabitatSkillController

SKILL_TO_TARGET: dict[str, Optional[str]] = {
    "forage_bowl": "prop_bowl_main",
    "drink_water": "prop_bottle_main",
    "enter_tunnel": "prop_tunnel_main",
    "retreat_to_hideout": "prop_hideout_main",
    "avoid_and_retreat": "prop_hideout_main",
    "explore_wheel": "prop_wheel_main",
    "cautious_sniff": "prop_treat_zone",
    "accept_petting": "prop_treat_zone",
    "groom_rest": None,
}


def _mujoco_quat_to_threejs(mj_quat_wxyz: np.ndarray) -> list[float]:
    """Convert MuJoCo [w, x, y, z] (Z-up) quaternion to Three.js [x, y, z, w] (Y-up)."""
    w, x, y, z = [float(v) for v in mj_quat_wxyz]
    # Coordinate mapping (x_3js = x_mj, y_3js = z_mj, z_3js = -y_mj)
    return [round(x, 6), round(z, 6), round(-y, 6), round(w, 6)]


def make_mujoco_clip_id(pet_id: str, skill_id: str, seed: int) -> str:
    raw = f"mujoco:{MODEL_VERSION}:{pet_id}:{skill_id}:{seed}".encode("utf-8")
    return "mjclip_" + hashlib.sha256(raw).hexdigest()[:14]


def generate_mujoco_onnx_clip(
    pet_id: str,
    skill_id: str,
    seed: int = 42,
    start_sim_time_sec: float = 0.0,
    max_approach_s: float = 5.0,
    interact_s: float = 1.0,
    fps: float = 20.0,
    start_xy: Tuple[float, float] = (0.0, 0.0),
    start_yaw: float = 0.0,
    onnx_path: Path = DEFAULT_ONNX_PATH,
) -> TrajectoryClipV1:
    """Roll out a physical MuJoCo + ONNX skill episode and return a `TrajectoryClipV1`."""
    ctrl = HabitatSkillController(onnx_path=onnx_path)
    ctrl.reset(start_xy=start_xy, start_yaw=start_yaw)

    target_id = SKILL_TO_TARGET.get(skill_id, "prop_bowl_main")
    obj = ctrl.objects.get(target_id) if target_id else None
    stop_radius = (obj.approach_radius_m + (0.06 if skill_id == "cautious_sniff" else 0.0)) if obj else 1.0
    target_xy = np.array(obj.pos[:2], dtype=np.float32) if obj else ctrl.data.qpos[0:2].copy()

    keyframes: list[TrajectoryKeyframeV1] = []
    record_stride = max(1, int(round((1.0 / fps) / ctrl.control_dt)))  # 50 Hz -> 20 Hz (~2-3 steps)
    step_idx = 0

    def _capture_kf() -> None:
        p = ctrl.data.qpos[0:3]
        q_mj = ctrl.data.qpos[3:7]
        joints = ctrl.data.qpos[ctrl._jnt_qposadr]
        touches = ctrl.data.sensordata[ctrl._touch_adrs]
        keyframes.append(
            TrajectoryKeyframeV1(
                t_sec=round(step_idx * ctrl.control_dt, 4),
                # MuJoCo (x, y, z_up) -> Three.js (x, y_up, -y)
                root_pos=[round(float(p[0]), 5), round(float(p[2]), 5), round(float(-p[1]), 5)],
                root_quat=_mujoco_quat_to_threejs(q_mj),
                joint_angles=[round(float(v), 5) for v in joints.tolist()],
                foot_contacts=[bool(t > 0.05) for t in touches.tolist()],
            )
        )

    _capture_kf()

    # Phase 1: LEARNED ONNX locomotion approach
    max_steps = int(round(max_approach_s / ctrl.control_dt))
    reached = obj is None
    for _ in range(max_steps):
        if reached:
            break
        diff = target_xy - ctrl.data.qpos[0:2]
        dist = float(np.linalg.norm(diff))
        if dist <= stop_radius:
            reached = True
            break
        yaw = ctrl._current_yaw()
        des_yaw = float(np.arctan2(diff[1], diff[0]))
        yaw_err = float(np.arctan2(np.sin(des_yaw - yaw), np.cos(des_yaw - yaw)))
        vx_cmd = 0.08 if abs(yaw_err) > 1.2 else float(np.clip(0.18 * max(0.35, np.cos(yaw_err)), 0.08, 0.18))
        yaw_cmd = float(np.clip(1.2 * yaw_err, -0.80, 0.80))
        fell = ctrl._step_onnx_policy(np.array([vx_cmd, 0.0, yaw_cmd], dtype=np.float32), yaw_err=yaw_err)
        step_idx += 1
        if step_idx % record_stride == 0:
            _capture_kf()
        if fell:
            break

    # Phase 2: Brief interaction posture
    interact_steps = int(round(interact_s / ctrl.control_dt))
    from contracts.locomotion_contracts import DEFAULT_STAND_JOINTS

    for k in range(interact_steps):
        pose = DEFAULT_STAND_JOINTS.copy()
        t_loc = k * ctrl.control_dt
        if skill_id == "forage_bowl":
            pose[2] = 0.30 + 0.06 * np.sin(8.0 * t_loc)
        elif skill_id == "drink_water":
            pose[2] = -0.30 + 0.05 * np.sin(6.0 * t_loc)
        elif skill_id in ("accept_petting", "cautious_sniff"):
            pose[2] = -0.10 + 0.08 * np.sin(5.0 * t_loc)
            pose[3] = 0.18 * np.sin(3.5 * t_loc)
        fell = ctrl._step_posture(pose)
        step_idx += 1
        if step_idx % record_stride == 0:
            _capture_kf()
        if fell:
            break

    ctrl.close()
    duration = round(step_idx * ctrl.control_dt, 4)
    clip_id = make_mujoco_clip_id(pet_id, skill_id, seed)
    return TrajectoryClipV1(
        clip_id=clip_id,
        pet_id=pet_id,
        skill_id=skill_id,
        seed=seed,
        origin=EventOrigin.OBSERVED_PHYSICS,
        behaviour_type=BehaviourType.LEARNED,
        morphology_version=MODEL_VERSION,
        environment_version=HABITAT_VERSION,
        fps=fps,
        start_sim_time_sec=start_sim_time_sec,
        end_sim_time_sec=round(start_sim_time_sec + duration, 4),
        keyframes=keyframes,
    )
