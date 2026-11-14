# P6.1 — Hamster Behaviours & Honest Implementation Labels

Per Non-Negotiable Rule 1, every behaviour records its exact implementation type. None of the high-level behaviour controllers below are claimed as end-to-end learned motor skills; their low-level execution is `scripted` while high-level skill selection is `learned` (or `scripted` in the priority baseline), hence **`scripted-with-learned-selection`**.

| Behaviour | Implementation Type | Initiation Condition | Termination Condition | Primary Drive Effects | Visual Treatment (Rig + Morphs) |
| --- | --- | --- | --- | --- | --- |
| `cheek_stuffing` | `scripted-with-learned-selection` | `hunger > 0.15` | `elapsed > 60s` or `hunger < 0.10` | `hunger -`, `comfort +`, `stress -` | `cheek_pouch_left/right` (0→1), `mouth_open`, `chew` |
| `hind_leg_standing` | `scripted-with-learned-selection` | `curiosity > 0.20` | `elapsed > 20s` | `curiosity -`, `stress -` | `whisker_forward`, `nose_wrinkle`, `earOrientation`, `blinkAndGaze` |
| `grooming` | `scripted-with-learned-selection` | `stress > 0.15` or `comfort < 0.85` | `elapsed > 45s` | `stress -`, `comfort +` | `squint`, `blink`, `mouth_open`, `springJiggle` |
| `digging` | `scripted-with-learned-selection` | `curiosity > 0.25` & `energy > 0.40` | `elapsed > 50s` | `curiosity -`, `comfort +`, `energy -` | `BeddingDeformer` paw scoops, `nose_wrinkle`, `tail` |
| `nesting` | `scripted-with-learned-selection` | `comfort < 0.70` or `energy < 0.55` | `elapsed > 90s` or `comfort > 0.85` | `comfort +`, `stress -`, `energy +` | `ear_fold`, `squint`, `breath_in`, `breathing` |

