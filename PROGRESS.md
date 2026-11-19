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

---

## Stage 2b + 3b + 5b: Real Flat-Ground Video Upgrade, 1M-Step Smoothness Refinement & UI Wiring — **COMPLETE**

### What Was Done
- **13 New Videos Audited (`21` total in `data/raw_video/`):** Extracted DeepLabCut 3.0.2 SuperAnimal poses, real flat-ground gait statistics, and 4 additional `REAL_VIDEO` MJCF reference clips (`real_grass_walk_sniff_REAL.npz`, `real_flat_mat_eat_walk_REAL.npz`, `real_rear_sniff_enclosure_REAL.npz`, `real_hand_taming_walk_REAL.npz`, now **6 `REAL_VIDEO` + 5 `SYNTHETIC`** clips in `data/reference_motion/`) via [`scripts/stage2b_extract_new_real_videos.py`](scripts/stage2b_extract_new_real_videos.py).
- **1M-Step High-Smoothness PPO Refinement:** Upgraded [`training/hamster_locomotion_env.py`](training/hamster_locomotion_env.py) with native yaw-invariant tilt observations, 2nd-order action jerk + anti-chatter paw cadence penalties, and stronger yaw tracking; trained all 4 ablation conditions for `1,000,000` steps each (`64` envs on RTX 5070):
  - `imitation_real` (purely from 6 `REAL_VIDEO` clips): **`98.0%` non-fall**, **lowest speed error (`0.0989 m/s`)**.
  - `imitation_mixed` (6 `REAL_VIDEO` + 5 `SYNTHETIC`, exported to `best_policy.onnx`): **`98.0%` non-fall**, **`0.114 m/s`** speed error, **`0.673 m`** walk distance, ONNX diff **`1.16e-6`**, latency **`0.0126 ms`**.
  - Re-ran Stage 4 habitat eval (**`100.0%` success**, **`0.0%` falls**) and refreshed all 6 Stage 5 MuJoCo + ONNX web clips.
- **UI Wiring (`web/`):** Built [`web/src/components/ParentInteractionPanel.tsx`](web/src/components/ParentInteractionPanel.tsx) (Offer Treat / Gentle Pet / Call Attention, live Familiarity & Stress meters, non-forced response badge, honesty labels, MuJoCo clip link) and mounted it in [`web/src/components/Observatory.tsx`](web/src/components/Observatory.tsx). Verified `tsc && vite build` (`2.96 s`, 0 errors) and all regression tests (**10/10** Docker + **2/2** Stage 5 bridge tests passing).

---

## Stage 5c: Live Browser Realism Calibration & Wheel Visibility — **COMPLETE**

### What Was Done
- **Real-Video Speed & Behaviour Calibration (`604dff4`):** Audited user screen recording (`data/audit_frames/screen_recording_check.jpg`) and calibrated `web/src/three/habitat/hamsterBehavior.ts` & `web/src/three/rig/poseApplication.ts` directly to measured real-video statistics (`0.085–0.115 m/s` walk, `2.3 rad/s` turn, speed-locked `0.055 m` stride cadence, `2.09 Hz` wheel cadence, calm `10.5–15.0 rad/s` groom/chew/dig, `2.0–7.0 s` calm bouts).
- **Center Log-Tunnel Clearance & Wheel Visits (`1c0aa0b`):** Tightened obstacle padding (`0.036 → 0.022 m`), widened front/back BFS corridor waypoints, increased cross-cage timeouts (`14–16 s`), and widened wheel-entry tolerance so Hammy reliably navigates around the log and runs on the wheel.
- **Visible Wheel Rotation (`8cdc850`):** Added 12 wooden inner grip rungs + 3 back-wall spokes as children of `prop_wheel_drum` in `web/src/three/habitat/HabitatSceneView.tsx` so drum spin and coasting rock are clearly visible.
- **Documentation:** Updated `data/video_audit.md` for all 21 videos and recorded [`docs/decisions/ADR-0007-real-video-refinement-and-web-calibration.md`](docs/decisions/ADR-0007-real-video-refinement-and-web-calibration.md).

---

## Asset Integration Pipeline — Step 1 (Audit) & Step 2 (Gap Analysis) — **COMPLETE (Awaiting HUMAN CHECKPOINT 1)**

### What Was Done
- **Step 1 — Unpack & Audit (`scripts/step1_audit_raw_assets.py`, `scripts/step1_write_audit_docs.py`):**
  - Copied all 4 downloaded archives from `props/` into `assets/raw/` and unpacked **2,766 files** representing **524 unique 3D models** and **255 texture/preview `.png` files**:
    1. `kenney_food-kit.zip` (`200` models in `.glb`, `.fbx`, `.obj/.mtl` + `512×512` `colormap.png` + `200` preview `.png`s) — **CC0 1.0 Universal** (`License.txt` verified, author: **Kenney**, `https://kenney.nl/assets/food-kit`) → **APPROVED**.
    2. `KayKit_Dungeon_Pack_1.1_FREE.zip` (`211` models in `.gltf/.bin`, `.fbx`, `.obj/.mtl` + `1024×1024` `dungeon_texture.png`) — **CC0 1.0 Universal** (`License.txt` verified, author: **Kay Lousberg**, `https://kaylousberg.itch.io/kaykit-dungeon`) → **APPROVED**.
    3. `drive-download-20261119T082111Z-1-001.zip` (`103` models in `.blend`, `.fbx`, `.obj/.mtl`) — **NO LICENSE / README** in archive, and missing external referenced texture `//Blender/DavidThorn/Library/Large/Texture.png` → **REJECTED** (Rule: *Never use an asset with an unclear licence*).
    4. `Food&DrinksPack.rar` (`10` `.fbx` models + `28` `.png` textures) — **NO LICENSE / README** in archive, and 100% processed human junk food/drinks (`CannedFood`, `Canned_Tuna`, `CoffeeCup`, `FrozenPizza`, `Hamburger`, `HotDog`, `Ice_Cream`, `Milk`, `Pizza`, `Sushi`) → **REJECTED**.
  - Checked every food asset against veterinary Syrian hamster safety standards (RSPCA, PDSA, Merck Veterinary Manual, California Hamster Association) and excluded toxic/doubtful items (avocado/persin, citrus, alliums/onion/leek, sticky peanut butter jar, nightshades, chocolate/sweets, processed fast food, dairy, alcohol/caffeine).
  - Wrote full per-file audit and gap report in [`assets/ASSET_AUDIT.md`](assets/ASSET_AUDIT.md), license registry in [`ASSETS_LICENSES.md`](ASSETS_LICENSES.md), and attribution registry in [`CREDITS.md`](CREDITS.md) (plus structured metrics in `assets/audit_data.json`).
- **Step 2 — Gap Analysis Summary:**
  - **Foods (7 required, hamster-safe only):** `broccoli` (`kenney_food-kit`, CC0) and `carrot` (`kenney_food-kit`, CC0) are present (`DOWNLOADED`, need rescaling from `~0.16–0.19 m` human scale to `0.014–0.018 m` hamster piece scale + paw pickup pivot). **Gaps to generate in Blender (Step 3):** `food_seed_mix`, `food_sunflower_seed`, `food_peanut` (Kenney only has a peanut-butter jar, which is unsafe for cheek pouches), `food_apple_piece` (seedless slice; Kenney whole/half apples have exposed seeds), and `food_blueberry`.
  - **Water & Containers (4 required):** `prop_food_bowl` (`kenney_food-kit/bowl.glb`, CC0) and `prop_shelf` (`KayKit/shelf_small.gltf`, CC0) are present (`DOWNLOADED`, need rescaling to hamster dimensions). **Gaps to generate in Blender (Step 3):** `water_bottle` with a separate scalable `water_liquid` mesh, and `water_bowl` with a separate scalable `water_liquid` mesh.
  - **Costumes (6 required + 1 back-slot item = 7 total):** **100% GAP** (`0` costumes in `assets/raw/`). All 7 (`costume_party_hat`, `costume_top_hat`, `costume_bow_tie`, `costume_scarf`, `costume_crown`, `costume_tiny_glasses`, plus `costume_backpack` so `head_slot`, `neck_slot`, and `back_slot` are all testable) will be generated in Step 3 at Syrian hamster scale with named attachment sockets.
  - **Props (7 required):** `prop_wheel`, `prop_tunnel_straight`, `prop_tunnel_curved`, and `prop_hideout` exist in our procedural `blender/scripts/10_cage.py` scene and will be exported as standalone base-center-pivoted `.blend`/`.glb` assets; **new gaps to generate in Step 3:** `prop_bridge_ramp` (arched bendy log bridge), `prop_chew_toy` (gnawed applewood dumbbell chew), and `prop_small_ball` (woven willow play ball).
  - **Decor (5 required):** `decor_wooden_item` (`KayKit/barrel_small.gltf`, CC0) and `decor_flag` (`KayKit/banner_blue.gltf`, CC0) are present (`DOWNLOADED`, need rescaling to hamster cage scale). **Gaps to generate in Blender (Step 3):** `decor_plant` (hamster-safe potted spider plant), `decor_bedding_patch` (organic aspen/paper/moss patch), and `decor_picture_frame` (mini wooden standing frame).

### Exact Next Step
**STOP AT HUMAN CHECKPOINT 1 (After Step 2):** Present the audit ([`assets/ASSET_AUDIT.md`](assets/ASSET_AUDIT.md), [`ASSETS_LICENSES.md`](ASSETS_LICENSES.md), [`CREDITS.md`](CREDITS.md)) and gap analysis to the user and wait for approval before proceeding to **Step 3 (Generate missing assets in headless Blender 5.2)**, **Step 4 (Convert, optimize & generate thumbnails + `assets/manifest.json`)**, and **Step 5 (Eating animation clip set & HUMAN CHECKPOINT 2)**.

---

## Asset Integration Pipeline — Step 3 (Blender Asset Generation), Step 4 (Conversion, Optimization & Manifest) & Step 5 (Eating Animation) — **COMPLETE (Awaiting HUMAN CHECKPOINT 2)**

### What Was Done
- **Step 3 — Generate Missing Assets in Headless Blender 5.2.3 LTS (`scripts/step3_step4_build_and_optimize_assets.py`):**
  - Built 24 missing low-poly, metric hamster-scale (`0.15 m` Syrian hamster reference) 3D models in `assets/source/*.blend` and adapted 6 approved CC0 models from `kenney_food-kit.zip` and `KayKit_Dungeon_Pack_1.1_FREE.zip` (**30 total assets**):
    - **7 Hamster-Safe Foods (`food_*`, pickup pivot at `pickup_pivot`):** `food_seed_mix` (`GENERATED`, `324` tris), `food_sunflower_seed` (`GENERATED`, `288` tris), `food_peanut` (`GENERATED`, `600` tris), `food_carrot_piece` (`DOWNLOADED` Kenney CC0 rescaled to `0.022 m`, `148` tris), `food_broccoli_floret` (`DOWNLOADED` Kenney CC0 rescaled to `0.019 m`, `220` tris), `food_apple_piece` (`GENERATED` seedless slice, `52` tris), `food_blueberry` (`GENERATED`, `520` tris).
    - **2 Water Sources (`water_*`, with separate scalable `water_liquid` mesh):** `water_bottle` (`GENERATED`, `536` tris, `0.16 m` body + angled steel ball-spout + separate `water_liquid` cylinder pivoted at bottom for `0..1` water level scaling) and `water_bowl` (`GENERATED`, `360` tris, `0.068 m` ceramic dish + separate `water_liquid` mesh).
    - **7 Costumes (`costume_*`, with named attachment sockets `head_slot`, `neck_slot`, `back_slot`):** `costume_party_hat` (`head_slot`, `728` tris), `costume_top_hat` (`head_slot`, `324` tris), `costume_bow_tie` (`neck_slot`, `372` tris), `costume_scarf` (`neck_slot`, `780` tris), `costume_crown` (`head_slot`, `860` tris), `costume_tiny_glasses` (`head_slot`, `876` tris), and `costume_backpack` (`back_slot`, `200` tris).
    - **9 Props (`prop_*`, base-center pivot `Z=0`, all `< 2,500` tris):** `prop_food_bowl` (`DOWNLOADED` Kenney CC0 rescaled to `0.082 m`, `84` tris), `prop_shelf` (`DOWNLOADED` KayKit CC0 rescaled to `0.18 m`, `60` tris), `prop_wheel` (`GENERATED`, `0.28 m` wheel with 12 grip rungs, `816` tris), `prop_tunnel_straight` (`GENERATED`, `224` tris), `prop_tunnel_curved` (`GENERATED`, `1,632` tris), `prop_hideout` (`GENERATED`, `84` tris), `prop_bridge_ramp` (`GENERATED` 11-log bendy arch bridge, `572` tris), `prop_chew_toy` (`GENERATED` applewood dumbbell chew, `212` tris), `prop_small_ball` (`GENERATED` woven willow play ball, `2,304` tris).
    - **5 Cage Decor Items (`decor_*`, base-center pivot `Z=0`, all `< 600` tris):** `decor_plant` (`GENERATED` terracotta spider plant, `232` tris), `decor_wooden_item` (`DOWNLOADED` KayKit CC0 mini climbing barrel rescaled to `0.062 m`, `207` tris), `decor_bedding_patch` (`GENERATED` moss/aspen mound, `528` tris), `decor_flag` (`DOWNLOADED` KayKit CC0 pennant banner rescaled to `0.115 m`, `97` tris), `decor_picture_frame` (`GENERATED` mini wooden portrait frame, `36` tris).
- **Step 4 — Convert, Optimize, Render Thumbnails & Build Manifest:**
  - Exported all 30 assets as Y-up `.glb` files (scale applied, materials merged, textures resized `<= 512px` for small items / `<= 1024px` for props) to both `assets/web/*.glb` and `web/public/assets/items/*.glb`.
  - Rendered 30 studio `256×256` transparent PNG thumbnails with Cycles OptiX to `assets/thumbnails/*.png` and `web/public/assets/thumbnails/*.png`.
  - Generated [`assets/manifest.json`](assets/manifest.json) (mirrored to `web/public/assets/manifest.json`) with `id`, `name`, `category`, `file_path`, `web_url`, `thumbnail`, `scale`, `dimensions_m`, `collision_radius_m`, `pivot`, `attachment_slot`, `hamster_safe`, `licence`, `source`, `origin_label` (`GENERATED` / `DOWNLOADED`), and `polygon_count` / `triangle_count`.
- **Step 5 — Eating Animation Clip Set & Cheek-Pouch Shape Keys (`scripts/step5_author_eating_animation.py`, `scripts/step5_encode_video_and_sheet.py`):**
  - Added 4 attachment socket bones directly to `HamsterRig` (`head_slot`, `neck_slot`, `back_slot`, `food_hold_socket`) and fixed orbital eye surface placement (`ham_eye_L/R`) in `blender/scripts/60_rig_and_export_glb.py`.
  - Authored all 7 required `ANIMATION-DRIVEN` NLA clips (`sit_up`, `grab_food`, `bring_to_mouth`, `chew_loop`, `swallow`, `stuff_cheek`, `release_idle`) plus the composite 192-frame `eat_full_sequence` action, calibrating posture and 4.8 Hz jaw/paw cadence to the real eating videos in `data/raw_video/`.
  - Keyframed `cheek_pouch_left` and `cheek_pouch_right` shape keys (`0.0 → 0.98`) across the 3 LOD meshes (`ham_body_LOD0/1/2`) and exported the updated `web/public/assets/hamster.glb` (`966 KB`).
  - Rendered the 7-stage contact sheet (`renders/step5/eating_sequence_contact_sheet.png`) and full sequence review video (`renders/step5/eating_animation_sequence.mp4`).

### Exact Next Step
**STOP AT HUMAN CHECKPOINT 2 (After Step 5):** Present the eating animation render (`renders/step5/eating_animation_sequence.mp4` and `renders/step5/eating_sequence_contact_sheet.png`) and `assets/manifest.json` summary to the user and wait for approval before proceeding to **Step 6 (Shelf-based opt-in backend & frontend integration, collision/navigation updates, command tests & live browser screen recording)** and **Step 7 (Performance & quality check)**.

---

## Asset Integration Pipeline — Step 6 (Shelf-Based Opt-In Integration) & Step 7 (Performance & Quality Check) — **COMPLETE (Awaiting HUMAN CHECKPOINT 3)**

### What Was Done
- **Step 6 — Server-Authoritative Shelf Commands & Layout Persistence (`services/commands/handler.py`, `services/api/routes/shelves.py`, `services/api/main.py`):**
  - Implemented 10 idempotent, server-authoritative shelf commands (`offer_food`, `refill_water`, `equip_costume`, `unequip_costume`, `place_prop`, `move_prop`, `remove_prop`, `consume_food`, `consume_water`, `reset_clean_cage`) validated against `assets/manifest.json`, `hamster_safe` food flags, cage bounds (`[-0.44, 0.44] × [-0.19, 0.19] m`), and prop collision radii.
  - Added server-side food spoilage rule (`SPOILAGE_SIM_SEC = 600.0` seconds) and logged every `offer_food`, `refill_water`, `equip_costume`, `unequip_costume`, `place_prop`, `move_prop`, `remove_prop`, `eat`, and `drink` action as a `WorldEvent` and `CareAction`.
  - Enforced the **Core Default 3D Habitat + Opt-In Shelves** rule: the default habitat always includes the **Hamster, Home (`prop_hideout`), Logs (`prop_tunnel_*`), Food Bowl (`prop_bowl`), Water Tank (`prop_bottle_*` with scalable `water_liquid` cylinder), and Running Wheel (`prop_wheel_*`)**, while extra chew blocks/sticks, costumes, offered foods, and extra placed props/decor are strictly opt-in via the 5 shelves.
- **Step 6 — Frontend 5 Separate Opt-In Shelves, Lazy-Loading & Collision/Navigation (`web/src/components/AssetShelfDrawer.tsx`, `web/src/three/habitat/HabitatSceneView.tsx`, `web/src/three/habitat/hamsterBehavior.ts`):**
  - Built 5 separate closed-by-default shelf drawers (`1. Food Shelf`, `2. Water Shelf`, `3. Costume Shelf`, `4. Props Shelf`, `5. Decor Shelf`), each with search, `Browse` vs. `In cage now` tabs, portion quantity selector (`1x..5x`), costume slot controls (`head_slot`, `neck_slot`, `back_slot` + `Unequip All`), interactive placement mode (X/Y sliders + 45° rotation + bounds/overlap validation + `Send to Shelf`), and `Reset Clean Cage`.
  - Implemented strict lazy-loading and GPU memory disposal: 256×256 thumbnails load only when a shelf drawer is opened; 3D `.glb` models load only when equipped/placed in the cage and are explicitly disposed (`geometry.dispose()`, `material.dispose()`) when removed.
  - Wired dynamic obstacle collision & navigation updates in `HamsterBehaviorController` so placed props update `dynamicObstacles` and the hamster walks around them cleanly, approaches offered food, sits up holding the food mesh on `food_hold_socket` (`Eating with Both Paws (ANIMATION-DRIVEN)`), and triggers server-authoritative `consume_food` (bulging `cheek_pouch_left/right` morphs) and `consume_water`.
- **Step 6 & Step 7 Automated Verification & Live Browser Screen Recording:**
  - **Backend Pytest Suite:** `python -m pytest tests/test_step6_shelf_commands.py tests/test_p2_3.py -v` -> **21/21 PASSED** (covering manifest safety, clean default cage, idempotent duplicate delivery, out-of-bounds & overlapping placement rejection, costume slot replacement/unequip, server-authoritative eating/drinking, and layout persistence).
  - **Frontend Vitest & TypeScript Production Build:** `npm --prefix web test -- --run` -> **18/18 PASSED across 5 test files** (including `AssetShelfDrawer.test.tsx` and `phase3.test.ts`); `npm --prefix web run build` -> **0 TypeScript errors**.
  - **Live Acceptance Screen Recording & Step 7 Telemetry (`scripts/step6_record_acceptance_and_perf.py`):**
    - Recorded [`renders/step6/step6_acceptance_recording.mp4`](renders/step6/step6_acceptance_recording.mp4) and [`renders/step6/step6_acceptance_contact_sheet.png`](renders/step6/step6_acceptance_contact_sheet.png) showing:
      1. Fresh load -> clean minimal cage (`0 props`, bedding + 1 basic water bottle, all 5 shelves closed).
      2. Open `1. Food Shelf` -> choose `Fresh Carrot Piece` -> Offer -> hamster approaches and eats with both front paws (`Eating with Both Paws (ANIMATION-DRIVEN)`), cheek pouches bulge (`0% -> 35%`).
      3. Open `2. Water Shelf` -> click `Refill Water (100%)` -> visible `water_liquid` scales to `100%`.
      4. Open `3. Costume Shelf` -> equip `Festive Party Hat` on `head_slot` -> visible on hamster's head -> unequip.
      5. Open `4. Props Shelf` -> select `Straight Hollow Bark Tunnel` -> rotate 45° & confirm placement -> tunnel lazy-loads into cage -> reload page -> layout persists (`Clean Opt-In Habitat (1 props)`) -> open `In cage now` tab -> `Send to Shelf` removes and unloads tunnel (`0 props`).
    - Authored [`docs/research/step7_asset_performance_report.md`](docs/research/step7_asset_performance_report.md) with desktop (`1280×800`) and mid-range phone (`390×844`) benchmarks across Default Clean Cage (`46` calls, `54,986` tris, `60.0 FPS`), Lightly Decorated Cage (`65` calls, `56,110` tris, `60.0 FPS`), and Heavily Decorated Cage (`109` calls, `58,134` tris, `60.0 FPS`), plus an honest visual critique of what still looks fake.

### Exact Next Step
**STOP AT HUMAN CHECKPOINT 3 (After Step 6 & Step 7):** Present the acceptance screen recording ([`renders/step6/step6_acceptance_recording.mp4`](renders/step6/step6_acceptance_recording.mp4)), milestone contact sheet ([`renders/step6/step6_acceptance_contact_sheet.png`](renders/step6/step6_acceptance_contact_sheet.png)), test results, and Step 7 performance & honesty report ([`docs/research/step7_asset_performance_report.md`](docs/research/step7_asset_performance_report.md)) to the user for review.










