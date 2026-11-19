# ADR-0007: Real Flat-Ground Video Upgrade, 1M-Step Smooth PPO Refinement, and 3D Browser Realism Calibration

**Date:** 2026-11-19  
**Status:** Accepted  

## Context
After completing Stages 0–5, 13 additional real hamster videos were added to `data/raw_video/` (21 total), including fixed-camera flat-ground walking, bipedal rearing, hand-walking/taming, and fixed top-down enclosure exploration. In parallel, live browser review of the photorealistic 3D habitat identified three realism issues: (1) hyperactive movement/turning/grooming speeds, (2) center log-tunnel collision wedging preventing cross-cage wheel visits, and (3) visually invisible wheel rotation on a smooth uniform cylinder.

## Decisions & Verified Results
1. **Batch 2 Pose Extraction (`scripts/stage2b_extract_new_real_videos.py`):**
   - Extracted 5 additional real clips via DeepLabCut 3.0.2 SuperAnimal (`superanimal_quadruped` + `superanimal_topviewmouse`), establishing real flat-ground hamster benchmarks: speed `0.077–0.129 m/s`, stride frequency `1.48–2.09 Hz`, stride length `0.047–0.060 m`, and intermittent stop-start bouts (`0.72–1.22 s` move / `0.25–1.16 s` stop).
   - Expanded `data/reference_motion/` to **6 `REAL_VIDEO` + 5 `SYNTHETIC`** clips.
2. **1M-Step High-Smoothness PPO Refinement (`training/hamster_locomotion_env.py`, `scripts/stage3b_export_best_imitation.py`):**
   - Added native yaw-invariant tilt observations, 2nd-order action-jerk penalty, anti-chatter paw cadence penalty, and stronger yaw tracking.
   - Trained all 4 ablation conditions for `1,000,000` steps (`64` envs on RTX 5070): `imitation_real` achieved `98.0%` non-fall and lowest speed error (`0.0989 m/s`); `imitation_mixed` (exported to `best_policy.onnx`, `max_abs_diff = 1.16e-6`, `0.0126 ms` latency) achieved `98.0%` non-fall, `0.673 m` walk distance, and `100.0%` Stage 4 habitat success at `0.0%` falls.
3. **3D Browser Realism & Interaction Calibration (`web/`):**
   - Wired `ParentInteractionPanel.tsx` into `Observatory.tsx` (Offer Treat / Gentle Pet / Call Attention, non-forced taming meters, FastAPI + local manifest clip fallback).
   - Calibrated `hamsterBehavior.ts` and `poseApplication.ts` directly to measured real-video speeds (`0.085–0.115 m/s`), turning rate (`2.3 rad/s`), speed-locked gait cadence (`0.055 m` stride), wheel cadence (`2.09 Hz`), and calm micro-behaviours (`2.0–7.0 s`).
   - Tightened center log-tunnel padding (`0.036 → 0.022 m`), widened BFS corridor waypoints & timeouts (`14–16 s`), and added 12 wooden inner grip rungs + 3 back-wall spokes to `prop_wheel_drum` so wheel spin is clearly visible.
