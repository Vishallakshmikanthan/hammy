# HAMMY — P1.2 Homeostatic Drives & 100-Day Baseline Report

- **Behaviour Label (Non-Negotiable Rule 1):** `scripted` (`ScriptedHomeostaticBaselinePolicy`)
- **Event Origin (Non-Negotiable Rule 2):** `observed_physics`
- **Simulated Duration:** `100.0 days` (`28,800` steps at `dt = 300 s`)
- **Wall-Clock Execution Time:** `4.65 seconds` (`6,187` steps/sec)
- **Cumulative Homeostatic Reward:** `-0.0942`
- **Plot Artifact:** `docs/research/baseline_100days_drives.svg`

## 1. Time-in-Healthy-Range Across 100 Simulated Days (`scripted`)

| Drive | Healthy Bounds | Mean Value | Min / Max | Time in Healthy Range (%) |
| :--- | :--- | :--- | :--- | :--- |
| **Hunger** | `[0.00, 0.45]` | `0.115` | `0.000` / `0.288` | **100.00%** |
| **Thirst** | `[0.00, 0.40]` | `0.121` | `0.000` / `0.335` | **100.00%** |
| **Energy** | `[0.35, 1.00]` | `0.681` | `0.000` / `1.000` | **93.88%** |
| **Comfort** | `[0.50, 1.00]` | `0.998` | `0.735` / `1.000` | **100.00%** |
| **Stress** | `[0.00, 0.35]` | `0.001` | `0.000` / `0.097` | **100.00%** |
| **Curiosity** | `[0.00, 0.65]` | `0.001` | `0.000` / `0.256` | **100.00%** |

- **Overall Mean Time-in-Healthy-Range:** **98.98%**

## 2. Skill Allocation Distribution (`scripted`)

| Skill Name | Steps Selected | Share of 100 Days (%) |
| :--- | :--- | :--- |
| `sleep_in_hideout` | 23,003 | 79.87% |
| `run_on_wheel` | 2,254 | 7.83% |
| `drink_at_bottle` | 2,041 | 7.09% |
| `eat_at_bowl` | 1,502 | 5.22% |
