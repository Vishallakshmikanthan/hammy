"""
HAMMY — P1.5: Empirical Skill-Outcome Models for Fast Background Simulation (`ai/cognition/skill_outcome_model.py`).
Implements:
  - Parametric conditional empirical distribution models fitted to `simulation/datasets/skill_outcomes.parquet`.
  - Conditioned on initial distance to target, current drive states, and circadian phase.
  - Samples: success, duration (sec), energy cost, collision count, drive deltas, and final state.
  - Exposes `sample_skill_outcome(skill, context, rng)` where every sampled outcome is explicitly
    tagged with `origin = EventOrigin.SAMPLED_FROM_SKILL_MODEL` (Non-Negotiable Rule 2).
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from contracts.schemas import (
    BehaviourType,
    DriveVectorV1,
    EventOrigin,
    ObservationV1,
    ObservationV2,
)
from ai.policies.skills import SKILLS_BY_NAME, SKILL_NAMES, Skill

PARQUET_DATASET_PATH = ROOT_DIR / "simulation" / "datasets" / "skill_outcomes.parquet"
PARAMS_JSON_PATH = Path(__file__).parent / "skill_models_params.json"

DRIVE_KEYS = ["hunger", "thirst", "energy", "comfort", "stress", "curiosity"]

OBJECT_POSITIONS_DEFAULT = {
    "prop_bowl_main": [0.32, -0.08, 0.04],
    "prop_bottle_main": [0.38, 0.12, 0.08],
    "prop_hideout_main": [-0.26, -0.06, 0.06],
    "prop_tunnel_main": [-0.10, 0.14, 0.05],
    "prop_wheel_main": [-0.34, 0.10, 0.16],
    "prop_chew_block_main": [0.08, -0.14, 0.03],
}

TARGET_PROP_BY_SKILL = {
    "approach_food": "prop_bowl_main",
    "eat": "prop_bowl_main",
    "drink": "prop_bottle_main",
    "explore_area": "prop_chew_block_main",
    "rest": "prop_hideout_main",
    "hide": "prop_tunnel_main",
    "enter_tunnel": "prop_tunnel_main",
    "run_on_wheel": "prop_wheel_main",
}


class SkillOutcome(BaseModel):
    """Result of sampling a skill execution from empirical models (Rule 2: origin enforcement)."""
    model_config = ConfigDict(extra="forbid")

    skill_name: str
    success: bool
    duration_sec: float = Field(..., ge=0.0)
    energy_cost: float = Field(..., ge=0.0)
    collision_count: int = Field(default=0, ge=0)
    delta_drives: Dict[str, float]
    final_drives: DriveVectorV1
    final_pos_xyz: List[float] = Field(..., min_length=3, max_length=3)
    final_flags: Dict[str, bool] = Field(default_factory=dict)
    final_cheek_pouch_fill: float = Field(default=0.0, ge=0.0, le=1.0)
    origin: EventOrigin = Field(default=EventOrigin.SAMPLED_FROM_SKILL_MODEL)
    behaviour_type: BehaviourType = Field(default=BehaviourType.SCRIPTED)


class EmpiricalSkillModel:
    """Statistical model for a single skill fitted on physics rollouts."""

    def __init__(self, skill_name: str, params: Dict[str, Any]):
        self.skill_name = skill_name
        self.params = params

    @classmethod
    def fit_from_df(cls, skill_name: str, df: pd.DataFrame) -> EmpiricalSkillModel:
        sub = df[df["skill_name"] == skill_name]
        if len(sub) == 0:
            raise ValueError(f"No records found for skill '{skill_name}'")

        # 1. Success rate
        success_rate = float(sub["success"].mean())

        # 2. Duration distribution: mean, std, distance correlation
        dur_mean = float(sub["duration_sec"].mean())
        dur_std = float(sub["duration_sec"].std(ddof=1)) if len(sub) > 1 else 0.5
        dist_mean = float(sub["init_dist_to_target_m"].mean())
        # Linear slope vs distance if std > 0
        if dist_mean > 0 and sub["init_dist_to_target_m"].std() > 1e-4:
            cov = np.cov(sub["init_dist_to_target_m"], sub["duration_sec"])[0, 1]
            var_dist = float(sub["init_dist_to_target_m"].var())
            slope_dist = cov / max(1e-6, var_dist)
        else:
            slope_dist = 0.0

        # 3. Energy cost and collisions
        energy_mean = float(sub["energy_cost"].mean())
        energy_std = float(sub["energy_cost"].std(ddof=1)) if len(sub) > 1 else 0.001
        collision_mean = float(sub["collision_count"].mean())

        # 4. Drive deltas (mean and std for each of the 6 drives)
        drive_deltas = {}
        for k in DRIVE_KEYS:
            col = f"delta_{k}"
            m = float(sub[col].mean()) if col in sub else 0.0
            s = float(sub[col].std(ddof=1)) if col in sub and len(sub) > 1 else 0.001
            drive_deltas[k] = {"mean": round(m, 5), "std": round(max(0.0001, s), 5)}

        # 5. Spatial displacement statistics (dx, dy)
        dx = sub["final_pos_x"] - sub["init_pos_x"]
        dy = sub["final_pos_y"] - sub["init_pos_y"]
        dx_mean = float(dx.mean())
        dx_std = float(dx.std(ddof=1)) if len(sub) > 1 else 0.05
        dy_mean = float(dy.mean())
        dy_std = float(dy.std(ddof=1)) if len(sub) > 1 else 0.05

        params = {
            "success_rate": round(success_rate, 4),
            "duration": {
                "mean": round(dur_mean, 2),
                "std": round(max(0.2, dur_std), 2),
                "slope_dist": round(float(slope_dist), 3),
                "dist_mean": round(dist_mean, 3),
                "min": round(float(sub["duration_sec"].min()), 1),
                "max": round(float(sub["duration_sec"].max()), 1),
            },
            "energy_cost": {
                "mean": round(energy_mean, 5),
                "std": round(max(0.0001, energy_std), 5),
            },
            "collision_rate": round(collision_mean, 3),
            "drive_deltas": drive_deltas,
            "displacement": {
                "dx_mean": round(dx_mean, 4),
                "dx_std": round(dx_std, 4),
                "dy_mean": round(dy_mean, 4),
                "dy_std": round(dy_std, 4),
            },
        }
        return cls(skill_name, params)

    def sample(
        self,
        context: Dict[str, Any],
        rng: Optional[np.random.Generator] = None,
    ) -> SkillOutcome:
        active_rng = rng or np.random.default_rng()

        init_dist = float(context.get("dist_to_target_m", 0.25))
        init_drives = context.get("drives", {})
        init_pos = context.get("position_xyz", [0.0, 0.0, 0.165])
        target_oid = TARGET_PROP_BY_SKILL.get(self.skill_name)
        target_pos = context.get("target_pos_xyz") or OBJECT_POSITIONS_DEFAULT.get(target_oid, [0.0, 0.0, 0.05])

        # 1. Sample success
        # If eat, must be close to food bowl
        if self.skill_name == "eat" and init_dist > 0.085:
            success = False
        else:
            success = bool(active_rng.uniform(0.0, 1.0) <= self.params["success_rate"])

        # 2. Sample duration
        dur_cfg = self.params["duration"]
        base_dur = dur_cfg["mean"] + dur_cfg["slope_dist"] * (init_dist - dur_cfg["dist_mean"])
        dur = float(active_rng.normal(base_dur, dur_cfg["std"]))
        dur = float(np.clip(dur, dur_cfg["min"], dur_cfg["max"]))

        # 3. Sample energy cost & collisions
        ec_cfg = self.params["energy_cost"]
        energy_cost = max(0.0, float(active_rng.normal(ec_cfg["mean"], ec_cfg["std"])))
        collisions = int(max(0, active_rng.poisson(max(0.01, self.params["collision_rate"]))))

        # 4. Sample drive deltas
        deltas: Dict[str, float] = {}
        final_drives_dict: Dict[str, float] = {}
        for k in DRIVE_KEYS:
            d_cfg = self.params["drive_deltas"][k]
            cur_val = float(init_drives.get(k, 0.50))
            delta = float(active_rng.normal(d_cfg["mean"], d_cfg["std"]))

            # Physics-consistent bounds: eating cannot reduce hunger below 0
            if k == "hunger" and self.skill_name in ("eat", "approach_food") and success:
                delta = -min(cur_val, abs(delta))
            elif k == "thirst" and self.skill_name == "drink" and success:
                delta = -min(cur_val, abs(delta))
            elif k == "energy" and self.skill_name == "rest" and success:
                delta = max(0.0, delta)

            deltas[k] = round(delta, 5)
            final_drives_dict[k] = float(np.clip(cur_val + delta, 0.0, 1.0))

        # Advance circadian phase by duration (24h = 86400s)
        cur_phase = float(init_drives.get("circadian_phase", 0.0))
        final_phase = (cur_phase + (dur / 86400.0)) % 1.0
        final_drives_dict["circadian_phase"] = round(final_phase, 4)

        # 5. Sample final spatial coordinates & flags
        final_flags = {
            "inside_hideout": False,
            "inside_tunnel": False,
            "on_wheel": False,
        }
        cheek_fill = round(float(np.clip(context.get("cheek_pouch_fill", 0.0), 0.0, 1.0)), 4)
        if self.skill_name == "eat" and success:
            cheek_fill = min(1.0, round(cheek_fill + float(active_rng.uniform(0.05, 0.15)), 4))

        if success and target_oid:
            # Arrived at target object with slight jitter
            jitter = active_rng.normal(0.0, 0.015, size=2)
            fx = float(np.clip(target_pos[0] + jitter[0], -0.45, 0.45))
            fy = float(np.clip(target_pos[1] + jitter[1], -0.20, 0.20))
            fz = float(target_pos[2])

            if self.skill_name == "rest":
                final_flags["inside_hideout"] = True
            elif self.skill_name in ("hide", "enter_tunnel"):
                final_flags["inside_tunnel"] = True
            elif self.skill_name == "run_on_wheel":
                final_flags["on_wheel"] = True
        else:
            disp = self.params["displacement"]
            dx = float(active_rng.normal(disp["dx_mean"], disp["dx_std"]))
            dy = float(active_rng.normal(disp["dy_mean"], disp["dy_std"]))
            fx = float(np.clip(init_pos[0] + dx, -0.45, 0.45))
            fy = float(np.clip(init_pos[1] + dy, -0.20, 0.20))
            fz = float(init_pos[2])

        final_pos_xyz = [round(fx, 4), round(fy, 4), round(fz, 4)]

        b_type = BehaviourType.SCRIPTED
        if self.skill_name in SKILLS_BY_NAME:
            b_type = SKILLS_BY_NAME[self.skill_name].behaviour_type

        return SkillOutcome(
            skill_name=self.skill_name,
            success=success,
            duration_sec=round(dur, 2),
            energy_cost=round(energy_cost, 5),
            collision_count=collisions,
            delta_drives=deltas,
            final_drives=DriveVectorV1(**final_drives_dict),
            final_pos_xyz=final_pos_xyz,
            final_flags=final_flags,
            final_cheek_pouch_fill=cheek_fill,
            origin=EventOrigin.SAMPLED_FROM_SKILL_MODEL,
            behaviour_type=b_type,
        )


class SkillOutcomeModelManager:
    """Manages all 8 empirical skill models and handles persistence."""

    def __init__(self, params_path: Optional[str | Path] = None):
        self.params_path = Path(params_path or PARAMS_JSON_PATH)
        self.models: Dict[str, EmpiricalSkillModel] = {}

        if self.params_path.exists():
            self._load_params()
        elif PARQUET_DATASET_PATH.exists():
            self.fit_and_save()
        else:
            # Fallback will fit when parquet is generated
            pass

    def fit_and_save(self, parquet_path: Optional[str | Path] = None) -> None:
        p_path = Path(parquet_path or PARQUET_DATASET_PATH)
        if not p_path.exists():
            raise FileNotFoundError(f"Parquet dataset not found at {p_path}")

        df = pd.read_parquet(p_path)
        all_params = {}

        for s_name in SKILL_NAMES:
            model = EmpiricalSkillModel.fit_from_df(s_name, df)
            self.models[s_name] = model
            all_params[s_name] = model.params

        self.params_path.parent.mkdir(parents=True, exist_ok=True)
        self.params_path.write_text(json.dumps(all_params, indent=2), encoding="utf-8")

    def _load_params(self) -> None:
        all_params = json.loads(self.params_path.read_text(encoding="utf-8"))
        for s_name, p in all_params.items():
            self.models[s_name] = EmpiricalSkillModel(s_name, p)

    def sample(
        self,
        skill_name: str,
        context: Dict[str, Any] | ObservationV1 | ObservationV2,
        rng: Optional[np.random.Generator] = None,
    ) -> SkillOutcome:
        if not self.models:
            if self.params_path.exists():
                self._load_params()
            elif PARQUET_DATASET_PATH.exists():
                self.fit_and_save()
            else:
                raise RuntimeError("Skill models not fitted yet; run collector first.")

        if skill_name not in self.models:
            raise ValueError(f"Unknown skill '{skill_name}'")

        # Convert ObservationV1/V2 to context dict if needed
        if isinstance(context, (ObservationV1, ObservationV2)):
            target_oid = TARGET_PROP_BY_SKILL.get(skill_name)
            dist_to_target = 0.25
            target_pos = None
            for o in context.nearby_objects:
                if o.object_id == target_oid:
                    dist_to_target = o.distance_m
                    target_pos = [
                        context.position_xyz[0] + o.rel_pos_xy[0],
                        context.position_xyz[1] + o.rel_pos_xy[1],
                        0.05,
                    ]
                    break

            ctx_dict = {
                "drives": context.drives.model_dump(),
                "position_xyz": list(context.position_xyz),
                "dist_to_target_m": dist_to_target,
                "target_pos_xyz": target_pos,
                "cheek_pouch_fill": context.cheek_pouch_fill,
            }
        else:
            ctx_dict = dict(context)

        return self.models[skill_name].sample(ctx_dict, rng=rng)


# Global singleton instance
_MODEL_MANAGER: Optional[SkillOutcomeModelManager] = None


def get_skill_outcome_model_manager() -> SkillOutcomeModelManager:
    global _MODEL_MANAGER
    if _MODEL_MANAGER is None:
        _MODEL_MANAGER = SkillOutcomeModelManager()
    return _MODEL_MANAGER


def sample_skill_outcome(
    skill: str | Skill,
    context: Dict[str, Any] | ObservationV1 | ObservationV2,
    rng: Optional[np.random.Generator] = None,
) -> SkillOutcome:
    """
    Primary API function required by P1.5 specification:
    `sample_skill_outcome(skill, context, rng)`
    Explicitly tags the output with `origin = EventOrigin.SAMPLED_FROM_SKILL_MODEL`.
    """
    skill_name = skill.name if isinstance(skill, Skill) else str(skill)
    manager = get_skill_outcome_model_manager()
    return manager.sample(skill_name, context, rng=rng)
