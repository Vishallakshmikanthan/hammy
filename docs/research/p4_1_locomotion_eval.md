# P4.1 — Stand-In Quadruped Locomotion Evaluation Report

- **Morphology:** `quadruped_standin_v1.0.0`
- **Environment:** `quadruped_env_v1.0.0`
- **Obs / Act Schemas:** `locomotion_obs_v1.0.0` / `locomotion_act_v1.0.0`
- **Code Version:** `502984a`
- **Behaviour Label:** `learned` (PPO MLP Actor-Critic)
- **ONNX Equivalence Max Diff:** `8.941e-08` (tolerance `1e-5`)

## 5-Seed Summary (Mean ± 95% CI)

| Metric | Value |
| --- | --- |
| Success Rate (no-fall episodes) | 1.0000 ± 0.0000 |
| Falls per Episode | 0.0000 ± 0.0000 |
| Speed Tracking Error (m/s) | 0.2443 ± 0.0092 |

## Per-Seed Breakdown

| Seed | Success Rate | Falls / Ep | Speed Error (m/s) |
| --- | ---: | ---: | ---: |
| 42 | 1.0000 | 0.0000 | 0.2486 |
| 101 | 1.0000 | 0.0000 | 0.2348 |
| 202 | 1.0000 | 0.0000 | 0.2593 |
| 303 | 1.0000 | 0.0000 | 0.2340 |
| 404 | 1.0000 | 0.0000 | 0.2448 |
