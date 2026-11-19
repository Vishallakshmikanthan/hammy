"""Stage 1 acceptance tests: Syrian hamster MJCF model & versioned locomotion contracts."""

from __future__ import annotations

from pathlib import Path

import mujoco
import numpy as np
import pytest

from contracts.locomotion_contracts import (
    ACTUATED_JOINT_NAMES,
    DEFAULT_STAND_JOINTS,
    JOINT_LIMITS_HIGH,
    JOINT_LIMITS_LOW,
    MODEL_VERSION,
    NUM_ACTUATED_JOINTS,
    OBS_DIM,
    LocomotionActionV1,
    LocomotionObservationV1,
    clamp_joint_targets,
    export_locomotion_json_schemas,
    validate_contract_compatibility,
)

MODEL_PATH = Path("simulation/models/hamster/hamster.xml")


def _load_stand_state():
    model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
    data = mujoco.MjData(model)
    key_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "stand")
    assert key_id >= 0, "Missing 'stand' keyframe in hamster.xml"
    mujoco.mj_resetDataKeyframe(model, data, key_id)
    mujoco.mj_forward(model, data)
    return model, data, key_id


def test_mjcf_structure_mass_dof_and_geoms():
    model, data, _ = _load_stand_state()

    # Exact 16 actuated DoF + 1 passive tail DoF
    assert model.nu == NUM_ACTUATED_JOINTS == 16
    act_joints = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, model.actuator_trnid[i, 0])
        for i in range(model.nu)
    ]
    assert tuple(act_joints) == ACTUATED_JOINT_NAMES

    tail_jnt = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "tail_pitch")
    assert tail_jnt >= 0

    # Total mass ~0.125 kg (published Syrian hamster range)
    total_mass = float(np.sum(model.body_mass))
    assert 0.120 <= total_mass <= 0.130, f"Unexpected total mass: {total_mass:.4f} kg"

    # Explicit torque limits on all actuators
    for i in range(model.nu):
        assert model.actuator_forcelimited[i] == 1
        lo, hi = model.actuator_forcerange[i]
        assert lo < 0.0 < hi

    # Separated visual (group 2, no contact) and collision (group 3, contact) geoms
    vis_count = 0
    col_count = 0
    for g in range(model.ngeom):
        if model.geom_group[g] == 2:
            assert model.geom_contype[g] == 0 and model.geom_conaffinity[g] == 0
            vis_count += 1
        elif model.geom_group[g] == 3:
            assert model.geom_contype[g] > 0 and model.geom_conaffinity[g] > 0
            col_count += 1
    assert vis_count >= 15
    assert col_count >= 10


def test_stands_10s_without_nan_or_drift():
    model, data, _ = _load_stand_state()
    init_xy = data.qpos[0:2].copy()

    n_steps = int(round(10.0 / model.opt.timestep))  # 5000 steps
    min_z = float("inf")
    max_z = -float("inf")
    max_tilt_deg = 0.0

    for _ in range(n_steps):
        data.ctrl[:] = DEFAULT_STAND_JOINTS
        mujoco.mj_step(model, data)
        assert np.all(np.isfinite(data.qpos)), "NaN/Inf in qpos during 10s stand"
        assert np.all(np.isfinite(data.qvel)), "NaN/Inf in qvel during 10s stand"
        z = float(data.qpos[2])
        min_z = min(min_z, z)
        max_z = max(max_z, z)

        # Body up-vector z-component from pelvis quaternion [w, x, y, z]
        w, x, y, qz = data.qpos[3:7]
        up_z = 1.0 - 2.0 * (x * x + y * y)
        tilt = float(np.degrees(np.arccos(np.clip(up_z, -1.0, 1.0))))
        max_tilt_deg = max(max_tilt_deg, tilt)

    drift_xy = float(np.linalg.norm(data.qpos[0:2] - init_xy))
    assert drift_xy < 0.015, f"Excessive horizontal drift over 10s: {drift_xy:.4f} m"
    assert 0.030 <= min_z and max_z <= 0.065, f"Height out of bounds: [{min_z:.4f}, {max_z:.4f}]"
    assert max_tilt_deg < 12.0, f"Excessive body tilt over 10s: {max_tilt_deg:.2f} deg"

    # Verify all 4 paw touch sensors register positive ground contact force
    for name in ("fl_touch", "fr_touch", "bl_touch", "br_touch"):
        sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, name)
        adr = model.sensor_adr[sid]
        assert data.sensordata[adr] > 0.01, f"Paw sensor {name} lost contact: {data.sensordata[adr]}"


def test_clean_reset_and_joint_limits_respected():
    model, data, key_id = _load_stand_state()
    qpos_init = data.qpos.copy()
    qvel_init = data.qvel.copy()

    # Drive joints hard toward their extremes
    for step in range(250):
        target = JOINT_LIMITS_HIGH if (step // 50) % 2 == 0 else JOINT_LIMITS_LOW
        data.ctrl[:] = target
        mujoco.mj_step(model, data)

    # Check actuated joint positions stay within limits (+ small solver margin)
    for i, jname in enumerate(ACTUATED_JOINT_NAMES):
        jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, jname)
        qadr = model.jnt_qposadr[jid]
        lo, hi = model.jnt_range[jid]
        val = float(data.qpos[qadr])
        assert lo - 0.05 <= val <= hi + 0.05, f"Joint {jname}={val:.3f} violated [{lo}, {hi}]"

    # Reset and verify exact restoration
    mujoco.mj_resetDataKeyframe(model, data, key_id)
    mujoco.mj_forward(model, data)
    np.testing.assert_allclose(data.qpos, qpos_init, atol=1e-7)
    np.testing.assert_allclose(data.qvel, qvel_init, atol=1e-7)


def test_versioned_contracts_roundtrip_and_safety(tmp_path: Path):
    obs = LocomotionObservationV1(
        joint_pos=DEFAULT_STAND_JOINTS.tolist(),
        joint_vel=[0.0] * NUM_ACTUATED_JOINTS,
        body_quat=[1.0, 0.0, 0.0, 0.0],
        body_ang_vel=[0.0, 0.0, 0.0],
        foot_contacts=[1.0, 1.0, 1.0, 1.0],
        command=[0.15, 0.0, 0.0],
        prev_action=DEFAULT_STAND_JOINTS.tolist(),
        ref_phase=[0.0, 1.0],
    )
    vec = obs.to_vector()
    assert vec.shape == (OBS_DIM,)
    obs2 = LocomotionObservationV1.from_vector(vec)
    np.testing.assert_allclose(obs.to_vector(), obs2.to_vector(), atol=1e-6)

    # NaN rejected
    with pytest.raises(ValueError):
        LocomotionObservationV1(
            joint_pos=[float("nan")] + [0.0] * 15,
            joint_vel=[0.0] * 16,
            body_quat=[1.0, 0.0, 0.0, 0.0],
            body_ang_vel=[0.0, 0.0, 0.0],
            foot_contacts=[1.0, 1.0, 1.0, 1.0],
        )

    # Out-of-limits action rejected unless clamped
    raw = np.full(NUM_ACTUATED_JOINTS, 9.9, dtype=np.float32)
    with pytest.raises(ValueError):
        LocomotionActionV1(joint_targets=raw.tolist())

    clamped = clamp_joint_targets(raw)
    act = LocomotionActionV1(joint_targets=clamped.tolist())
    assert act.model_version == MODEL_VERSION

    # Contract mismatch rejected
    with pytest.raises(ValueError):
        validate_contract_compatibility(
            {"model_version": "hamster_wrong_v0", "obs_schema_version": "locomotion_obs_v1.0.0", "act_schema_version": "locomotion_act_v1.0.0"}
        )

    obs_p, act_p = export_locomotion_json_schemas(tmp_path)
    assert obs_p.exists() and act_p.exists()
