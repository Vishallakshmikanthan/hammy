# ADR-0003: Stage 2 Pose Estimation, Retargeting, and Drop-In `REAL_VIDEO` + `SYNTHETIC` Reference Library

**Date:** 2026-11-19  
**Status:** Accepted  

## Context
Stage 2 extracts 2D keypoints from usable real hamster videos, cleans and segments them into gait statistics, retargets them to `hamster_mjcf_v1.0.0`, and supplies flat-ground locomotion reference clips for Stage 3 PPO imitation training.

## Key Decisions
1. **Pose Estimator Selection:**
   - Used **DeepLabCut 3.0.2 PyTorch SuperAnimal** (`superanimal_quadruped`, `hrnet_w32` + `fasterrcnn_resnet50_fpn_v2`) on RTX 5070 CUDA 12.8 across all 3 usable clips (`video1_syrian_groom`, `video6_wheel_run`, `video7_platform_walk`).
   - Tested `superanimal_topviewmouse` on `video7_platform_walk` first; it failed detection (`0.2%` valid) because `video7` is an oblique 3/4 view rather than a top-down lab arena. Switching to `superanimal_quadruped` (`bbox_threshold=0.25`) raised paw validity to `57.8–68.3%` and nose/ear validity to `76.2–86.2%`.
2. **2D Single-Camera Retargeting Boundaries (Measured vs. Estimated):**
   - **Measured from 2D video:** Sagittal `spine_pitch`, `neck_pitch`, fore-aft paw excursion (`hip_pitch`), and vertical paw lift (`knee_pitch` + ground contact indicator).
   - **Estimated / constrained (unobservable from single side camera):** Lateral abduction (`*_hip_abd = 0`), `spine_yaw = 0`, `neck_yaw = 0`; all joint angles strictly clamped to `hamster_mjcf_v1.0.0` limits.
3. **Explicit `SYNTHETIC` Fallback & Source-Agnostic Drop-In Architecture (`training/reference_library.py`):**
   - Because no unoccluded flat-ground Syrian hamster walking video is present yet, we generated 5 explicitly tagged `SYNTHETIC` procedural locomotion clips (`walk_slow_SYNTHETIC.npz`, `trot_medium_SYNTHETIC.npz`, `turn_left_SYNTHETIC.npz`, `turn_right_SYNTHETIC.npz`, `stop_start_SYNTHETIC.npz`) alongside 2 `REAL_VIDEO` retargeted clips (`real_video1_groom_REAL.npz`, `real_video6_wheel_run_REAL.npz`).
   - `ReferenceMotionLibrary` loads clips strictly by schema (`reference_clip_v1.0.0`) and `source_filter` (`"synthetic"`, `"real"`, `"mixed"`). Dropping new real-video `.npz` clips into `data/reference_motion/` requires **zero changes** to Stage 3 training code and enables separate synthetic-only, real-only, and mixed ablation reporting.
