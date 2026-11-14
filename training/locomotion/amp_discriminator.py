"""
P4.2 AMP-Style Motion Discriminator:
Scores state transitions (q_t, q_{t+1}) against reference hamster gait data
and produces a bounded style reward r_style in [0, 1].
"""

from __future__ import annotations

import numpy as np
from training.locomotion.policy import AdamOptimizer, _xavier_init


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20.0, 20.0)))


class AMPDiscriminator:
    """2-layer MLP discriminator on concatenated joint transitions [q_t, q_{t+1}]."""

    def __init__(self, feature_dim: int, hidden_dim: int = 64, seed: int = 7) -> None:
        self.feature_dim = feature_dim
        rng = np.random.default_rng(seed)
        self.w1 = _xavier_init(feature_dim, hidden_dim, rng)
        self.b1 = np.zeros(hidden_dim, dtype=np.float32)
        self.w2 = _xavier_init(hidden_dim, hidden_dim, rng)
        self.b2 = np.zeros(hidden_dim, dtype=np.float32)
        self.w3 = _xavier_init(hidden_dim, 1, rng, scale=0.1)
        self.b3 = np.zeros(1, dtype=np.float32)
        self.opt = AdamOptimizer(lr=5e-4)

    def forward(self, x: np.ndarray) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        h1 = np.tanh(x @ self.w1 + self.b1)
        h2 = np.tanh(h1 @ self.w2 + self.b2)
        logit = (h2 @ self.w3 + self.b3).squeeze(-1)
        return logit, {"x": x, "h1": h1, "h2": h2}

    def style_reward(self, q_t: np.ndarray, q_next: np.ndarray) -> np.ndarray:
        x = np.concatenate([q_t, q_next], axis=-1)
        logit, _ = self.forward(x)
        prob = _sigmoid(logit)
        # Least-squares / bounded AMP style reward in [0, 1]
        return np.clip(1.0 - 0.5 * ((prob - 1.0) ** 2) * 2.0, 0.0, 1.0).astype(np.float32)

    def train_step(
        self,
        ref_transitions: np.ndarray,
        policy_transitions: np.ndarray,
        rng: np.random.Generator,
        batch_size: int = 256,
    ) -> float:
        n = min(batch_size, len(ref_transitions), len(policy_transitions))
        r_idx = rng.integers(0, len(ref_transitions), size=n)
        p_idx = rng.integers(0, len(policy_transitions), size=n)

        x = np.concatenate([ref_transitions[r_idx], policy_transitions[p_idx]], axis=0)
        y = np.concatenate([np.ones(n, dtype=np.float32), np.zeros(n, dtype=np.float32)], axis=0)

        logit, cache = self.forward(x)
        prob = _sigmoid(logit)
        loss = -np.mean(y * np.log(prob + 1e-6) + (1.0 - y) * np.log(1.0 - prob + 1e-6))

        d_logit = ((prob - y) / x.shape[0])[:, None]
        d_w3 = cache["h2"].T @ d_logit
        d_b3 = np.sum(d_logit, axis=0)
        d_h2 = d_logit @ self.w3.T
        d_z2 = d_h2 * (1.0 - cache["h2"] ** 2)
        d_w2 = cache["h1"].T @ d_z2
        d_b2 = np.sum(d_z2, axis=0)
        d_h1 = d_z2 @ self.w2.T
        d_z1 = d_h1 * (1.0 - cache["h1"] ** 2)
        d_w1 = x.T @ d_z1
        d_b1 = np.sum(d_z1, axis=0)

        self.opt.step(
            {"w1": self.w1, "b1": self.b1, "w2": self.w2, "b2": self.b2, "w3": self.w3, "b3": self.b3},
            {"w1": d_w1, "b1": d_b1, "w2": d_w2, "b2": d_b2, "w3": d_w3, "b3": d_b3},
        )
        return float(loss)

