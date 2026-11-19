# ADR-0001: Stage 0 Environment, Reference Architecture (`microduck_rl`), and Video-Only Pipeline Setup

**Date:** 2026-11-19  
**Status:** Accepted  

## Context
We are launching the HAMSTER video-to-locomotion RL training pipeline on a Windows laptop equipped with an **NVIDIA GeForce RTX 5070 Laptop GPU (8,151 MiB VRAM, Driver 592.01, CUDA 13.1)** and 32 GB RAM. Per `HAMSTER_Technical_Blueprint.md` (Section 4.2, Section 7, Section 9, Section 15, Section 22), we need:
1. Audited raw video inputs (`data/raw_video/`).
2. Verified MuJoCo + PyTorch CUDA (12.8+ for RTX 5070 Blackwell `sm_120`) + Gymnasium + PPO + pose estimation.
3. Architectural study of `pollen-robotics/microduck_rl` (with license compliance).

## Findings

### 1. GPU & Native Windows Runtime Blocker
- **GPU:** `NVIDIA GeForce RTX 5070 Laptop GPU` detected via `nvidia-smi` (Driver `592.01`, CUDA `13.1`, 8 GB VRAM).
- **Native Windows Blocker:** Windows Smart App Control (Application Control / WDAC) is active on this machine and blocks unsigned native Python extension binaries in user-writable virtual environments:
  - `.venv\Scripts\python.exe -c "import mujoco"` fails with:
    `ImportError: DLL load failed while importing _structs: An Application Control policy has blocked this file.`
  - Per prior repo log (`docs/decisions.md`), `torch.dll` is likewise blocked under native Windows Python.
- **Sanctioned Path Available:** `Docker 29.6.1` and `WSL2 (docker-desktop)` are already installed on this machine, though Docker Desktop is currently stopped (`npipe:////./pipe/dockerDesktopLinuxEngine` unavailable). Running a Linux CUDA 12.8+ container via Docker Desktop (`--gpus all`) or an Ubuntu WSL2 distro is the standard, supported path to run native MuJoCo + PyTorch CUDA (Blackwell `sm_120`) + DeepLabCut/SuperAnimal without modifying Windows security policies.

### 2. Study of `pollen-robotics/microduck_rl`
- **License:** **Apache License 2.0** for code (CAD/hardware models separately licensed under CC BY-SA-NC). Logged in `THIRD_PARTY_NOTICES.md`. Zero source code copied; patterns reimplemented cleanly for the quadrupedal Syrian hamster.
- **Key Architectural Patterns Adopted:**
  1. **Fixed, Versioned Observation Contract with Zero-Padding:** `microduck_rl` maintains a fixed-dimension observation vector across policies (48-dim proprioception + 13-dim command layout, zero-padding unused command slots) so policies can be hot-swapped safely. We will apply the same discipline in `contracts/` for our ~16-DoF hamster.
  2. **50 Hz Control Loop & Actuator Realism:** Policies run at 50 Hz with domain randomization over actuator strength, joint friction, mass, sensor noise, and control latency.
  3. **Baked Observation Normalization in ONNX Export:** `microduck_rl` bakes the running observation normalizer directly into the exported `policy.onnx` graph so inference runtimes never drift from training preprocessing. We will adopt this exact requirement in Stage 3 and verify PyTorch-vs-ONNX numerical equivalence.

### 3. Raw Video Audit (`data/video_audit.md`)
- All 5 clips in `reference/video/` were mirrored to `data/raw_video/` and audited via 3×3 contact sheets.
- **None** of the 5 clips contain walking, turning, rearing, or wheel-running locomotion. Only `hamster-video1.mp4` shows an unoccluded Syrian hamster on a fixed side-view camera (stationary grooming/crouching).
- Stage 2 will extract posture/proportion keypoints from `hamster-video1.mp4` and — unless walking footage is added — invoke the explicit Stage 2.7 `SYNTHETIC` procedural gait fallback for locomotion reference clips.

## Decision
1. **Do NOT bypass Windows Smart App Control** and **do NOT fake MuJoCo/CUDA smoke tests** with pure-NumPy stand-ins.
2. Execute all Stage 0–3 simulation, pose estimation, and RL training inside the pinned Docker image `hamster-train:cu128` (`docker/Dockerfile.training`, `docker/requirements-training.txt`) via Docker Desktop WSL2 with `--gpus all`:
   - **GPU:** `NVIDIA GeForce RTX 5070 Laptop GPU` (`sm_120` Blackwell, 8,151 MiB VRAM, Driver `592.01`).
   - **Core Stack:** `PyTorch 2.11.0+cu128` (CUDA 12.8), `MuJoCo 3.3.2` (EGL offscreen rendering), `Gymnasium 1.1.1`, `Stable-Baselines3 2.6.0`, `ONNX 1.17.0` + `ONNX Runtime 1.21.1` + `onnxscript`, `DeepLabCut 3.0.2` (PyTorch backend with pretrained SuperAnimal quadruped / top-view models).
3. **Reference Motion Architecture (Real + SYNTHETIC Drop-In):**
   - `data/raw_video/` now contains 8 clips (4 usable: `hamster-video6.mp4` 1080p wheel running, `hamster-video1.mp4` Syrian side-view crouch/groom, `hamster-video7.mp4` 1080p rearing/oblique walk/turn, `hamster-video8.mp4` 1080p Syrian behaviour montage; 4 rejected).
   - Because no unoccluded flat-ground Syrian walking clip is present yet, Stage 2 will extract real proportions & wheel/oblique gait stats where reliable AND generate explicitly marked `SYNTHETIC` procedural walk/trot/turn/stop reference clips (`*_SYNTHETIC.npz`, `source_type="SYNTHETIC"`).
   - All reference clips share a single versioned `.npz` schema so real flat-ground walking clips added later can replace or blend with `SYNTHETIC` clips without modifying Stage 3 training code.
4. Keep all contracts, MJCF models, data, tests, and experiment logs directly in the workspace (`simulation/`, `training/`, `contracts/`, `data/`, `docs/`, `tests/`).
