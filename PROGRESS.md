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

---

## Stage 1: Hamster Body Model (MJCF) — **COMPLETE (Awaiting HUMAN CHECKPOINT 1)**

### What Was Done
- Built versioned 16-actuated-DoF (+ 1 passive tail DoF) Syrian hamster MJCF model in [`simulation/models/hamster/hamster.xml`](simulation/models/hamster/hamster.xml) (`hamster_mjcf_v1.0.0`) and metadata/uncertainty spec in [`simulation/models/hamster/model_spec.json`](simulation/models/hamster/model_spec.json).
- Separated visual (`group="2"`, `density="0"`, no contact) and collision (`group="3"`, capsules/spheres) geometry; added torque-limited position actuators (`forcerange`), 4 paw touch sensors, and pelvis IMU sensors (`framequat`, `gyro`, `velocimeter`).
- Defined versioned observation (`locomotion_obs_v1.0.0`, fixed 64-dim vector) and action (`locomotion_act_v1.0.0`, 16-dim joint targets + safety clamp) contracts in [`contracts/locomotion_contracts.py`](contracts/locomotion_contracts.py) and exported JSON schemas in `contracts/json_schema/`.
- Recorded morphology assumptions and decisions in [`docs/decisions/ADR-0002-hamster-mjcf-morphology.md`](docs/decisions/ADR-0002-hamster-mjcf-morphology.md).
- Wrote and passed all 4 acceptance tests in [`tests/test_stage1_mjcf.py`](tests/test_stage1_mjcf.py) (4/4 PASSED in 0.42 s).
- Rendered 10 s multi-angle standing video (`renders/stage1/hamster_stand_10s.mp4`), 4-view model sheet (`renders/stage1/hamster_model_4view.png`), and metrics log (`renders/stage1/standing_metrics.json`).

### Metrics (10 s Standing Test, `dt=0.002 s`, 5,000 steps)
| Metric | Value | Acceptance Target | Status |
| :--- | :---: | :---: | :---: |
| Total mass | `0.125 kg` | `0.100–0.140 kg` (Syrian) | PASS |
| Actuated DoF (+ passive) | `16 (+1 tail)` | `~16 (+ passive tail)` | PASS |
| NaN / Inf count | `0` | `0` | PASS |
| Pelvis height (min / max / final) | `47.07 / 49.46 / 49.45 mm` | Stable in `[30, 65] mm` | PASS |
| Max body tilt | `2.065 deg` | `< 12 deg` | PASS |
| Final XY drift (10 s) | `1.663 mm` | `< 15 mm` | PASS |
| Mean paw contact forces (FL/FR/BL/BR) | `0.396 / 0.396 / 0.217 / 0.217 N` | All > 0, sum = `1.226 N` | PASS |

### Problems Caught & Fixed
- Initial MJCF run flagged `total_mass = 0.563 kg` via automated mass test because `class="visual"` ellipsoids defaulted to `density="1000"`. Fixed with `density="0"` on `class="visual"`, yielding exact `0.125 kg`.

### Exact Next Step
**STOP AT HUMAN CHECKPOINT 1:** Wait for user approval of `renders/stage1/hamster_model_4view.png` and `renders/stage1/hamster_stand_10s.mp4` before starting Stage 2 (Video → Reference Motion + `SYNTHETIC` procedural gait fallback).

