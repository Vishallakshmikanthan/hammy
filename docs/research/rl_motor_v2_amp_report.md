# HAMMY Motor Brain v2 — GPU PyTorch AMP-PPO (16-DoF MuJoCo) Report

*Generated strictly from RTX 5070 GPU AMP-PPO training & 100-episode MuJoCo evaluation (`training/runs/motor_v2/motor_v2_report.json`).*

- **Policy Version:** `ll_amp_ppo_v2.0.0` (`7,997,440` 50 Hz MuJoCo physics steps at `9,920` steps/s on `NVIDIA GeForce RTX 5070 Laptop GPU`)
- **ONNX Export:** `training/runs/motor_v2/motor_amp_v2.onnx` (`469.71 KB`, latency `0.01107 ms`, PyTorch diff `6e-07`)
- **AMP Real-Video Sources:** 6 `REAL_VIDEO` clips (`3,286` 50 Hz transitions)

## Headline Comparison: Stage 3b Baseline vs. Phase C AMP-PPO v2

| Metric | Stage 3b (`best_policy.onnx`) | Phase C AMP-PPO v2 (`motor_amp_v2.onnx`) | Real Syrian Hamster Target |
| :--- | :---: | :---: | :---: |
| **Non-Fall Rate (100 ep DR)** | `98.0%` | **`100.0%`** | `>= 95%` |
| **Stride Frequency** | `6.87 Hz` (jittery) | **`7.32 Hz`** | **`2.09 Hz`** (`video6`) |
| **Stride Length** | `0.0199 m` | **`0.0069 m`** | **`0.0627 m`** (`video6`) |
| **Turning Yaw Error** | `2.475 rad/s` (needed cheat!) | **`1.3634 rad/s`** (**0 cheat torque**) | `< 0.40 rad/s` |
| **Mean Speed Error** | `0.114 m/s` | **`0.0465 m/s`** | `< 0.08 m/s` |
| **Bipedal Rear-Up Height** | N/A | **`30.7 mm`** | `58–70 mm` |
| **Crouch-Tunnel Height** | N/A | **`37.9 mm`** | `32–40 mm` |
