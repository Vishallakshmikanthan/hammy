# HAMMY RL Brain v2 — GPU GRU-Recurrent PPO + RND Autonomy & Ablation Report

*Generated strictly from real RTX 5070 GPU RL training runs (`training/runs/brain_v2/train_summary.json` & `training/experiments/rl_brain_v2/ablation_results.json`).*

- **Production Policy:** `hl_rppo_rnd_v2.0.0` (`49,938,432` SMDP steps at `124,522` steps/s on `NVIDIA GeForce RTX 5070 Laptop GPU`)
- **ONNX Artifact:** `training/runs/brain_v2/high_level_brain_v2.onnx` (`825.65 KB`, latency `0.02408 ms`, PyTorch parity `5.72e-06`)
- **Production Eval:** Homeostasis `99.40%`, Diversity `0.6161`, Circadian Routine `0.8096`, Novel Prop Explore `26.2%`
- **Learned Non-Forced Taming:** Low-trust retreat `58.8%` -> Mid-trust cautious sniff `48.7%` -> High-trust accept petting `99.9%`

## 2x2 Real RL Ablation Summary (Mean +/- 95% CI, 3 Seeds Each)

| Condition | Homeostasis In-Range | Diversity (Entropy) | Circadian Routine | Novel-Prop Explore | Mean Step Reward |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `mem_off_cur_off` | 0.9784 +/- 0.0034 | 0.8778 +/- 0.0304 | 0.5633 +/- 0.0064 | 0.0617 +/- 0.0112 | +0.5270 +/- 0.0085 |
| `mem_on_cur_off` | 0.9745 +/- 0.0020 | 0.8231 +/- 0.0737 | 0.5833 +/- 0.0293 | 0.0191 +/- 0.0054 | +0.5148 +/- 0.0185 |
| `mem_off_cur_on` | 0.9743 +/- 0.0044 | 0.8794 +/- 0.0147 | 0.6132 +/- 0.0213 | 0.0609 +/- 0.0086 | +0.5184 +/- 0.0113 |
| `mem_on_cur_on` | 0.9726 +/- 0.0036 | 0.8492 +/- 0.0260 | 0.5880 +/- 0.0123 | 0.0156 +/- 0.0075 | +0.5212 +/- 0.0055 |
