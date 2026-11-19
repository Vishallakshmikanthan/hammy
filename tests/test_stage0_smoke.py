"""Stage 0f smoke tests: MuJoCo, RTX 5070 CUDA, Gymnasium, SB3 PPO, checkpoint save/load, ONNX."""

from __future__ import annotations

import os
from pathlib import Path

import gymnasium as gym
import mujoco
import numpy as np
import onnxruntime as ort
import pytest
import torch
from stable_baselines3 import PPO


MINIMAL_MJCF = """
<mujoco model="stage0_smoke">
  <option timestep="0.002" gravity="0 0 -9.81"/>
  <worldbody>
    <light pos="0 0 2" dir="0 0 -1"/>
    <geom name="floor" type="plane" size="2 2 0.1" rgba="0.8 0.8 0.8 1"/>
    <body name="torso" pos="0 0 0.2">
      <freejoint/>
      <geom type="box" size="0.05 0.03 0.02" mass="0.12" rgba="0.8 0.5 0.2 1"/>
      <body name="leg" pos="0.03 0 -0.02">
        <joint name="hip" type="hinge" axis="0 1 0" range="-1.0 1.0" damping="0.01"/>
        <geom type="capsule" fromto="0 0 0 0 0 -0.04" size="0.006" mass="0.01"/>
      </body>
    </body>
  </worldbody>
  <actuator>
    <position name="hip_act" joint="hip" kp="0.5" ctrlrange="-1.0 1.0"/>
  </actuator>
</mujoco>
"""


def test_mujoco_load_step_and_render():
    model = mujoco.MjModel.from_xml_string(MINIMAL_MJCF)
    data = mujoco.MjData(model)
    mujoco.mj_resetData(model, data)

    for step in range(100):
        data.ctrl[0] = 0.2 * np.sin(step * 0.1)
        mujoco.mj_step(model, data)

    assert np.all(np.isfinite(data.qpos)), "Non-finite qpos detected"
    assert np.all(np.isfinite(data.qvel)), "Non-finite qvel detected"
    assert data.qpos[2] > 0.0, "Torso fell through floor"

    # Verify headless offscreen rendering works (EGL or OSMesa)
    renderer = mujoco.Renderer(model, height=120, width=160)
    renderer.update_scene(data)
    frame = renderer.render()
    renderer.close()
    assert frame.shape == (120, 160, 3)
    assert frame.dtype == np.uint8
    assert float(frame.std()) > 1.0, "Rendered frame appears blank"


def test_torch_cuda_blackwell_execution():
    assert torch.cuda.is_available(), "CUDA GPU is not visible to PyTorch"
    device = torch.device("cuda:0")
    name = torch.cuda.get_device_name(0)
    assert len(name) > 0

    # Execute actual CUDA kernel + autograd backward pass (verifies sm_120 kernels)
    x = torch.randn((128, 128), device=device, requires_grad=True)
    w = torch.randn((128, 128), device=device, requires_grad=True)
    y = (x @ w).relu().sum()
    y.backward()
    torch.cuda.synchronize()

    assert torch.isfinite(y).item()
    assert x.grad is not None and torch.all(torch.isfinite(x.grad)).item()


def test_gymnasium_ppo_checkpoint_save_load(tmp_path: Path):
    env = gym.make("Pendulum-v1")
    obs, info = env.reset(seed=42)
    assert obs.shape == (3,)
    next_obs, reward, terminated, truncated, info = env.step(env.action_space.sample())
    assert np.all(np.isfinite(next_obs))
    assert np.isfinite(reward)

    model = PPO(
        "MlpPolicy",
        env,
        n_steps=64,
        batch_size=32,
        n_epochs=2,
        seed=42,
        device="cuda",
        verbose=0,
    )
    model.learn(total_timesteps=128)

    ckpt_path = tmp_path / "ppo_smoke.zip"
    model.save(str(ckpt_path))
    assert ckpt_path.exists()

    loaded = PPO.load(str(ckpt_path), env=env, device="cuda")
    test_obs = np.array([0.5, -0.3, 0.1], dtype=np.float32)
    act_orig, _ = model.predict(test_obs, deterministic=True)
    act_loaded, _ = loaded.predict(test_obs, deterministic=True)
    np.testing.assert_allclose(act_orig, act_loaded, atol=1e-6)
    env.close()


def test_onnx_export_and_ort_smoke(tmp_path: Path):
    net = torch.nn.Sequential(
        torch.nn.Linear(8, 16),
        torch.nn.Tanh(),
        torch.nn.Linear(16, 4),
    ).eval()
    dummy = torch.randn(1, 8)
    onnx_path = tmp_path / "smoke.onnx"
    torch.onnx.export(
        net,
        dummy,
        str(onnx_path),
        input_names=["obs"],
        output_names=["action"],
        opset_version=17,
    )
    assert onnx_path.exists()

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    ort_out = sess.run(["action"], {"obs": dummy.numpy()})[0]
    with torch.no_grad():
        pt_out = net(dummy).numpy()
    np.testing.assert_allclose(pt_out, ort_out, atol=1e-5)


def test_deeplabcut_superanimal_import():
    import deeplabcut

    assert hasattr(deeplabcut, "__version__")
    assert callable(deeplabcut.video_inference_superanimal)

