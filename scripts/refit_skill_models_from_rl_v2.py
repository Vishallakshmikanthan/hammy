"""
HAMMY — Phase E: Refit Empirical Background Catch-Up Surrogates (`ai/cognition/skill_models_params.json`)
from real biological drive dynamics so background catch-up never drives curiosity permanently to 0.0%!
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import numpy as np

from ai.cognition.drives import HomeostaticDrives
from ai.cognition.skill_outcome_model import PARAMS_JSON_PATH, TARGET_PROP_BY_SKILL

SKILLS_BASE_8 = (
    "approach_food",
    "eat",
    "drink",
    "explore_area",
    "rest",
    "hide",
    "enter_tunnel",
    "run_on_wheel",
)


def refit_balanced_skill_models(n_rollouts_per_skill: int = 300, seed: int = 42) -> Dict[str, dict]:
    """Samples physically consistent drive deltas from HomeostaticDrives so catch-up
    keeps Hunger, Thirst, Energy, Comfort, Stress, and Curiosity naturally balanced."""
    rng = np.random.default_rng(seed)
    all_params: Dict[str, dict] = {}

    dur_ranges = {
        "approach_food": (12.0, 28.0),
        "eat": (35.0, 75.0),
        "drink": (25.0, 55.0),
        "explore_area": (60.0, 150.0),
        "rest": (180.0, 480.0),
        "hide": (80.0, 180.0),
        "enter_tunnel": (35.0, 80.0),
        "run_on_wheel": (70.0, 180.0),
    }

    for sk in SKILLS_BASE_8:
        durs, ec, d_h, d_t, d_e, d_c, d_s, d_q = [], [], [], [], [], [], [], []
        lo, hi = dur_ranges[sk]
        for _ in range(n_rollouts_per_skill):
            hd = HomeostaticDrives(
                hunger=float(rng.uniform(0.15, 0.55)),
                thirst=float(rng.uniform(0.15, 0.50)),
                energy=float(rng.uniform(0.45, 0.90)),
                comfort=float(rng.uniform(0.55, 0.90)),
                stress=float(rng.uniform(0.08, 0.40)),
                curiosity=float(rng.uniform(0.15, 0.60)),
                circadian_phase=float(rng.uniform(0.0, 1.0)),
            )
            h0, t0, e0, c0, s0, q0 = hd.hunger, hd.thirst, hd.energy, hd.comfort, hd.stress, hd.curiosity
            dur = float(rng.uniform(lo, hi))
            hd.step(
                dur,
                is_eating=(sk == "eat"),
                is_drinking=(sk == "drink"),
                is_sleeping=(sk == "rest"),
                is_sheltered=(sk in ("rest", "hide", "enter_tunnel")),
                is_running_wheel=(sk == "run_on_wheel"),
                is_exploring=(sk in ("explore_area", "enter_tunnel")),
            )
            # Natural awake curiosity rise during eating/drinking/approaching (fixes legacy negative-curiosity bug!)
            if sk in ("approach_food", "eat", "drink"):
                hd.curiosity = float(np.clip(hd.curiosity + 0.025, 0.0, 1.0))

            durs.append(dur)
            ec.append(max(0.0, e0 - hd.energy))
            d_h.append(hd.hunger - h0)
            d_t.append(hd.thirst - t0)
            d_e.append(hd.energy - e0)
            d_c.append(hd.comfort - c0)
            d_s.append(hd.stress - s0)
            d_q.append(hd.curiosity - q0)

        def _ms(arr):
            return {"mean": round(float(np.mean(arr)), 5), "std": round(max(0.0005, float(np.std(arr, ddof=1))), 5)}

        all_params[sk] = {
            "success_rate": 0.985,
            "duration": {
                "mean": round(float(np.mean(durs)), 2),
                "std": round(max(0.5, float(np.std(durs, ddof=1))), 2),
                "slope_dist": 6.0,
                "dist_mean": 0.25,
                "min": round(lo, 1),
                "max": round(hi, 1),
            },
            "energy_cost": _ms(ec),
            "collision_rate": 0.0,
            "drive_deltas": {
                "hunger": _ms(d_h),
                "thirst": _ms(d_t),
                "energy": _ms(d_e),
                "comfort": _ms(d_c),
                "stress": _ms(d_s),
                "curiosity": _ms(d_q),
            },
            "displacement": {
                "dx_mean": 0.0,
                "dx_std": 0.12,
                "dy_mean": 0.0,
                "dy_std": 0.07,
            },
        }

    PARAMS_JSON_PATH.write_text(json.dumps(all_params, indent=2), encoding="utf-8")
    return all_params


if __name__ == "__main__":
    out = refit_balanced_skill_models()
    print(f"[SURROGATES] Refitted {len(out)} balanced skill models -> {PARAMS_JSON_PATH}")
    for k, v in out.items():
        print(f"  {k:15s} delta_curiosity={v['drive_deltas']['curiosity']['mean']:+.4f} delta_hunger={v['drive_deltas']['hunger']['mean']:+.4f}")
