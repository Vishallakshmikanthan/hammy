# P7.1 — Curiosity (RND) & Autonomy 30-Day Ablation Report

*Generated strictly from stored experiment data in `training/experiments/p7_1_autonomy/ablation_results.json`.*

- **Horizon:** 30 simulated days (2,880 ticks @ 15 min/tick), habitat rearrangement at Day 15
- **Seeds:** `[42, 101, 202, 303, 404]` (5 seeds per condition, 20 runs total)

## 2×2 Ablation Summary (Mean ± 95% CI)

| Condition | Homeostasis Time-in-Range | Behavioural Diversity (Norm. Entropy) | Routine Formation (Circadian) | Adaptation After Rearrangement (h) |
| --- | ---: | ---: | ---: | ---: |
| `mem_off_cur_off` | 0.6705 ± 0.0128 | 0.2321 ± 0.0055 | 0.5959 ± 0.0035 | 4.75 ± 3.30 |
| `mem_on_cur_off` | 0.6688 ± 0.0085 | 0.2299 ± 0.0069 | 0.5962 ± 0.0054 | 4.25 ± 2.80 |
| `mem_off_cur_on` | 0.6711 ± 0.0087 | 0.2309 ± 0.0069 | 0.5940 ± 0.0047 | 5.95 ± 1.51 |
| `mem_on_cur_on` | 0.6708 ± 0.0076 | 0.2295 ± 0.0068 | 0.5947 ± 0.0051 | 5.40 ± 1.73 |

## Claims Supported vs. Not Supported by This Data

### Supported
- **Homeostatic stability & circadian routine:** All 4 conditions maintained ~`67.08%` time-in-range and ~`0.59` circadian routine score over 30 simulated days.

### Not Supported
- Does **not** prove physical 3D motor learning (this 30-day ablation uses high-level skill selection over drive dynamics; low-level motor control is evaluated separately in P4.1/P4.2).
- Does **not** prove long-term open-ended skill invention (all skills are from the fixed `SKILLS_LIST` library).
- **RND curiosity did NOT meaningfully increase behavioural diversity in this run:** `mem_on_cur_on` (`0.2295`) vs `mem_on_cur_off` (`0.2299`) are within 95% CI overlap.
- **Memory + curiosity did NOT speed up post-rearrangement adaptation in this run:** `mem_on_cur_on` (`5.40 h`) vs `mem_off_cur_off` (`4.75 h`) overlap within 95% CI.
