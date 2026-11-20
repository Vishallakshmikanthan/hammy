"""
HAMMY — Phase C: GPU PyTorch Adversarial Motion Priors (AMP) Style Discriminator.

Implements Peng et al. (2021) AMP with Least-Squares GAN objective and Gradient Penalty
on RTX 5070 CUDA, trained directly on real Syrian hamster DeepLabCut reference clips
(`data/reference_motion/*_REAL.npz`).

AMP State Features per frame (36 dims):
  - joint_angles (16)
  - joint_velocities (16)
  - foot_contacts (4)
Transition pair fed to Discriminator: [s_t, s_{t+1}] -> 72 dims.
Outputs bounded real-hamster style reward r_style in [0, 1].
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import torch
import torch.nn as nn

from training.reference_library import ReferenceMotionLibrary

AMP_FRAME_DIM = 16 + 16 + 4  # 36
AMP_TRANSITION_DIM = AMP_FRAME_DIM * 2  # 72


def extract_amp_frame(
    qpos: np.ndarray, qvel: np.ndarray, contacts: np.ndarray
) -> np.ndarray:
    """Packs single-frame hamster biomechanical kinematics into 36-dim AMP feature vector."""
    return np.concatenate(
        [
            np.asarray(qpos, dtype=np.float32),
            np.clip(np.asarray(qvel, dtype=np.float32) * 0.15, -3.0, 3.0),
            np.clip(np.asarray(contacts, dtype=np.float32), 0.0, 1.0),
        ]
    ).astype(np.float32)


class RealVideoAMPDataset:
    """GPU-resident transition dataset built from REAL_VIDEO DeepLabCut hamster clips."""

    def __init__(
        self,
        ref_dir: str | Path = "data/reference_motion",
        source_filter: str = "real",
        dt: float = 0.02,
        device: str = "cuda",
    ) -> None:
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        lib = ReferenceMotionLibrary(ref_dir, source_filter=source_filter)  # type: ignore[arg-type]
        if len(lib) == 0:
            lib = ReferenceMotionLibrary(ref_dir, source_filter="mixed")

        transitions = []
        self.clip_sources: list[str] = []
        for clip in lib.clips:
            self.clip_sources.append(f"{clip.clip_id} ({clip.source_type}, {clip.num_frames}f)")
            # Resample clip smoothly at 50 Hz (dt=0.02s) so transition delta matches MuJoCo 50 Hz
            n_steps = max(4, int(round(clip.duration_s / dt)))
            frames = []
            prev_q = None
            for i in range(n_steps):
                sample = clip.sample_at_time(i * dt)
                q = sample["joint_angles"]
                dq = np.zeros_like(q) if prev_q is None else (q - prev_q) / dt
                prev_q = q
                frames.append(extract_amp_frame(q, dq, sample["foot_contacts"]))
            frames_arr = np.stack(frames, axis=0)
            for i in range(len(frames_arr) - 1):
                transitions.append(np.concatenate([frames_arr[i], frames_arr[i + 1]], axis=0))

        arr = np.stack(transitions, axis=0).astype(np.float32)
        self.transitions = torch.from_numpy(arr).to(self.device)
        self.num_transitions = int(self.transitions.shape[0])

    def sample(self, batch_size: int) -> torch.Tensor:
        idx = torch.randint(0, self.num_transitions, (batch_size,), device=self.device)
        return self.transitions[idx]


class GPUAMPDiscriminator(nn.Module):
    """RTX 5070 CUDA Least-Squares AMP Discriminator with Gradient Penalty."""

    def __init__(
        self,
        input_dim: int = AMP_TRANSITION_DIM,
        hidden_dim: int = 512,
        lr: float = 1e-4,
        gp_weight: float = 10.0,
        device: str = "cuda",
    ) -> None:
        super().__init__()
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.gp_weight = float(gp_weight)

        self.register_buffer("obs_mean", torch.zeros(input_dim, dtype=torch.float32))
        self.register_buffer("obs_var", torch.ones(input_dim, dtype=torch.float32))
        self.register_buffer("obs_count", torch.tensor(1e-4, dtype=torch.float32))

        self.trunk = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.SiLU(),
        )
        self.head = nn.Linear(hidden_dim // 2, 1)

        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=math.sqrt(2.0))
                nn.init.zeros_(m.bias)
        nn.init.uniform_(self.head.weight, -0.05, 0.05)

        self.to(self.device)
        self.optimizer = torch.optim.AdamW(self.parameters(), lr=lr, weight_decay=1e-4)

    @torch.no_grad()
    def update_rms(self, x: torch.Tensor) -> None:
        b_mean = x.mean(dim=0)
        b_var = x.var(dim=0, unbiased=False)
        b_cnt = float(x.shape[0])
        delta = b_mean - self.obs_mean
        tot = self.obs_count + b_cnt
        new_mean = self.obs_mean + delta * (b_cnt / tot)
        m2 = self.obs_var * self.obs_count + b_var * b_cnt + (delta * delta) * (self.obs_count * b_cnt / tot)
        self.obs_mean.copy_(new_mean)
        self.obs_var.copy_(torch.clamp(m2 / tot, min=1e-4))
        self.obs_count.copy_(tot)

    def normalize(self, x: torch.Tensor) -> torch.Tensor:
        return torch.clamp((x - self.obs_mean) / torch.sqrt(self.obs_var + 1e-5), -5.0, 5.0)

    def forward(self, trans: torch.Tensor) -> torch.Tensor:
        return self.head(self.trunk(self.normalize(trans))).squeeze(-1)

    @torch.no_grad()
    def compute_style_reward(self, trans: torch.Tensor) -> torch.Tensor:
        """Peng et al. LSGAN AMP reward: max(0, 1 - 0.25 * (D(s,s') - 1)^2) in [0, 1]."""
        logits = self.forward(trans)
        return torch.clamp(1.0 - 0.25 * (logits - 1.0) ** 2, 0.0, 1.0)

    def update(
        self,
        expert_dataset: RealVideoAMPDataset,
        policy_transitions: torch.Tensor,
        n_steps: int = 4,
        batch_size: int = 512,
    ) -> Dict[str, float]:
        self.train()
        n_pol = int(policy_transitions.shape[0])
        if n_pol < 32:
            return {"amp_loss": 0.0, "amp_expert_score": 0.0, "amp_policy_score": 0.0, "amp_gp": 0.0}

        # Update input normalization from balanced expert + policy batch
        self.update_rms(torch.cat([expert_dataset.sample(min(batch_size, n_pol)), policy_transitions[: min(batch_size, n_pol)]], dim=0))

        tot_loss, tot_exp, tot_pol, tot_gp = 0.0, 0.0, 0.0, 0.0
        for _ in range(n_steps):
            exp_x = expert_dataset.sample(batch_size).detach().requires_grad_(True)
            p_idx = torch.randint(0, n_pol, (batch_size,), device=self.device)
            pol_x = policy_transitions[p_idx].detach()

            exp_d = self.forward(exp_x)
            pol_d = self.forward(pol_x)

            # Least-squares GAN objective: expert -> +1, policy -> -1
            loss_exp = 0.5 * torch.mean((exp_d - 1.0) ** 2)
            loss_pol = 0.5 * torch.mean((pol_d + 1.0) ** 2)

            # R1 / Gradient Penalty on real-video expert transitions (prevents discriminator overconfidence)
            grads = torch.autograd.grad(
                outputs=exp_d.sum(),
                inputs=exp_x,
                create_graph=True,
                retain_graph=True,
                only_inputs=True,
            )[0]
            gp = torch.mean(torch.sum(grads * grads, dim=-1))

            loss = loss_exp + loss_pol + 0.5 * self.gp_weight * gp

            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.parameters(), 1.0)
            self.optimizer.step()

            tot_loss += float(loss.item())
            tot_exp += float(exp_d.mean().item())
            tot_pol += float(pol_d.mean().item())
            tot_gp += float(gp.item())

        return {
            "amp_loss": round(tot_loss / n_steps, 5),
            "amp_expert_score": round(tot_exp / n_steps, 4),
            "amp_policy_score": round(tot_pol / n_steps, 4),
            "amp_gp": round(tot_gp / n_steps, 5),
        }
