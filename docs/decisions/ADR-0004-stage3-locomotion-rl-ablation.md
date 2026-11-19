# ADR-0004: Stage 3 Locomotion RL with Imitation, 4-Way Ablation, and Baked-Norm ONNX Export

**Date:** 2026-11-19  
**Status:** Accepted (Awaiting HUMAN CHECKPOINT 3)  

## Context
Stage 3 trains a 50 Hz PPO locomotion policy for `hamster_mjcf_v1.0.0` (16 actuated DoF) using our versioned 64-dim observation contract (`locomotion_obs_v1.0.0`), success-gated curriculum (`stand → perturb → walk → turn → stop → target`), domain randomization, per-term reward logging, 4-way imitation ablation, and portable ONNX export.

## Key Engineering Findings & Decisions
1. **64-Env Parallelism Benchmark (`training/runs/stage3/bench_64envs.json`):**
   - `64 DummyVecEnv` on RTX 5070 achieved **`2,855.4` PPO train steps/s** (`4,124.2` rollout steps/s) using only **`18.07 MB`** peak GPU VRAM — nearly **7× faster** than `8 SubprocVecEnv` (`413.3` train steps/s) with zero multiprocessing overhead.
2. **Reward-Hacking & Physics Sign Diagnosis (Caught by Automated Audit):**
   - Initial run revealed zero-velocity standing collapse (`walk_dist = 0.01–0.06 m`, `100%` non-fall). Root causes: (a) right-hand-rule hip stance sign in Stage 2 reference clips initially pushed backward (`-0.188 m`), (b) `n_steps=256` with `64` envs performed only 24 PPO updates in 400k steps, and (c) high upright survival bonus rewarded freezing.
   - **Fixes:** Corrected hip stance/swing sign (verified open-loop `+0.190 m` walk / `+0.434 m` trot in MuJoCo), switched to `n_steps=64` (`122` PPO updates in 500k steps), added DeepMimic Reference State Initialization (RSI) during training resets while keeping the runtime `raw_obs -> action` policy 100% self-contained, and added an explicit anti-freeze forward progress term.
3. **4-Way Ablation Results (100 Randomized Episodes Each, `seed=42`, `500k` steps):**
   - `imitation_mixed` (`LEARNED` from `REAL_VIDEO` + `SYNTHETIC`): **`100.0%` non-fall**, lowest speed error (**`0.0741 m/s`**), `0.617 m` walk dist / 5 s, `0.2495 rad` joint RMSE, `0.357 s` stop settling.
   - `imitation_synthetic` (`LEARNED` from `SYNTHETIC`): **`100.0%` non-fall**, `0.0809 m/s` speed error, `0.623 m` walk dist / 5 s, best joint RMSE (**`0.2224 rad`**, 22% closer to reference than `no_imitation`), `0.232 s` stop settling.
   - `imitation_real` (`LEARNED` from `REAL_VIDEO` wheel/groom): **`100.0%` non-fall**, `0.0793 m/s` speed error, `0.386 m` walk dist / 5 s, fastest stop settling (**`0.166 s`**).
   - `no_imitation` (`LEARNED` pure RL baseline): **`100.0%` non-fall**, `0.0816 m/s` speed error, `0.676 m` walk dist / 5 s, higher joint RMSE (`0.2864 rad`) and slower stop settling (`0.478 s`).
4. **ONNX Export with Baked Observation Normalizer (`microduck_rl` pattern):**
   - Exported `training/runs/stage3/best_policy.onnx` (`340.85 KB`) with `VecNormalize` mean/variance/clip baked into the graph and versioned contract metadata in `metadata_props`.
   - Verified max abs diff vs PyTorch = **`1.07 × 10⁻⁶`** across 256 random observations; single-step CPU latency = **`0.0132 ms`**.
5. **Known Remaining Gaps (Honest Audit):**
   - Raw paw-touch edge frequency (`9.7 Hz`) reflects micro-bouncing paw chatter rather than clean long-swing strides (`2.09 Hz` real wheel / `2.6–4.0 Hz` synthetic target), and yaw-rate tracking error (`1.96 rad/s`) can be tightened in a longer follow-up run with higher yaw & smoothness weights and/or real flat-ground walking footage.
