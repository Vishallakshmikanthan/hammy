"""
P4.1 Separate Evaluation Script:
Evaluates a trained checkpoint + ONNX model across 5 seeds and writes
docs/research/p4_1_locomotion_eval.md with real measured metrics and 95% CIs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List
import numpy as np

from training.locomotion.contracts import (
    spec_for_hamster,
    spec_for_quadruped,
    validate_checkpoint_compatibility,
)
from training.locomotion.onnx_export import verify_onnx_equivalence
from training.locomotion.policy import MLPActorCritic
from training.locomotion.quadruped_env import VectorizedLeggedEnv

DEFAULT_SEEDS = [42, 101, 202, 303, 404]


def evaluate_policy(
    ckpt_dir: Path,
    morphology: str = "quadruped",
    seeds: List[int] = DEFAULT_SEEDS,
    episodes_per_seed: int = 32,
    episode_length: int = 200,
) -> Dict[str, Any]:
    policy, meta = MLPActorCritic.load(ckpt_dir / "policy.npz")
    expected = spec_for_hamster() if morphology == "hamster" else spec_for_quadruped()
    validate_checkpoint_compatibility(meta, expected)

    onnx_max_diff = verify_onnx_equivalence(policy, ckpt_dir / "policy.onnx")

    per_seed: List[Dict[str, Any]] = []
    for seed in seeds:
        env = VectorizedLeggedEnv(
            num_envs=episodes_per_seed,
            morphology=morphology,
            episode_length=episode_length,
            seed=seed,
            domain_randomization=True,
        )
        # Evaluate on the final "stop" (mixed stand/walk/turn/stop) stage
        env.curriculum.stage_idx = 4
        obs = env.reset(seed=seed)

        falls = np.zeros(episodes_per_seed, dtype=np.int32)
        speed_errs = []
        term_accum = {
            "velocity_tracking": 0.0,
            "orientation": 0.0,
            "torque_energy": 0.0,
            "action_rate": 0.0,
            "foot_slip": 0.0,
            "falls": 0.0,
        }

        for _ in range(episode_length):
            act = policy.forward_deterministic(obs)
            obs, _, _, info = env.step(act)
            falls += info["fallen"].astype(np.int32)
            err = np.linalg.norm(info["lin_vel_xy"] - info["commands"][:, :2], axis=-1)
            speed_errs.append(float(np.mean(err)))
            for k in term_accum:
                term_accum[k] += float(np.mean(info["reward_terms"][k]))

        falls_per_ep = float(np.mean(falls))
        mean_speed_err = float(np.mean(speed_errs))
        success_rate = float(np.mean(falls == 0))
        per_seed.append(
            {
                "seed": seed,
                "success_rate": round(success_rate, 4),
                "falls_per_episode": round(falls_per_ep, 4),
                "speed_tracking_error_m_s": round(mean_speed_err, 4),
                "mean_reward_terms": {k: round(v / episode_length, 4) for k, v in term_accum.items()},
            }
        )

    def mean_ci95(vals: List[float]) -> tuple[float, float]:
        arr = np.array(vals, dtype=np.float64)
        mean = float(np.mean(arr))
        ci = float(1.96 * np.std(arr, ddof=1) / np.sqrt(len(arr))) if len(arr) > 1 else 0.0
        return round(mean, 4), round(ci, 4)

    sr_m, sr_ci = mean_ci95([r["success_rate"] for r in per_seed])
    fl_m, fl_ci = mean_ci95([r["falls_per_episode"] for r in per_seed])
    se_m, se_ci = mean_ci95([r["speed_tracking_error_m_s"] for r in per_seed])

    return {
        "morphology": morphology,
        "checkpoint_metadata": meta,
        "onnx_max_diff": onnx_max_diff,
        "seeds": seeds,
        "summary": {
            "success_rate": {"mean": sr_m, "ci95": sr_ci},
            "falls_per_episode": {"mean": fl_m, "ci95": fl_ci},
            "speed_tracking_error_m_s": {"mean": se_m, "ci95": se_ci},
        },
        "per_seed": per_seed,
    }


def write_eval_markdown(report: Dict[str, Any], out_md: Path) -> None:
    s = report["summary"]
    meta = report["checkpoint_metadata"]
    lines = [
        "# P4.1 — Stand-In Quadruped Locomotion Evaluation Report",
        "",
        f"- **Morphology:** `{meta.get('morphology_version')}`",
        f"- **Environment:** `{meta.get('environment_version')}`",
        f"- **Obs / Act Schemas:** `{meta.get('obs_schema_version')}` / `{meta.get('act_schema_version')}`",
        f"- **Code Version:** `{meta.get('code_version')}`",
        f"- **Behaviour Label:** `learned` (PPO MLP Actor-Critic)",
        f"- **ONNX Equivalence Max Diff:** `{report['onnx_max_diff']:.3e}` (tolerance `1e-5`)",
        "",
        "## 5-Seed Summary (Mean ± 95% CI)",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Success Rate (no-fall episodes) | {s['success_rate']['mean']:.4f} ± {s['success_rate']['ci95']:.4f} |",
        f"| Falls per Episode | {s['falls_per_episode']['mean']:.4f} ± {s['falls_per_episode']['ci95']:.4f} |",
        f"| Speed Tracking Error (m/s) | {s['speed_tracking_error_m_s']['mean']:.4f} ± {s['speed_tracking_error_m_s']['ci95']:.4f} |",
        "",
        "## Per-Seed Breakdown",
        "",
        "| Seed | Success Rate | Falls / Ep | Speed Error (m/s) |",
        "| --- | ---: | ---: | ---: |",
    ]
    for r in report["per_seed"]:
        lines.append(
            f"| {r['seed']} | {r['success_rate']:.4f} | {r['falls_per_episode']:.4f} | {r['speed_tracking_error_m_s']:.4f} |"
        )
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate P4.1 locomotion policy across 5 seeds")
    parser.add_argument("--ckpt-dir", type=Path, default=Path("training/experiments/p4_1_quadruped"))
    parser.add_argument("--morphology", default="quadruped", choices=["quadruped", "hamster"])
    parser.add_argument("--out-md", type=Path, default=Path("docs/research/p4_1_locomotion_eval.md"))
    args = parser.parse_args()

    report = evaluate_policy(args.ckpt_dir, morphology=args.morphology)
    (args.ckpt_dir / "eval_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_eval_markdown(report, args.out_md)
    print(f"Evaluated 5 seeds -> {args.out_md} | success={report['summary']['success_rate']['mean']:.3f}")


if __name__ == "__main__":
    main()

