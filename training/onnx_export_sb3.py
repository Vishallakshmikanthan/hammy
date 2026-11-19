"""Export Stable-Baselines3 PPO policy + baked VecNormalize stats to ONNX.

Follows the pollen-robotics/microduck_rl pattern: observation normalization is baked
directly into the ONNX graph so downstream runtimes never drift from training preprocessing.
"""

from __future__ import annotations

import copy
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import VecNormalize

from contracts.locomotion_contracts import (
    ACTION_CONTRACT_VERSION,
    ACTION_DIM,
    MODEL_VERSION,
    OBS_CONTRACT_VERSION,
    OBS_DIM,
)


class BakedNormActor(torch.nn.Module):
    """Wraps SB3 MlpPolicy actor with baked VecNormalize (mean, var, clip) and action clip."""

    def __init__(
        self,
        ppo_model: PPO,
        obs_mean: np.ndarray,
        obs_var: np.ndarray,
        clip_obs: float = 10.0,
        epsilon: float = 1e-8,
    ) -> None:
        super().__init__()
        self.register_buffer("obs_mean", torch.tensor(obs_mean, dtype=torch.float32))
        self.register_buffer("obs_inv_std", torch.tensor(1.0 / np.sqrt(obs_var + epsilon), dtype=torch.float32))
        self.clip_obs = float(clip_obs)

        policy = ppo_model.policy
        self.mlp_extractor_policy = copy.deepcopy(policy.mlp_extractor.policy_net).to("cpu")
        self.action_net = copy.deepcopy(policy.action_net).to("cpu")

    def forward(self, raw_obs: torch.Tensor) -> torch.Tensor:
        norm_obs = torch.clamp((raw_obs - self.obs_mean) * self.obs_inv_std, -self.clip_obs, self.clip_obs)
        latent = self.mlp_extractor_policy(norm_obs)
        action = torch.clamp(self.action_net(latent), -1.0, 1.0)
        return action


def export_ppo_to_onnx(
    ppo_model: PPO,
    vec_norm: VecNormalize | None,
    onnx_path: Path,
    extra_metadata: dict[str, str] | None = None,
) -> dict[str, float | str]:
    onnx_path.parent.mkdir(parents=True, exist_ok=True)

    if vec_norm is not None:
        obs_mean = vec_norm.obs_rms.mean.astype(np.float32)
        obs_var = vec_norm.obs_rms.var.astype(np.float32)
        clip_obs = float(vec_norm.clip_obs)
        epsilon = float(vec_norm.epsilon)
    else:
        obs_mean = np.zeros(OBS_DIM, dtype=np.float32)
        obs_var = np.ones(OBS_DIM, dtype=np.float32)
        clip_obs = 10.0
        epsilon = 1e-8

    wrapper = BakedNormActor(ppo_model, obs_mean, obs_var, clip_obs=clip_obs, epsilon=epsilon).to("cpu").eval()
    dummy = torch.zeros((1, OBS_DIM), dtype=torch.float32)

    torch.onnx.export(
        wrapper,
        dummy,
        str(onnx_path),
        input_names=["raw_obs"],
        output_names=["action"],
        dynamic_axes={"raw_obs": {0: "batch"}, "action": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )

    # Embed versioned contract metadata directly into ONNX metadata_props
    model_proto = onnx.load(str(onnx_path))
    meta = {
        "model_version": MODEL_VERSION,
        "obs_schema_version": OBS_CONTRACT_VERSION,
        "act_schema_version": ACTION_CONTRACT_VERSION,
        "baked_obs_norm": "true",
        "obs_dim": str(OBS_DIM),
        "action_dim": str(ACTION_DIM),
    }
    if extra_metadata:
        meta.update({str(k): str(v) for k, v in extra_metadata.items()})
    for k, v in meta.items():
        entry = model_proto.metadata_props.add()
        entry.key = k
        entry.value = v
    onnx.save(model_proto, str(onnx_path))

    # Numerical equivalence check vs PyTorch + latency benchmark
    rng = np.random.default_rng(123)
    test_obs = rng.normal(0.0, 0.5, size=(256, OBS_DIM)).astype(np.float32)
    with torch.no_grad():
        pt_out = wrapper(torch.from_numpy(test_obs)).numpy()

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    ort_out = sess.run(["action"], {"raw_obs": test_obs})[0]
    max_diff = float(np.max(np.abs(pt_out - ort_out)))

    # Single-step inference latency (1000 iterations)
    single_obs = test_obs[:1]
    t0 = time.perf_counter()
    for _ in range(1000):
        sess.run(["action"], {"raw_obs": single_obs})
    dt_ms = (time.perf_counter() - t0) * 1000.0 / 1000.0

    return {
        "onnx_path": str(onnx_path),
        "max_abs_diff_vs_pytorch": max_diff,
        "single_step_latency_ms": round(dt_ms, 4),
        "model_size_kb": round(onnx_path.stat().st_size / 1024.0, 2),
    }
