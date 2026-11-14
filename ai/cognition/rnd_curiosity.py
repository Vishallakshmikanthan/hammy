"""
HAMMY — P7.1: Random Network Distillation (RND) Curiosity Module (`ai/cognition/rnd_curiosity.py`).
Includes:
  - Fixed random target network + online-trained predictor network
  - Intrinsic reward decay over simulated time
  - Noisy-TV safeguard: attenuates intrinsic reward on high-repeat / irreducible-entropy bins
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np

from training.locomotion.policy import AdamOptimizer, _xavier_init


@dataclass
class RNDConfig:
    obs_dim: int = 10
    embed_dim: int = 32
    hidden_dim: int = 64
    lr: float = 1e-3
    decay_half_life_steps: float = 2500.0
    max_intrinsic_reward: float = 0.25
    noisy_tv_damping_rate: float = 0.30


class RNDCuriosityModule:
    def __init__(self, config: RNDConfig = RNDConfig(), seed: int = 42) -> None:
        self.cfg = config
        rng = np.random.default_rng(seed)

        # Fixed random target network
        self.t_w1 = _xavier_init(config.obs_dim, config.hidden_dim, rng)
        self.t_b1 = np.zeros(config.hidden_dim, dtype=np.float32)
        self.t_w2 = _xavier_init(config.hidden_dim, config.embed_dim, rng)
        self.t_b2 = np.zeros(config.embed_dim, dtype=np.float32)

        # Trainable predictor network
        self.p_w1 = _xavier_init(config.obs_dim, config.hidden_dim, rng)
        self.p_b1 = np.zeros(config.hidden_dim, dtype=np.float32)
        self.p_w2 = _xavier_init(config.hidden_dim, config.embed_dim, rng)
        self.p_b2 = np.zeros(config.embed_dim, dtype=np.float32)

        self.opt = AdamOptimizer(lr=config.lr)
        self.total_steps = 0
        self.bin_visits: Dict[Tuple[int, ...], int] = {}
        self.running_err_mean = 0.05
        self.running_err_var = 0.02

    def _target(self, x: np.ndarray) -> np.ndarray:
        h = np.tanh(x @ self.t_w1 + self.t_b1)
        return (h @ self.t_w2 + self.t_b2).astype(np.float32)

    def _predictor(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        h = np.tanh(x @ self.p_w1 + self.p_b1)
        out = (h @ self.p_w2 + self.p_b2).astype(np.float32)
        return out, h

    def _discretize(self, obs_vec: np.ndarray) -> Tuple[int, ...]:
        return tuple(int(v) for v in np.round(obs_vec[:4] * 4.0))

    def compute_intrinsic_reward(self, obs_vec: np.ndarray, update: bool = True) -> float:
        x = np.asarray(obs_vec, dtype=np.float32).reshape(1, -1)
        target_emb = self._target(x)
        pred_emb, h = self._predictor(x)

        err = float(np.mean((pred_emb - target_emb) ** 2))
        self.running_err_mean = 0.99 * self.running_err_mean + 0.01 * err
        self.running_err_var = 0.99 * self.running_err_var + 0.01 * ((err - self.running_err_mean) ** 2)
        norm_err = err / (np.sqrt(self.running_err_var) + 1e-4)

        # Noisy-TV safeguard: damp repeated visits to the same discretized state bin
        b = self._discretize(x[0])
        visits = self.bin_visits.get(b, 0) + 1
        self.bin_visits[b] = visits
        noisy_tv_safeguard = 1.0 / (1.0 + self.cfg.noisy_tv_damping_rate * max(0, visits - 3))

        # Intrinsic reward decay
        decay = 0.5 ** (self.total_steps / max(1.0, self.cfg.decay_half_life_steps))
        r_int = float(np.clip(norm_err * 0.08 * decay * noisy_tv_safeguard, 0.0, self.cfg.max_intrinsic_reward))

        if update:
            self.total_steps += 1
            d_out = 2.0 * (pred_emb - target_emb) / self.cfg.embed_dim
            d_w2 = h.T @ d_out
            d_b2 = np.sum(d_out, axis=0)
            d_h = d_out @ self.p_w2.T
            d_z1 = d_h * (1.0 - h ** 2)
            d_w1 = x.T @ d_z1
            d_b1 = np.sum(d_z1, axis=0)
            self.opt.step(
                {"w1": self.p_w1, "b1": self.p_b1, "w2": self.p_w2, "b2": self.p_b2},
                {"w1": d_w1, "b1": d_b1, "w2": d_w2, "b2": d_b2},
            )

        return r_int

