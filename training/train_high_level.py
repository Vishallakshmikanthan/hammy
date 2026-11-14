"""
HAMMY — P1.3: High-Level PPO Actor-Critic Policy & Training Loop (`training/train_high_level.py`).
Trains a learned high-level policy over the 8-skill options library in `HighLevelSMDPEnv`
using Proximal Policy Optimization (PPO-Clip) with Generalized Advantage Estimation (GAE).
Saves experiment configuration, training logs, and policy checkpoints under
`training/experiments/p1_3_high_level/`.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from contracts.schemas import BehaviourType
from simulation.smdp_env import HighLevelSMDPEnv
from ai.policies.skills import SKILL_NAMES


def softmax(x: np.ndarray) -> np.ndarray:
    e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e_x / np.sum(e_x, axis=-1, keepdims=True)


class AdamOptimizer:
    def __init__(self, params: List[np.ndarray], lr: float = 3e-4, beta1: float = 0.9, beta2: float = 0.999, eps: float = 1e-8):
        self.params = params
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.m = [np.zeros_like(p) for p in params]
        self.v = [np.zeros_like(p) for p in params]
        self.t = 0

    def step(self, grads: List[np.ndarray], max_grad_norm: float = 0.5):
        self.t += 1
        # Gradient clipping by global norm
        total_norm_sq = sum(np.sum(g ** 2) for g in grads)
        clip_coef = max_grad_norm / (math.sqrt(total_norm_sq) + 1e-6)
        if clip_coef < 1.0:
            grads = [g * clip_coef for g in grads]

        for i, (p, g) in enumerate(zip(self.params, grads)):
            self.m[i] = self.beta1 * self.m[i] + (1.0 - self.beta1) * g
            self.v[i] = self.beta2 * self.v[i] + (1.0 - self.beta2) * (g ** 2)
            m_hat = self.m[i] / (1.0 - self.beta1 ** self.t)
            v_hat = self.v[i] / (1.0 - self.beta2 ** self.t)
            p -= self.lr * m_hat / (np.sqrt(v_hat) + self.eps)


class PPOActorCritic:
    """
    2-Layer MLP Actor-Critic with PPO clipping and GAE.
    Actor: 41 -> 64 -> 64 -> 8 (Categorical policy pi(a|s))
    Critic: 41 -> 64 -> 64 -> 1 (Baseline value V(s))
    """

    def __init__(self, obs_dim: int = 41, act_dim: int = 8, hidden_dim: int = 64, seed: int = 42):
        self.obs_dim = obs_dim
        self.act_dim = act_dim
        self.hidden_dim = hidden_dim
        self.rng = np.random.default_rng(seed)

        # Orthogonal / Glorot initialization
        scale = 1.0 / math.sqrt(obs_dim)
        self.W1 = self.rng.uniform(-scale, scale, size=(obs_dim, hidden_dim)).astype(np.float32)
        self.b1 = np.zeros(hidden_dim, dtype=np.float32)
        scale = 1.0 / math.sqrt(hidden_dim)
        self.W2 = self.rng.uniform(-scale, scale, size=(hidden_dim, hidden_dim)).astype(np.float32)
        self.b2 = np.zeros(hidden_dim, dtype=np.float32)

        # Actor head (small initial weights so starting policy is close to uniform)
        self.W_actor = self.rng.uniform(-0.05, 0.05, size=(hidden_dim, act_dim)).astype(np.float32)
        self.b_actor = np.zeros(act_dim, dtype=np.float32)

        # Critic head
        self.W_critic = self.rng.uniform(-scale, scale, size=(hidden_dim, 1)).astype(np.float32)
        self.b_critic = np.zeros(1, dtype=np.float32)

    def parameters(self) -> List[np.ndarray]:
        return [self.W1, self.b1, self.W2, self.b2, self.W_actor, self.b_actor, self.W_critic, self.b_critic]

    def forward(self, obs: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Forward pass.
        obs shape: (N, obs_dim) or (obs_dim,)
        Returns: (pi_probs, values, h1, h2)
        """
        single = (obs.ndim == 1)
        x = obs[None, :] if single else obs

        # Shared representation layers with tanh activations
        h1 = np.tanh(x @ self.W1 + self.b1)
        h2 = np.tanh(h1 @ self.W2 + self.b2)

        logits = h2 @ self.W_actor + self.b_actor
        pi_probs = softmax(logits)
        values = (h2 @ self.W_critic + self.b_critic).squeeze(-1)

        if single:
            return pi_probs[0], values[0], h1[0], h2[0]
        return pi_probs, values, h1, h2

    def sample_action(self, obs: np.ndarray, deterministic: bool = False) -> Tuple[int, float, float]:
        pi_probs, value, _, _ = self.forward(obs)
        if deterministic:
            act_idx = int(np.argmax(pi_probs))
        else:
            act_idx = int(self.rng.choice(self.act_dim, p=pi_probs))
        log_prob = float(np.log(max(pi_probs[act_idx], 1e-8)))
        return act_idx, log_prob, float(value)

    def save(self, filepath: str | Path):
        data = {
            "obs_dim": self.obs_dim,
            "act_dim": self.act_dim,
            "hidden_dim": self.hidden_dim,
            "W1": self.W1.tolist(),
            "b1": self.b1.tolist(),
            "W2": self.W2.tolist(),
            "b2": self.b2.tolist(),
            "W_actor": self.W_actor.tolist(),
            "b_actor": self.b_actor.tolist(),
            "W_critic": self.W_critic.tolist(),
            "b_critic": self.b_critic.tolist(),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, filepath: str | Path) -> PPOActorCritic:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        model = cls(obs_dim=data["obs_dim"], act_dim=data["act_dim"], hidden_dim=data["hidden_dim"])
        model.W1 = np.array(data["W1"], dtype=np.float32)
        model.b1 = np.array(data["b1"], dtype=np.float32)
        model.W2 = np.array(data["W2"], dtype=np.float32)
        model.b2 = np.array(data["b2"], dtype=np.float32)
        model.W_actor = np.array(data["W_actor"], dtype=np.float32)
        model.b_actor = np.array(data["b_actor"], dtype=np.float32)
        model.W_critic = np.array(data["W_critic"], dtype=np.float32)
        model.b_critic = np.array(data["b_critic"], dtype=np.float32)
        return model


class LearnedPPOPolicy:
    """Wrapper implementing policy inference labelled `BehaviourType.LEARNED`."""
    behaviour_type = BehaviourType.LEARNED

    def __init__(self, model: PPOActorCritic):
        self.model = model

    def select_action(self, obs_features: np.ndarray, deterministic: bool = True) -> Tuple[int, str]:
        act_idx, _, _ = self.model.sample_action(obs_features, deterministic=deterministic)
        return act_idx, SKILL_NAMES[act_idx]


def compute_gae(rewards: np.ndarray, values: np.ndarray, dones: np.ndarray, next_val: float, gamma: float = 0.99, lam: float = 0.95) -> Tuple[np.ndarray, np.ndarray]:
    """Computes Generalized Advantage Estimates and discounted return targets."""
    T = len(rewards)
    advantages = np.zeros(T, dtype=np.float32)
    last_gae = 0.0
    for t in reversed(range(T)):
        val_next = next_val if t == T - 1 else values[t + 1]
        mask = 1.0 - dones[t]
        delta = rewards[t] + gamma * val_next * mask - values[t]
        advantages[t] = delta + gamma * lam * mask * last_gae
        last_gae = advantages[t]
    returns = advantages + values
    return advantages, returns


def train_ppo(
    total_iterations: int = 40,
    steps_per_iteration: int = 256,
    batch_size: int = 64,
    train_epochs: int = 4,
    clip_ratio: float = 0.20,
    lr: float = 4e-4,
    entropy_coef: float = 0.015,
    value_coef: float = 0.50,
    seed: int = 101,
    enable_memory: bool = False,
    exp_dir: str | Path = "training/experiments/p1_3_high_level",
) -> Tuple[PPOActorCritic, Dict[str, Any]]:
    exp_path = Path(exp_dir)
    exp_path.mkdir(parents=True, exist_ok=True)

    env = HighLevelSMDPEnv(
        max_smdp_steps=steps_per_iteration + 10,
        sub_dt_sec=2.0,
        enable_memory=enable_memory,
    )
    model = PPOActorCritic(obs_dim=env.obs_dim, act_dim=env.num_actions, hidden_dim=64, seed=seed)
    optimizer = AdamOptimizer(model.parameters(), lr=lr)

    obs, _ = env.reset(seed=seed)
    history_logs = []

    t_start = time.perf_counter()
    for iteration in range(1, total_iterations + 1):
        # 1. Collect rollout trajectory of SMDP transitions
        b_obs = np.empty((steps_per_iteration, env.obs_dim), dtype=np.float32)
        b_acts = np.empty(steps_per_iteration, dtype=np.int32)
        b_rews = np.empty(steps_per_iteration, dtype=np.float32)
        b_dones = np.empty(steps_per_iteration, dtype=np.float32)
        b_logp = np.empty(steps_per_iteration, dtype=np.float32)
        b_vals = np.empty(steps_per_iteration, dtype=np.float32)

        ep_rewards = []
        cur_ep_ret = 0.0

        for step in range(steps_per_iteration):
            act_idx, log_prob, val = model.sample_action(obs, deterministic=False)
            next_obs, r, term, trunc, info = env.step(act_idx)
            done = term or trunc

            b_obs[step] = obs
            b_acts[step] = act_idx
            b_rews[step] = r
            b_dones[step] = 1.0 if done else 0.0
            b_logp[step] = log_prob
            b_vals[step] = val

            cur_ep_ret += r
            obs = next_obs

            if done:
                ep_rewards.append(cur_ep_ret)
                cur_ep_ret = 0.0
                obs, _ = env.reset(seed=seed + iteration * 100 + step)

        _, last_val, _, _ = model.forward(obs)
        advantages, returns = compute_gae(b_rews, b_vals, b_dones, float(last_val))
        adv_std = float(np.std(advantages))
        norm_adv = (advantages - float(np.mean(advantages))) / (adv_std + 1e-8)

        # 2. PPO update over minibatches
        total_pi_loss = 0.0
        total_vf_loss = 0.0
        indices = np.arange(steps_per_iteration)

        for _ in range(train_epochs):
            model.rng.shuffle(indices)
            for start in range(0, steps_per_iteration, batch_size):
                end = start + batch_size
                mb_idx = indices[start:end]

                mb_obs = b_obs[mb_idx]
                mb_act = b_acts[mb_idx]
                mb_adv = norm_adv[mb_idx]
                mb_ret = returns[mb_idx]
                mb_old_logp = b_logp[mb_idx]

                # Forward pass
                h1 = np.tanh(mb_obs @ model.W1 + model.b1)
                h2 = np.tanh(h1 @ model.W2 + model.b2)
                logits = h2 @ model.W_actor + model.b_actor
                probs = softmax(logits)
                vals = (h2 @ model.W_critic + model.b_critic).squeeze(-1)

                cur_logp = np.log(np.maximum(probs[np.arange(len(mb_act)), mb_act], 1e-8))
                ratio = np.exp(cur_logp - mb_old_logp)

                surr1 = ratio * mb_adv
                surr2 = np.clip(ratio, 1.0 - clip_ratio, 1.0 + clip_ratio) * mb_adv
                clip_obj = np.minimum(surr1, surr2)

                # Entropy bonus
                entropy = -np.sum(probs * np.log(np.maximum(probs, 1e-8)), axis=-1)

                # Actor gradient
                grad_surr = np.where(surr1 <= surr2, mb_adv, np.where((ratio < 1.0 - clip_ratio) | (ratio > 1.0 + clip_ratio), 0.0, mb_adv))
                d_logp = np.zeros_like(probs)
                d_logp[np.arange(len(mb_act)), mb_act] = 1.0
                d_logits = -(probs * (grad_surr[:, None] * (d_logp - probs))) - entropy_coef * (probs * (np.log(np.maximum(probs, 1e-8)) + 1.0 - np.sum(probs * np.log(np.maximum(probs, 1e-8)), axis=-1, keepdims=True)))

                d_W_actor = (h2.T @ d_logits) / len(mb_idx)
                d_b_actor = np.mean(d_logits, axis=0)

                # Critic gradient
                d_val = value_coef * (vals - mb_ret)
                d_W_critic = (h2.T @ d_val[:, None]) / len(mb_idx)
                d_b_critic = np.mean(d_val, axis=0)

                # Backprop to hidden layers
                d_h2 = (d_logits @ model.W_actor.T) + (d_val[:, None] @ model.W_critic.T)
                d_pre_h2 = d_h2 * (1.0 - h2 ** 2)
                d_W2 = (h1.T @ d_pre_h2) / len(mb_idx)
                d_b2 = np.mean(d_pre_h2, axis=0)

                d_h1 = d_pre_h2 @ model.W2.T
                d_pre_h1 = d_h1 * (1.0 - h1 ** 2)
                d_W1 = (mb_obs.T @ d_pre_h1) / len(mb_idx)
                d_b1 = np.mean(d_pre_h1, axis=0)

                grads = [d_W1, d_b1, d_W2, d_b2, d_W_actor, d_b_actor, d_W_critic, d_b_critic]
                optimizer.step(grads)

                total_pi_loss += float(-np.mean(clip_obj))
                total_vf_loss += float(0.5 * np.mean((vals - mb_ret) ** 2))

        avg_ret = float(np.mean(ep_rewards)) if ep_rewards else float(cur_ep_ret)
        history_logs.append({
            "iteration": iteration,
            "mean_reward": round(float(np.mean(b_rews)), 5),
            "ep_return": round(avg_ret, 4),
            "policy_loss": round(total_pi_loss / (train_epochs * (steps_per_iteration / batch_size)), 5),
            "value_loss": round(total_vf_loss / (train_epochs * (steps_per_iteration / batch_size)), 5),
        })

        if iteration % 10 == 0 or iteration == 1:
            print(f"Iter {iteration:3d}/{total_iterations} | Mean Step Reward: {np.mean(b_rews):+.4f} | Avg Ep Return: {avg_ret:+.3f}")

    elapsed = time.perf_counter() - t_start

    # Save checkpoint & training config
    ckpt_path = exp_path / "checkpoint_ppo.json"
    model.save(ckpt_path)

    config_info = {
        "algorithm": "PPO-Clip (SMDP Options)",
        "behaviour_type": BehaviourType.LEARNED.value,
        "obs_dim": env.obs_dim,
        "act_dim": env.num_actions,
        "hidden_dim": 64,
        "skills": SKILL_NAMES,
        "total_iterations": total_iterations,
        "steps_per_iteration": steps_per_iteration,
        "total_smdp_steps": total_iterations * steps_per_iteration,
        "batch_size": batch_size,
        "train_epochs": train_epochs,
        "clip_ratio": clip_ratio,
        "lr": lr,
        "seed": seed,
        "elapsed_seconds": round(elapsed, 2),
    }

    (exp_path / "config.json").write_text(json.dumps(config_info, indent=2), encoding="utf-8")
    (exp_path / "training_log.json").write_text(json.dumps(history_logs, indent=2), encoding="utf-8")
    print(f">> PPO Training complete in {elapsed:.2f}s. Checkpoint saved to {ckpt_path}")
    return model, config_info


if __name__ == "__main__":
    train_ppo()

