"""Unit and integration tests for Phase 4 (P4.1 & P4.2) locomotion."""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import onnx
import pytest

from training.locomotion.amp_discriminator import AMPDiscriminator
from training.locomotion.contracts import (
    HAMSTER_MORPHOLOGY_VERSION,
    QUADRUPED_MORPHOLOGY_VERSION,
    spec_for_hamster,
    spec_for_quadruped,
    validate_checkpoint_compatibility,
)
from training.locomotion.curriculum import CurriculumState
from training.locomotion.keypoint_ingest import (
    generate_reference_hamster_gait,
    ingest_keypoints_json,
    validate_hamster_mjcf,
)
from training.locomotion.onnx_export import export_policy_to_onnx, verify_onnx_equivalence
from training.locomotion.policy import MLPActorCritic
from training.locomotion.quadruped_env import HAMSTER_XML_PATH, VectorizedLeggedEnv


def test_checkpoint_compatibility_rejects_mismatch():
    spec = spec_for_quadruped()
    good_meta = spec.to_metadata()
    validate_checkpoint_compatibility(good_meta, spec)

    bad_morph = {**good_meta, "morphology_version": HAMSTER_MORPHOLOGY_VERSION}
    with pytest.raises(ValueError, match="morphology_version"):
        validate_checkpoint_compatibility(bad_morph, spec)

    bad_obs = {**good_meta, "obs_schema_version": "locomotion_obs_v0.0.0"}
    with pytest.raises(ValueError, match="obs_schema_version"):
        validate_checkpoint_compatibility(bad_obs, spec)


def test_quadruped_and_hamster_envs_step_and_log_rewards():
    for morph, exp_obs, exp_act in [("quadruped", 45, 12), ("hamster", 51, 14)]:
        env = VectorizedLeggedEnv(num_envs=8, morphology=morph, seed=123)
        obs1 = env.reset(seed=123)
        obs2 = VectorizedLeggedEnv(num_envs=8, morphology=morph, seed=123).reset(seed=123)
        assert obs1.shape == (8, exp_obs)
        np.testing.assert_allclose(obs1, obs2)

        act = np.zeros((8, exp_act), dtype=np.float32)
        next_obs, rew, done, info = env.step(act)
        assert next_obs.shape == (8, exp_obs)
        assert not np.any(np.isnan(next_obs))
        assert not np.any(np.isnan(rew))
        assert set(info["reward_terms"].keys()) == {
            "velocity_tracking",
            "orientation",
            "torque_energy",
            "action_rate",
            "foot_slip",
            "falls",
        }


def test_curriculum_advances_only_on_measured_success():
    cur = CurriculumState(advance_threshold=0.72)
    assert cur.stage == "stand"
    assert not cur.update(0.50)
    assert cur.stage == "stand"
    assert cur.update(0.80)
    assert cur.stage == "perturbation_recovery"


def test_onnx_export_and_runtime_equivalence(tmp_path: Path):
    spec = spec_for_quadruped()
    policy = MLPActorCritic(obs_dim=spec.obs_dim, action_dim=spec.action_dim, seed=7)
    onnx_path = tmp_path / "test_policy.onnx"
    meta = spec.to_metadata()
    export_policy_to_onnx(policy, onnx_path, meta)

    max_diff = verify_onnx_equivalence(policy, onnx_path, num_samples=24, atol=1e-5)
    assert max_diff < 1e-5

    model = onnx.load(str(onnx_path))
    props = {p.key: p.value for p in model.metadata_props}
    assert props["morphology_version"] == QUADRUPED_MORPHOLOGY_VERSION
    assert props["obs_schema_version"] == spec.obs_schema_version


def test_hamster_mjcf_keypoint_ingest_and_amp_discriminator(tmp_path: Path):
    mjcf = validate_hamster_mjcf(HAMSTER_XML_PATH)
    assert mjcf["dof_count"] == 14
    assert len(mjcf["spine_joints"]) == 2
    assert 0.09 <= mjcf["total_mass_kg"] <= 0.16

    ref = generate_reference_hamster_gait(num_steps=100)
    kp_file = tmp_path / "keypoints.json"
    frames = [
        {
            "joints_14": ref["q"][i].tolist(),
            "contacts_4": ref["foot_contacts"][i].tolist(),
            "speed": float(ref["speed_m_s"][i]),
        }
        for i in range(100)
    ]
    kp_file.write_text(json.dumps({"frames": frames}), encoding="utf-8")
    ingested = ingest_keypoints_json(kp_file)
    assert ingested["q"].shape == (100, 14)
    assert ingested["stride_frequency_hz"] > 0.0

    disc = AMPDiscriminator(feature_dim=28)
    r_style = disc.style_reward(ref["q"][:-1], ref["q"][1:])
    assert r_style.shape == (99,)
    assert np.all((r_style >= 0.0) & (r_style <= 1.0))

