"""Stage 3 acceptance tests: locomotion env, contracts, ONNX export, and 100-ep evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort

from contracts.locomotion_contracts import (
    ACTION_DIM,
    DEFAULT_STAND_JOINTS,
    JOINT_LIMITS_HIGH,
    JOINT_LIMITS_LOW,
    OBS_DIM,
    LocomotionActionV1,
    LocomotionObservationV1,
    clamp_joint_targets,
    validate_contract_compatibility,
)
from training.hamster_locomotion_env import CURRICULUM_STAGES, HamsterLocomotionEnv


def test_locomotion_env_contracts_and_reward_decomposition():
    env = HamsterLocomotionEnv(source_filter="mixed", use_imitation=True, curriculum_stage=2, domain_randomization=True)
    obs, info = env.reset(seed=42)
    assert obs.shape == (OBS_DIM,)
    assert np.all(np.isfinite(obs))
    parsed = LocomotionObservationV1.from_vector(obs)
    assert len(parsed.joint_pos) == 16

    expected_terms = {
        "r_track_joint",
        "r_track_vel",
        "r_track_contact",
        "r_upright",
        "r_command",
        "r_smooth",
        "r_energy",
        "r_fall",
    }
    for _ in range(25):
        act = np.zeros(ACTION_DIM, dtype=np.float32)
        obs, rew, term, trunc, info = env.step(act)
        assert obs.shape == (OBS_DIM,)
        assert np.all(np.isfinite(obs))
        assert np.isfinite(rew)
        assert set(info["reward_terms"].keys()) == expected_terms

    # Verify all 6 curriculum stages reset cleanly
    for st in range(len(CURRICULUM_STAGES)):
        env.set_curriculum_stage(st)
        o, i = env.reset(seed=100 + st)
        assert o.shape == (OBS_DIM,)
        assert i["curriculum_stage"] == CURRICULUM_STAGES[st]
    env.close()


def test_exported_onnx_contracts_and_finite_outputs():
    onnx_path = Path("training/runs/stage3/best_policy.onnx")
    assert onnx_path.exists(), f"Missing exported policy: {onnx_path}"

    proto = onnx.load(str(onnx_path))
    meta = {p.key: p.value for p in proto.metadata_props}
    validate_contract_compatibility(meta)
    assert meta.get("baked_obs_norm") == "true"

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(7)
    dummy_obs = rng.normal(0.0, 0.3, size=(32, OBS_DIM)).astype(np.float32)
    out = sess.run(["action"], {"raw_obs": dummy_obs})[0]
    assert out.shape == (32, ACTION_DIM)
    assert np.all(np.isfinite(out))
    assert np.all(out >= -1.0001) and np.all(out <= 1.0001)

    # Verify mapped joint targets pass LocomotionActionV1 contract
    scale = 0.45 * (JOINT_LIMITS_HIGH - JOINT_LIMITS_LOW)
    targets = clamp_joint_targets(DEFAULT_STAND_JOINTS + out[0] * scale)
    act = LocomotionActionV1(joint_targets=targets.tolist())
    assert len(act.joint_targets) == 16


def test_ablation_report_and_acceptance_thresholds():
    report_path = Path("training/runs/stage3/ablation_report.json")
    assert report_path.exists(), f"Missing {report_path}"
    report = json.loads(report_path.read_text(encoding="utf-8"))

    # All 4 ablation conditions must be reported separately
    for cond in ("imitation_synthetic", "imitation_real", "imitation_mixed", "no_imitation"):
        assert cond in report["ablation"], f"Missing ablation condition: {cond}"
        ev = report["ablation"][cond]
        assert ev["n_episodes"] == 100
        assert ev["all_actions_finite"] is True

    best = report["best_condition"]
    best_ev = report["ablation"][best]
    assert best_ev["non_fall_rate_pct"] >= 95.0, f"Best policy non-fall rate {best_ev['non_fall_rate_pct']}% < 95%"
    assert best_ev["mean_walk_distance_5s_m"] > 0.10, f"Possible zero-velocity collapse: {best_ev['mean_walk_distance_5s_m']} m"
    assert report["onnx_export"]["max_abs_diff_vs_pytorch"] < 1e-4

    for video in (
        "renders/stage3/policy_walk_speeds.mp4",
        "renders/stage3/policy_turn_left_right.mp4",
        "renders/stage3/policy_stop_start.mp4",
        "renders/stage3/stage3_policy_preview.png",
    ):
        p = Path(video)
        assert p.exists() and p.stat().st_size > 10_000, f"Missing or empty policy render: {p}"
