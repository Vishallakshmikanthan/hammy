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

---

## Stage 2: Video to Reference Motion — **COMPLETE (Awaiting HUMAN CHECKPOINT 2)**

### What Was Done
- **Pose Estimation (`scripts/stage2_extract_poses.py`):** Ran DeepLabCut 3.0.2 `superanimal_quadruped` (`hrnet_w32`) on RTX 5070 across 3 usable clips (`video1_syrian_groom`, `video6_wheel_run`, `video7_platform_walk`), saving raw & cleaned 10-keypoint CSVs (`data/keypoints/*_raw.csv`, `*_clean.csv`).
- **Cleaning & Gait Statistics (`scripts/stage2_clean_retarget_and_render.py`):** Dropped low-confidence keypoints (`p < 0.35`), interpolated gaps (`<= 12` frames), Savitzky-Golay smoothed, normalized body scale, and computed real-video wheel gait & stop-start statistics in [`data/reference_motion/gait_statistics.json`](data/reference_motion/gait_statistics.json).
- **Retargeting & Unified Drop-In Library (`training/reference_library.py`):**
  - Saved 2 `REAL_VIDEO` retargeted clips (`real_video1_groom_REAL.npz`, `real_video6_wheel_run_REAL.npz`).
  - Generated 5 explicitly marked `SYNTHETIC` (`ANIMATION-DRIVEN`) procedural flat-ground locomotion clips (`walk_slow_SYNTHETIC.npz`, `trot_medium_SYNTHETIC.npz`, `turn_left_SYNTHETIC.npz`, `turn_right_SYNTHETIC.npz`, `stop_start_SYNTHETIC.npz`) via `scripts/stage2_generate_synthetic_gaits.py`.
  - Built source-agnostic `ReferenceMotionLibrary` supporting `synthetic`, `real`, and `mixed` modes without changing Stage 3 training code.
- **Overlays & Tests:** Rendered 3 real-video keypoint overlay videos + 4 MuJoCo reference playback videos + 2 preview sheets in `renders/stage2/`, recorded [`docs/decisions/ADR-0003-stage2-pose-and-reference-motion.md`](docs/decisions/ADR-0003-stage2-pose-and-reference-motion.md), and passed all 3 Stage 2 acceptance tests in [`tests/test_stage2_reference_motion.py`](tests/test_stage2_reference_motion.py) (3/3 PASSED in 0.55 s).

### Key Metrics
| Clip / Metric | Raw Jitter (px/f²) | Clean Jitter (px/f²) | Keypoint Validity (`p>=0.35`) | Retarget Clip Err (rad) |
| :--- | :---: | :---: | :--- | :---: |
| `video1_syrian_groom` (`REAL_VIDEO`) | `15.92` | `5.02` (-68%) | nose `98%`, ears `99.7–100%`, fl/fr paw `91–99%` | `0.0004` |
| `video6_wheel_run` (`REAL_VIDEO`) | `24.42` | `13.22` (-46%) | nose `100%`, neck `100%`, fl/bl paw `78–80%` | `0.0112` |
| `video7_platform_walk` (`REAL_VIDEO`) | `32.75` | `13.17` (-60%) | nose `85.5%`, ears `76–86%`, paws `58–68%` | N/A (oblique) |

- **Real-video wheel gait (`video6`, scaled to `0.145 m` Syrian length):** stride freq `2.09 Hz` (`0.479 s` period), paw excursion `0.432` body lengths → scaled stride length `0.0627 m`, scaled speed `0.131 m/s`.
- **Real-video stop-start (`video7`, oblique handheld):** moving fraction `0.855`, `39` transitions, mean move bout `0.86 s`, mean stop bout `0.14 s`.

### Exact Next Step
**STOP AT HUMAN CHECKPOINT 2:** Wait for user review of the keypoint overlay videos and MuJoCo reference renders in `renders/stage2/` before starting Stage 3 (Locomotion RL with imitation + curriculum + ablation + ONNX export).

---

## Stage 3: Locomotion RL with Imitation — **COMPLETE (Awaiting HUMAN CHECKPOINT 3)**

### What Was Done
- Built 50 Hz MuJoCo Gymnasium env ([`training/hamster_locomotion_env.py`](training/hamster_locomotion_env.py)) using versioned 64-dim obs / 16-dim action contracts, 8 separately logged reward terms, 6-stage success-gated curriculum (`stand → perturb → walk → turn → stop → target`), plausible domain randomization (`±12%` mass, `±25%` friction, `±15%` actuator gain, sensor noise, `0–20 ms` control delay), and DeepMimic RSI.
- Benchmarked 64 parallel envs on RTX 5070 ([`training/runs/stage3/bench_64envs.json`](training/runs/stage3/bench_64envs.json)): `64 DummyVecEnv` achieved `2,855.4` PPO train steps/s at `18.07 MB` peak GPU VRAM.
- Ran full 4-way PPO ablation (`500,000` steps each, `64` envs, `seed=42`) and 100-episode standardized evaluation ([`training/runs/stage3/ablation_report.json`](training/runs/stage3/ablation_report.json)).
- Exported best policy (`imitation_mixed`) to [`training/runs/stage3/best_policy.onnx`](training/runs/stage3/best_policy.onnx) with baked `VecNormalize` (`max_abs_diff = 1.07e-6`, latency `0.0132 ms`, size `340.85 KB`).
- Rendered policy walk, turn, and stop-start videos in `renders/stage3/`, wrote [`docs/decisions/ADR-0004-stage3-locomotion-rl-ablation.md`](docs/decisions/ADR-0004-stage3-locomotion-rl-ablation.md), and passed **3/3** Stage 3 acceptance tests in [`tests/test_stage3_locomotion.py`](tests/test_stage3_locomotion.py) (`0.44 s`).

### 4-Way Ablation Metrics (100 Randomized Episodes Each)
| Condition | Honesty Label | Non-Fall (%) | Speed Err (m/s) | Walk Dist 5 s (m) | Joint RMSE (rad) | Stop Settle (s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`imitation_mixed`** (Best) | `LEARNED` (MIXED real+synthetic) | **`100.0%`** | **`0.0741`** | `0.617` | `0.2495` | `0.357` |
| `imitation_synthetic` | `LEARNED` (SYNTHETIC ref) | `100.0%` | `0.0809` | `0.623` | **`0.2224`** | `0.232` |
| `imitation_real` | `LEARNED` (REAL_VIDEO wheel/groom) | `100.0%` | `0.0793` | `0.386` | `0.2979` | **`0.166`** |
| `no_imitation` | `LEARNED` (pure RL baseline) | `100.0%` | `0.0816` | `0.676` | `0.2864` | `0.478` |

### Exact Next Step
**STOP AT HUMAN CHECKPOINT 3:** Wait for user review of `renders/stage3/policy_walk_speeds.mp4`, `renders/stage3/policy_turn_left_right.mp4`, `renders/stage3/policy_stop_start.mp4`, and `renders/stage3/stage3_policy_preview.png`.

---

## Stage 4: Habitat Interaction, Autonomous Behaviours & Petting/Taming — **COMPLETE (Awaiting HUMAN CHECKPOINT 4)**

### What Was Done
- Built single-source MuJoCo habitat scene builder via `mujoco.MjSpec` ([`simulation/habitat_objects.py`](simulation/habitat_objects.py), `habitat_mujoco_v1.0.0`) attaching enclosure walls and 6 interactive props (`prop_bowl_main`, `prop_bottle_main`, `prop_hideout_main`, `prop_tunnel_main`, `prop_wheel_main`, `prop_treat_zone`) directly onto `hamster_mjcf_v1.0.0`.
- Built internal drive engine, transparent `RULE-BASED` autonomous skill selector, and non-forced petting/taming state machine ([`ai/behaviour_manager.py`](ai/behaviour_manager.py)).
- Built closed-loop ONNX habitat skill executor ([`simulation/habitat_skill_controller.py`](simulation/habitat_skill_controller.py)) validating `best_policy.onnx` contract compatibility and applying yaw-invariant tilt observations + gentle `RULE-BASED` heading steering assist.
- Evaluated 12 physical MuJoCo episodes (6 continuous autonomous skills + 6 petting/taming interactions) via [`scripts/stage4_eval_and_render.py`](scripts/stage4_eval_and_render.py), logged grounded events to `training/runs/stage4/events.jsonl`, rendered 2 videos + preview in `renders/stage4/`, recorded [`docs/decisions/ADR-0005-stage4-habitat-behaviours-and-petting.md`](docs/decisions/ADR-0005-stage4-habitat-behaviours-and-petting.md), and passed **4/4** tests in [`tests/test_stage4_habitat_behaviour.py`](tests/test_stage4_habitat_behaviour.py) (`0.42 s`).

### Key Metrics
| Metric | Measured Value | Target | Status |
| :--- | :---: | :---: | :---: |
| Total physical skill executions | `12` (6 autonomous + 6 petting) | — | PASS |
| Task completion rate | **`100.0%`** (`12/12`) | `>= 80%` | PASS |
| Fall rate | **`0.0%`** (`0/12`) | `0%` | PASS |
| Taming response curve | `avoid_and_retreat (×2) → cautious_sniff (×2) → accept_petting (×2)` | Non-forced progression | PASS |
| Familiarity / Stress curve | Familiarity `0.05 → 0.78`, Stress `0.45 → 0.03` | Bounded `[0, 1]` | PASS |

### Exact Next Step
**STOP AT HUMAN CHECKPOINT 4:** Wait for user review of `renders/stage4/stage4_autonomous_habitat.mp4`, `renders/stage4/stage4_petting_taming.mp4`, and `renders/stage4/stage4_habitat_preview.png`. Next stage after approval: bridging the trained ONNX policy & behaviour stream into the existing realistic 3D web habitat (`hamster.glb` + FastAPI backend).

---

## Stage 5: MuJoCo + ONNX Bridge to Photorealistic Web Habitat — **COMPLETE (21/21 Total Tests Passing)**

### What Was Done
- Extended [`contracts/schemas.py`](contracts/schemas.py) (`SUPPORTED_SCHEMA_VERSIONS` + `TrajectoryKeyframeV1.joint_angles` up to 16 DoF, backward-compatible).
- Built real MuJoCo + ONNX `TrajectoryClipV1` exporter ([`services/simulation_worker/mujoco_clip_generator.py`](services/simulation_worker/mujoco_clip_generator.py)) and exported 6 verified `observed_physics` / `learned` clips via [`scripts/stage5_export_web_clips.py`](scripts/stage5_export_web_clips.py) to both `LocalObjectStorage` and `web/public/assets/mujoco_clips/` (`forage_bowl`, `drink_water`, `enter_tunnel`, `retreat_to_hideout`, `cautious_sniff`, `accept_petting`) without modifying `hamster.glb`.
- Added FastAPI bridge router ([`services/api/routes/mujoco_bridge.py`](services/api/routes/mujoco_bridge.py)) mounted in [`services/api/main.py`](services/api/main.py) (`/api/v1/mujoco/status`, `/api/v1/mujoco/interact`, `/api/v1/mujoco/clips/{clip_id}`).
- Recorded [`docs/decisions/ADR-0006-stage5-mujoco-onnx-web-bridge.md`](docs/decisions/ADR-0006-stage5-mujoco-onnx-web-bridge.md) and passed full Stage 0–5 regression suite (**19/19** Docker GPU tests + **2/2** Stage 5 web bridge tests = **21/21 PASSED**).

### Exact Next Step
Ready for either: (a) dropping real flat-ground walking videos into `data/raw_video/` to re-run Stage 2/3 and compare `real-only` vs `synthetic-only` vs `mixed`, or (b) wiring a dedicated Petting / Offer Treat button in `web/` UI to `POST /api/v1/mujoco/interact` and previewing live in the browser.





