"""Benchmark 64 parallel MuJoCo envs + RTX 5070 GPU memory and throughput."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from training.hamster_locomotion_env import HamsterLocomotionEnv


def _make_env(rank: int):
    def _init():
        env = HamsterLocomotionEnv(curriculum_stage=2, domain_randomization=True)
        env.reset(seed=1000 + rank)
        return env
    return _init


def bench_vec(n_envs: int, use_subproc: bool, steps_per_env: int = 64) -> dict:
    if use_subproc:
        vec = SubprocVecEnv([_make_env(i) for i in range(n_envs)], start_method="spawn")
    else:
        vec = DummyVecEnv([_make_env(i) for i in range(n_envs)])
    obs = vec.reset()
    t0 = time.perf_counter()
    for _ in range(steps_per_env):
        acts = np.zeros((n_envs, 16), dtype=np.float32)
        obs, rew, dones, infos = vec.step(acts)
    dt = time.perf_counter() - t0
    total_steps = n_envs * steps_per_env
    fps = total_steps / max(dt, 1e-6)

    # Also measure tiny PPO update GPU memory on RTX 5070
    torch.cuda.reset_peak_memory_stats()
    model = PPO("MlpPolicy", vec, n_steps=64, batch_size=256, n_epochs=2, device="cuda", verbose=0, seed=42)
    t_tr = time.perf_counter()
    model.learn(total_timesteps=n_envs * 64)
    dt_tr = time.perf_counter() - t_tr
    peak_mb = torch.cuda.max_memory_allocated() / (1024.0 * 1024.0)
    vec.close()
    return {
        "n_envs": n_envs,
        "backend": "SubprocVecEnv" if use_subproc else "DummyVecEnv",
        "rollout_steps_per_sec": round(fps, 1),
        "ppo_train_steps_per_sec": round((n_envs * 64) / max(dt_tr, 1e-6), 1),
        "gpu_peak_allocated_mb": round(peak_mb, 2),
    }


def main() -> None:
    out_dir = Path("training/runs/stage3")
    out_dir.mkdir(parents=True, exist_ok=True)

    results = [
        bench_vec(8, use_subproc=True, steps_per_env=64),
        bench_vec(64, use_subproc=False, steps_per_env=64),
    ]
    out_path = out_dir / "bench_64envs.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
