# HAMSTER Training Pipeline — Progress Log

## Stage 0: Audit and Setup — **COMPLETE (Acceptance Passed)**

### Status by Sub-step
- **0a. Raw video audit:** **COMPLETE**
  - Audited all 8 clips in `data/raw_video/` (mirrored from `reference/video/`).
  - Saved 3×3 contact sheets in `data/audit_frames/` and documented full ranking in [`data/video_audit.md`](data/video_audit.md).
  - **Usable (4):** `hamster-video6.mp4` (1080p side-profile wheel running, real-time + slow-mo), `hamster-video1.mp4` (Syrian hamster fixed side-profile crouch/groom), `hamster-video7.mp4` (1080p rearing/oblique walk/turn/stop-start), `hamster-video8.mp4` (1080p Syrian montage).
  - **Rejected (4):** `hamster-video2.mp4`, `hamster-video3.mp4`, `hamster-video4.mp4`, `hamster-video5.mp4` (occluded in box/jar/cup/bedding, stationary).
- **0b. GPU & driver check:** **COMPLETE**
  - Verified `NVIDIA GeForce RTX 5070 Laptop GPU` (8,151 MiB VRAM, compute capability `(12, 0)` Blackwell `sm_120`, Driver `592.01`, CUDA `13.1`).
  - Verified `PyTorch 2.11.0+cu128` executes CUDA forward + autograd backward kernels cleanly inside Docker (`hamster-train:cu128`).
- **0c. Project structure:** **COMPLETE**
  - Created/verified `simulation/`, `training/`, `scripts/`, `contracts/`, `docs/decisions/`, `tests/`, `data/`, `docker/`.
- **0d. Tool installation:** **COMPLETE**
  - Built pinned Docker image `hamster-train:cu128` ([`docker/Dockerfile.training`](docker/Dockerfile.training), [`docker/requirements-training.txt`](docker/requirements-training.txt)):
    - `mujoco==3.3.2` (with EGL headless rendering), `gymnasium==1.1.1`, `stable-baselines3==2.6.0`, `torch==2.11.0+cu128`, `onnx==1.17.0`, `onnxruntime==1.21.1`, `onnxscript==0.7.2`, `deeplabcut==3.0.2` (PyTorch backend + SuperAnimal).
- **0e. `pollen-robotics/microduck_rl` study:** **COMPLETE**
  - Verified **Apache-2.0** code license; documented adopted patterns in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and [`docs/decisions/ADR-0001-stage0-environment-and-pipeline.md`](docs/decisions/ADR-0001-stage0-environment-and-pipeline.md). Zero code copied.
- **0f. Smoke tests:** **COMPLETE (5/5 PASSED in 6.17 s)**
  - [`tests/test_stage0_smoke.py`](tests/test_stage0_smoke.py): MuJoCo load/step/EGL render, RTX 5070 `sm_120` CUDA forward+backward, Gymnasium + SB3 PPO train/save/reload determinism, ONNX export + ORT match, DeepLabCut SuperAnimal import.

### Exact Next Step
Proceed to **Stage 1: Hamster body model (MJCF)** — build versioned 16-DoF `simulation/models/hamster/hamster.xml` + versioned observation/action contracts in `contracts/` + physics stability tests + rendered 10 s standing video, then stop at **HUMAN CHECKPOINT 1**.
