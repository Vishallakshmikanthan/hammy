"""
HAMMY — P1.5 Unit Tests: Skill-Outcome Models & Background Simulation (`tests/test_p1_5.py`).
Tests:
  1. Parquet Dataset: Verification of 1,200 physics rollouts, schema columns, and non-NaN values.
  2. Model Checkpoint: Verification of `skill_models_params.json` containing all 8 skill distributions.
  3. Skill Outcome Sampling: Explicit enforcement of `origin = EventOrigin.SAMPLED_FROM_SKILL_MODEL`
     per Non-Negotiable Rule 2.
  4. Contract Inputs: Sampling with `ObservationV1` and `ObservationV2` contexts.
  5. Multi-Step Catch-Up Progression: Monotonic time progression, bounded drives, and physical validity.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import pandas as pd
from pydantic import ValidationError

from contracts.schemas import (
    BehaviourType,
    DriveVectorV1,
    EventOrigin,
    ObservationV1,
    ObservationV2,
)
from simulation.habitat_env import HabitatEnv
from ai.policies.skills import SKILL_NAMES, SKILLS_BY_NAME
from ai.cognition.skill_outcome_model import (
    PARAMS_JSON_PATH,
    PARQUET_DATASET_PATH,
    SkillOutcome,
    get_skill_outcome_model_manager,
    sample_skill_outcome,
)


class TestPhase1_5SkillOutcomeModels(unittest.TestCase):
    def test_parquet_dataset_exists_and_valid(self):
        """Verify Parquet dataset integrity: row count, schema columns, and absence of NaNs."""
        self.assertTrue(PARQUET_DATASET_PATH.exists(), f"Dataset not found at {PARQUET_DATASET_PATH}")
        df = pd.read_parquet(PARQUET_DATASET_PATH)

        self.assertGreaterEqual(len(df), 1000)
        # Check all 8 skills exist in dataset
        unique_skills = set(df["skill_name"].unique())
        for s_name in SKILL_NAMES:
            self.assertIn(s_name, unique_skills)

        # Mandatory columns
        required_cols = [
            "skill_name", "skill_version", "environment_version", "seed",
            "init_dist_to_target_m", "init_hunger", "init_energy",
            "success", "duration_sec", "energy_cost", "collision_count",
            "delta_hunger", "delta_thirst", "delta_energy",
            "final_pos_x", "final_pos_y", "final_inside_hideout"
        ]
        for col in required_cols:
            self.assertIn(col, df.columns)

        # No NaNs in duration or drive deltas
        self.assertFalse(df["duration_sec"].isna().any())
        self.assertFalse(df["delta_hunger"].isna().any())
        self.assertFalse(df["delta_energy"].isna().any())

    def test_empirical_model_parameters(self):
        """Verify empirical parameter checkpoint structure and valid statistics."""
        manager = get_skill_outcome_model_manager()
        self.assertTrue(PARAMS_JSON_PATH.exists())

        for s_name in SKILL_NAMES:
            self.assertIn(s_name, manager.models)
            model = manager.models[s_name]
            p = model.params
            self.assertGreaterEqual(p["success_rate"], 0.0)
            self.assertLessEqual(p["success_rate"], 1.0)
            self.assertGreater(p["duration"]["mean"], 0.0)
            self.assertGreater(p["duration"]["std"], 0.0)
            self.assertIn("delta_hunger", [f"delta_{k}" for k in p["drive_deltas"]])

    def test_sample_skill_outcome_origin_and_contract(self):
        """Verify Rule 2: origin is strictly EventOrigin.SAMPLED_FROM_SKILL_MODEL."""
        rng = np.random.default_rng(777)
        dummy_context = {
            "dist_to_target_m": 0.20,
            "drives": {
                "hunger": 0.45,
                "thirst": 0.35,
                "energy": 0.60,
                "comfort": 0.80,
                "stress": 0.15,
                "curiosity": 0.40,
                "circadian_phase": 0.20,
            },
            "position_xyz": [0.10, -0.05, 0.165],
            "cheek_pouch_fill": 0.05,
        }

        for s_name in SKILL_NAMES:
            outcome = sample_skill_outcome(s_name, dummy_context, rng=rng)
            self.assertIsInstance(outcome, SkillOutcome)
            self.assertEqual(outcome.skill_name, s_name)
            # NON-NEGOTIABLE RULE 2:
            self.assertEqual(outcome.origin, EventOrigin.SAMPLED_FROM_SKILL_MODEL)
            self.assertGreater(outcome.duration_sec, 0.0)
            self.assertGreaterEqual(outcome.energy_cost, 0.0)
            self.assertGreaterEqual(outcome.collision_count, 0)

            # Drives contract verification
            d = outcome.final_drives
            self.assertIsInstance(d, DriveVectorV1)
            for k in ["hunger", "thirst", "energy", "comfort", "stress", "curiosity", "circadian_phase"]:
                val = getattr(d, k)
                self.assertGreaterEqual(val, 0.0)
                self.assertLessEqual(val, 1.0)

            # Spatial boundary check
            self.assertEqual(len(outcome.final_pos_xyz), 3)
            self.assertLessEqual(abs(outcome.final_pos_xyz[0]), 0.46)
            self.assertLessEqual(abs(outcome.final_pos_xyz[1]), 0.21)

    def test_sample_with_observation_contract(self):
        """Verify sampling accepts ObservationV1 and ObservationV2 objects directly."""
        env = HabitatEnv()
        obs_v1, _ = env.reset(seed=42)

        out1 = sample_skill_outcome("eat", obs_v1)
        self.assertIsInstance(out1, SkillOutcome)
        self.assertEqual(out1.origin, EventOrigin.SAMPLED_FROM_SKILL_MODEL)

        env_v2 = HabitatEnv(use_v2_observation=True)
        obs_v2, _ = env_v2.reset(seed=42)
        out2 = sample_skill_outcome("drink", obs_v2)
        self.assertIsInstance(out2, SkillOutcome)
        self.assertEqual(out2.origin, EventOrigin.SAMPLED_FROM_SKILL_MODEL)

    def test_chained_catchup_progression(self):
        """Simulate 25 consecutive background catch-up steps chaining outcomes."""
        rng = np.random.default_rng(1234)
        current_drives = DriveVectorV1(
            hunger=0.20, thirst=0.20, energy=0.80,
            comfort=0.80, stress=0.10, curiosity=0.30,
            circadian_phase=0.0,
        )
        current_pos = [0.0, 0.0, 0.165]
        sim_time = 0.0

        for step in range(25):
            ctx = {
                "dist_to_target_m": 0.25,
                "drives": current_drives.model_dump(),
                "position_xyz": current_pos,
            }
            # Alternate through realistic skills
            skill_choice = ["explore_area", "eat", "drink", "rest", "run_on_wheel"][step % 5]
            out = sample_skill_outcome(skill_choice, ctx, rng=rng)

            self.assertGreater(out.duration_sec, 0.0)
            sim_time += out.duration_sec
            current_drives = out.final_drives
            current_pos = out.final_pos_xyz

        self.assertGreater(sim_time, 100.0)
        self.assertTrue(0.0 <= current_drives.hunger <= 1.0)
        self.assertTrue(0.0 <= current_drives.energy <= 1.0)


if __name__ == "__main__":
    unittest.main()
