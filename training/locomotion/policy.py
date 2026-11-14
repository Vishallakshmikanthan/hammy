"""
Vectorized MLP Actor-Critic and PPO trainer for Phase 4 locomotion.
Implemented in vectorized NumPy so it runs reliably across both Linux/WSL2 and
Windows machines with Smart App Control (`WinError 4551`) restrictions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
import json
from pathlib import Path
import numpy as np


def _xavier_init(in_dim: int, out_dim: int, rng: np.random.Generator, scale: float = 1.0) -> np.ndarray:
    limit = scale * np.sqrt(6.0 / (in_dim + out_dim))
    return rng.uniform(-limit, limit, size=(in_dim, out_dim)).astype(np.float32)


class MLPActorCritic:
    """2-hidden-layer tanh MLP Actor + Critic with diagonal Gaussian policy."""

    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        hidden_dim: int = 64,
        action_scale: float = 0.80,
        seed: int = 42,
    ) -> None:
        self.obs_dim = obs_dim
        self.action_dim = action_dim
        self.hidden_dim = hidden_dim
        self.action_scale = action_scale
        rng = np.random.default_rng(seed)

        # Actor weights
        self.w1 = _xavier_init(obs_dim, hidden_dim, rng)
        self.b1 = np.zeros(hidden_dim, dtype=np.float32)
        self.w2 = _xavier_init(hidden_dim, hidden_dim, rng)
        self.b2 = np.zeros(hidden_dim, dtype=np.float32)
        self.w3 = _xavier_init(hidden_dim, action_dim, rng, scale=0.05)
        self.b3 = np.zeros(action_dim, dtype=np.float32)
        self.log_std = np.full(action_dim, -1.0, dtype=np.float32)

        # Critic weights
        self.vw1 = _xavier_init(obs_dim, hidden_dim, rng)
        self.vb1 = np.zeros(hidden_dim, dtype=np.float32)
        self.vw2 = _xavier_init(hidden_dim, hidden_dim, rng)
        self.vb2 = np.zeros(hidden_dim, dtype=np.float32)
        self.vw3 = _xavier_init(hidden_dim, 1, rng, scale=0.1)
        self.vb3 = np.zeros(1, dtype=np.float32)

    def forward_actor(self, obs: np.ndarray) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        z1 = obs @ self.w1 + self.b1
        h1 = np.tanh(z1)
        z2 = h1 @ self.w2 + self.b2
        h2 = np.tanh(z2)
        z3 = h2 @ self.w3 + self.b3
        mean = np.tanh(z3) * self.action_scale
        cache = {"obs": obs, "h1": h1, "h2": h2, "z3": z3, "raw_tanh": np.tanh(z3)}
        return mean.astype(np.float32), cache

    def forward_deterministic(self, obs: np.ndarray) -> np.ndarray:
        mean, _ = self.forward_actor(obs)
        return mean

    def forward_critic(self, obs: np.ndarray) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        h1 = np.tanh(obs @ self.vw1 + self.vb1)
        h2 = np.tanh(h1 @ self.vw2 + self.vb2)
        val = (h2 @ self.vw3 + self.vb3).squeeze(-1)
        return val.astype(np.float32), {"obs": obs, "h1": h1, "h2": h2}

    def sample_action(
        self, obs: np.ndarray, rng: np.random.Generator
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        mean, _ = self.forward_actor(obs)
        std = np.exp(self.log_std)
        noise = rng.normal(0.0, 1.0, size=mean.shape).astype(np.float32)
        action = np.clip(mean + noise * std, -self.action_scale, self.action_scale)
        log_prob = -0.5 * np.sum(((action - mean) / std) ** 2 + 2 * self.log_std + np.log(2 * np.pi), axis=-1)
        val, _ = self.forward_critic(obs)
        return action, log_prob.astype(np.float32), val

    def evaluate_log_prob(self, obs: np.ndarray, action: np.ndarray) -> np.ndarray:
        mean, _ = self.forward_actor(obs)
        std = np.exp(self.log_std)
        return (-0.5 * np.sum(((action - mean) / std) ** 2 + 2 * self.log_std + np.log(2 * np.pi), axis=-1)).astype(np.float32)

    def save(self, path: Path, metadata: Dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            path,
            w1=self.w1,
            b1=self.b1,
            w2=self.w2,
            b2=self.b2,
            w3=self.w3,
            b3=self.b3,
            log_std=self.log_std,
            vw1=self.vw1,
            vb1=self.vb1,
            vw2=self.vw2,
            vb2=self.vb2,
            vw3=self.vw3,
            vb3=self.vb3,
            action_scale=np.array([self.action_scale], dtype=np.float32),
            metadata_json=np.array([json.dumps(metadata)]),
        )

    @classmethod
    def load(cls, path: Path) -> tuple["MLPActorCritic", Dict[str, str]]:
        data = np.load(path, allow_pickle=False)
        w1 = data["w1"]
        w3 = data["w3"]
        policy = cls(
            obs_dim=w1.shape[0],
            action_dim=w3.shape[1],
            hidden_dim=w1.shape[1],
            action_scale=float(data["action_scale"][0]),
        )
        for k in ["w1", "b1", "w2", "b2", "w3", "b3", "log_std", "vw1", "vb1", "vw2", "vb2", "vw3", "vb3"]:
            setattr(policy, k, data[k].astype(np.float32))
        metadata = json.loads(str(data["metadata_json"][0]))
        return policy, metadata


class AdamOptimizer:
    def __init__(self, lr: float = 3e-4, beta1: float = 0.9, beta2: float = 0.999, eps: float = 1e-8) -> None:
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.t = 0
        self.m: Dict[str, np.ndarray] = {}
        self.v: Dict[str, np.ndarray] = {}

    def step(self, params: Dict[str, np.ndarray], grads: Dict[str, np.ndarray], max_grad_norm: float = 1.0) -> None:
        self.t += 1
        total_norm = np.sqrt(sum(float(np.sum(g * g)) for g in grads.values()))
        clip_coef = min(1.0, max_grad_norm / (total_norm + 1e-6))

        for name, param in params.items():
            g = grads[name] * clip_coef
            if name not in self.m:
                self.m[name] = np.zeros_like(param)
                self.v[name] = np.zeros_like(param)
            self.m[name] = self.beta1 * self.m[name] + (1 - self.beta1) * g
            self.v[name] = self.beta2 * self.v[name] + (1 - self.beta2) * (g * g)
            m_hat = self.m[name] / (1 - self.beta1 ** self.t)
            v_hat = self.v[name] / (1 - self.beta2 ** self.t)
            param -= self.lr * m_hat / (np.sqrt(v_hat) + self.eps)


def ppo_update(
    policy: MLPActorCritic,
    actor_opt: AdamOptimizer,
    critic_opt: AdamOptimizer,
    obs: np.ndarray,
    actions: np.ndarray,
    old_log_probs: np.ndarray,
    returns: np.ndarray,
    advantages: np.ndarray,
    clip_eps: float = 0.2,
    epochs: int = 4,
    batch_size: int = 512,
    rng: np.random.Generator = np.random.default_rng(0),
) -> Dict[str, float]:
    n = obs.shape[0]
    adv_norm = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
    actor_losses = []
    critic_losses = []

    for _ in range(epochs):
        perm = rng.permutation(n)
        for start in range(0, n, batch_size):
            mb = perm[start : start + batch_size]
            mb_obs = obs[mb]
            mb_act = actions[mb]
            mb_old_lp = old_log_probs[mb]
            mb_ret = returns[mb]
            mb_adv = adv_norm[mb]

            # Actor forward + analytic PPO-clip gradient
            mean, cache = policy.forward_actor(mb_obs)
            std = np.exp(policy.log_std)
            var = std ** 2
            log_prob = -0.5 * np.sum(((mb_act - mean) / std) ** 2 + 2 * policy.log_std + np.log(2 * np.pi), axis=-1)
            ratio = np.exp(np.clip(log_prob - mb_old_lp, -10.0, 10.0))

            surr1 = ratio * mb_adv
            surr2 = np.clip(ratio, 1.0 - clip_eps, 1.0 + clip_eps) * mb_adv
            unclipped = (surr1 <= surr2) | (
                ((mb_adv >= 0) & (ratio <= 1.0 + clip_eps)) | ((mb_adv < 0) & (ratio >= 1.0 - clip_eps))
            )
            actor_loss = -np.mean(np.minimum(surr1, surr2))
            actor_losses.append(float(actor_loss))

            # d(-min(surr1, surr2))/d(mean)
            scale = np.where(unclipped, -ratio * mb_adv, 0.0)[:, None] / mb_obs.shape[0]
            d_mean = scale * (mb_act - mean) / var
            d_z3 = d_mean * policy.action_scale * (1.0 - cache["raw_tanh"] ** 2)
            d_w3 = cache["h2"].T @ d_z3
            d_b3 = np.sum(d_z3, axis=0)
            d_h2 = d_z3 @ policy.w3.T
            d_z2 = d_h2 * (1.0 - cache["h2"] ** 2)
            d_w2 = cache["h1"].T @ d_z2
            d_b2 = np.sum(d_z2, axis=0)
            d_h1 = d_z2 @ policy.w2.T
            d_z1 = d_h1 * (1.0 - cache["h1"] ** 2)
            d_w1 = mb_obs.T @ d_z1
            d_b1 = np.sum(d_z1, axis=0)
            d_log_std = np.sum(scale * (((mb_act - mean) ** 2) / var - 1.0), axis=0)

            actor_opt.step(
                {
                    "w1": policy.w1,
                    "b1": policy.b1,
                    "w2": policy.w2,
                    "b2": policy.b2,
                    "w3": policy.w3,
                    "b3": policy.b3,
                    "log_std": policy.log_std,
                },
                {
                    "w1": d_w1,
                    "b1": d_b1,
                    "w2": d_w2,
                    "b2": d_b2,
                    "w3": d_w3,
                    "b3": d_b3,
                    "log_std": d_log_std,
                },
            )

            # Critic forward + MSE gradient
            val, vcache = policy.forward_critic(mb_obs)
            err = val - mb_ret
            critic_loss = 0.5 * np.mean(err ** 2)
            critic_losses.append(float(critic_loss))

            d_val = (err[:, None]) / mb_obs.shape[0]
            d_vw3 = vcache["h2"].T @ d_val
            d_vb3 = np.sum(d_val, axis=0)
            d_vh2 = d_val @ policy.vw3.T
            d_vz2 = d_vh2 * (1.0 - vcache["h2"] ** 2)
            d_vw2 = vcache["h1"].T @ d_vz2
            d_vb2 = np.sum(d_vz2, axis=0)
            d_vh1 = d_vz2 @ policy.vw2.T
            d_vz1 = d_vh1 * (1.0 - vcache["h1"] ** 2)
            d_vw1 = mb_obs.T @ d_vz1
            d_vb1 = np.sum(d_vz1, axis=0)

            critic_opt.step(
                {
                    "vw1": policy.vw1,
                    "vb1": policy.vb1,
                    "vw2": policy.vw2,
                    "vb2": policy.vb2,
                    "vw3": policy.vw3,
                    "vb3": policy.vb3,
                },
                {
                    "vw1": d_vw1,
                    "vb1": d_vb1,
                    "vw2": d_vw2,
                    "vb2": d_vb2,
                    "vw3": d_vw3,
                    "vb3": d_vb3,
                },
            )

    policy.log_std = np.clip(policy.log_std, -2.5, -0.3)
    return {
        "actor_loss": float(np.mean(actor_losses)),
        "critic_loss": float(np.mean(critic_losses)),
    }

