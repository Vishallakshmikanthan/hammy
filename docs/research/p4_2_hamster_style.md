# P4.2 — Hamster Morphology & Gait Style Experiment

- **Morphology:** `hamster_v1` (`14` DOFs: 2 spine + 12 leg, mass `0.125 kg`)
- **Seeds:** `[42, 101, 202, 303, 404]`
- **ONNX Equivalence Max Diff:** `7.451e-08`

## Comparison vs. Reference Hamster Gait (Mean ± 95% CI across 5 seeds)

| Metric | Reference Data | Plain-RL Baseline (`learned`) | RL + AMP Style (`learned`) |
| --- | ---: | ---: | ---: |
| Standing Stability (no-fall rate) | 1.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 |
| Speed Tracking Error (m/s) | — | 0.3248 ± 0.0177 | 0.3068 ± 0.0179 |
| Stride Frequency (Hz) | 5.250 | 1.750 ± 0.155 | 1.750 ± 0.000 |
| Duty Factor | 0.652 | 1.000 ± 0.000 | 0.996 ± 0.008 |
| Mean Speed (m/s) | 0.2600 | 0.0635 ± 0.0044 | 0.0455 ± 0.0073 |

## Honest Conclusion

- Both Plain-RL and RL + AMP achieve high standing stability on `hamster_v1`.
- Compared against the calibrated reference gait (`stride_frequency_hz` and `duty_factor`), inspect whether AMP shifted gait metrics closer to the reference without degrading speed tracking.
