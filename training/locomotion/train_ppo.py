"""
P4.1 Training Script: Vectorized PPO for Stand-In Quadruped (or Hamster) Locomotion.
Logs each reward term separately, advances curriculum based on measured success,
saves reproducible config, seed, code version, checkpoint, and ONNX export.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List
import numpy as np

from training.locomotion.onnx_export import export_policy_to_onnx, verify_onnx_equivalence
from training.locomotion.policy import AdamOptimizer, MLPActorCritic, ppo_update
from training.locomotion.quadruped_env import VectorizedLeggedEnv


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def compute_gae(
    rewards: np.ndarray,
    values: np.ndarray,
    dones: np.ndarray,
    last_values: np.ndarray,
    gamma: float = 0.99,
    lam: float = 0.95,
) -> tuple[np.ndarray, np.ndarray]:
    T, N = rewards.shape
    adv = np.zeros((T, N), dtype=np.float32)
    last_gae = np.zeros(N, dtype=np.float32)
    for t in reversed(range(T)):
        next_val = last_values if t == T - 1 else values[t + 1]
        next_non_term = 1.0 - dones[t].astype(np.float32)
        delta = rewards[t] + gamma * next_val * next_non_term - values[t]
        last_gae = delta + gamma * lam * next_non_term * last_gae
        adv[t] = last_gae
    returns = adv + values
    return returns, adv


def train(
    morphology: str = "quadruped",
    num_envs: int = 256,
    num_updates: int = 40,
    horizon: int = 48,
    seed: int = 42,
    out_dir: Path = Path("training/experiments/p4_1_quadruped"),
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    env = VectorizedLeggedEnv(
        num_envs=num_envs,
        morphology=morphology,
        episode_length=200,
        seed=seed,
        domain_randomization=True,
    )
    policy = MLPActorCritic(
        obs_dim=env.obs_dim,
        action_dim=env.action_dim,
        hidden_dim=64,
        action_scale=env.joint_limit,
        seed=seed,
    )
    actor_opt = AdamOptimizer(lr=4e-4)
    critic_opt = AdamOptimizer(lr=8e-4)

    obs = env.reset(seed=seed)
    history: List[Dict[str, Any]] = []
    t0 = time.perf_counter()

    for update in range(1, num_updates + 1):
        buf_obs = np.zeros((horizon, num_envs, env.obs_dim), dtype=np.float32)
        buf_act = np.zeros((horizon, num_envs, env.action_dim), dtype=np.float32)
        buf_lp = np.zeros((horizon, num_envs), dtype=np.float32)
        buf_rew = np.zeros((horizon, num_envs), dtype=np.float32)
        buf_val = np.zeros((horizon, num_envs), dtype=np.float32)
        buf_done = np.zeros((horizon, num_envs), dtype=bool)

        term_sums: Dict[str, float] = {
            "velocity_tracking": 0.0,
            "orientation": 0.0,
            "torque_energy": 0.0,
            "action_rate": 0.0,
            "foot_slip": 0.0,
            "falls": 0.0,
        }
        fall_count = 0
        speed_errs = []

        for t in range(horizon):
            act, lp, val = policy.sample_action(obs, rng)
            next_obs, rew, done, info = env.step(act)
            buf_obs[t] = obs
            buf_act[t] = act
            buf_lp[t] = lp
            buf_rew[t] = rew
            buf_val[t] = val
            buf_done[t] = done
            obs = next_obs

            for k in term_sums:
                term_sums[k] += float(np.mean(info["reward_terms"][k]))
            fall_count += int(np.sum(info["fallen"]))
            err = np.linalg.norm(info["lin_vel_xy"] - info["commands"][:, :2], axis=-1)
            speed_errs.append(float(np.mean(err)))

        _, _, last_val = policy.sample_action(obs, rng)
        returns, advantages = compute_gae(buf_rew, buf_val, buf_done, last_val)

        losses = ppo_update(
            policy=policy,
            actor_opt=actor_opt,
            critic_opt=critic_opt,
            obs=buf_obs.reshape(-1, env.obs_dim),
            actions=buf_act.reshape(-1, env.action_dim),
            old_log_probs=buf_lp.reshape(-1),
            returns=returns.reshape(-1),
            advantages=advantages.reshape(-1),
            rng=rng,
        )

        # Success rate proxy: non-falling rollouts with low tracking error
        mean_speed_err = float(np.mean(speed_errs))
        fall_rate = fall_count / (horizon * num_envs)
        success_rate = float(np.clip((1.0 - fall_rate * 10.0) * np.exp(-2.0 * mean_speed_err), 0.0, 1.0))
        advanced = env.curriculum.update(success_rate)
        if advanced:
            obs = env.reset()

        row = {
            "update": update,
            "curriculum_stage": env.curriculum.stage,
            "mean_reward": float(np.mean(buf_rew)),
            "success_rate": success_rate,
            "speed_error_m_s": mean_speed_err,
            "fall_rate": fall_rate,
            "reward_terms": {k: v / horizon for k, v in term_sums.items()},
            **losses,
        }
        history.append(row)

    elapsed = time.perf_counter() - t0
    meta = {
        **env.spec.to_metadata(),
        "seed": str(seed),
        "code_version": _git_sha(),
        "behaviour_type": "learned",
        "final_curriculum_stage": env.curriculum.stage,
    }

    ckpt_path = out_dir / "policy.npz"
    onnx_path = out_dir / "policy.onnx"
    policy.save(ckpt_path, meta)
    export_policy_to_onnx(policy, onnx_path, meta)
    onnx_max_diff = verify_onnx_equivalence(policy, onnx_path)

    report = {
        "config": {
            "morphology": morphology,
            "num_envs": num_envs,
            "num_updates": num_updates,
            "horizon": horizon,
            "seed": seed,
            "domain_randomization": True,
        },
        "metadata": meta,
        "training_seconds": round(elapsed, 2),
        "total_env_steps": num_updates * horizon * num_envs,
        "onnx_max_diff": onnx_max_diff,
        "final_metrics": history[-1],
        "history": history,
    }
    (out_dir / "train_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train P4.1 locomotion PPO policy")
    parser.add_argument("--morphology", default="quadruped", choices=["quadruped", "hamster"])
    parser.add_argument("--num-envs", type=int, default=256)
    parser.add_argument("--num-updates", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, default=Path("training/experiments/p4_1_quadruped"))
    args = parser.parse_args()

    res = train(
        morphology=args.morphology,
        num_envs=args.num_envs,
        num_updates=args.num_updates,
        seed=args.seed,
        out_dir=args.out_dir,
    )
    print(
        f"Trained {args.morphology} ({res['total_env_steps']} steps in {res['training_seconds']}s) | "
        f"stage={res['metadata']['final_curriculum_stage']} | onnx_diff={res['onnx_max_diff']:.2e}"
    )


if __name__ == "__main__":
    main()

