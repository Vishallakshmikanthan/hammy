"""
HAMMY — P1.3 Unit Tests (`tests/test_p1_3.py`).
Tests the formal skill catalog, high-level SMDP environment, scripted baseline policy,
and PPO Actor-Critic architecture.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np

from contracts.schemas import ActionV1, BehaviourType, ObservationV1
from simulation.habitat_env import HabitatEnv
from simulation.smdp_env import HighLevelSMDPEnv, extract_observation_features
from ai.policies.skills import SKILLS_LIST, SKILL_NAMES, SKILLS_BY_NAME, ScriptedHomeostaticBaselinePolicy
from training.train_high_level import PPOActorCritic, LearnedPPOPolicy


class TestPhase1_3SkillsAndPolicies(unittest.TestCase):
    def setUp(self):
        self.env = HighLevelSMDPEnv(max_smdp_steps=20, sub_dt_sec=2.0, record_trajectory=True)

    def test_skills_catalog_integrity(self):
        """Verify all 8 skills exist with valid attributes and limits."""
        self.assertEqual(len(SKILLS_LIST), 8)
        expected_names = [
            "approach_food", "eat", "drink", "explore_area",
            "rest", "hide", "enter_tunnel", "run_on_wheel"
        ]
        self.assertEqual(SKILL_NAMES, expected_names)

        obs, _ = self.env.env.reset(seed=42)
        for skill in SKILLS_LIST:
            self.assertTrue(isinstance(skill.name, str))
            self.assertGreater(skill.max_duration_sec, 0.0)
            can_init = skill.can_initiate(obs)
            self.assertIsInstance(can_init, bool)
            term = skill.is_terminated(obs, step_in_skill=0, time_in_sec=0.0)
            self.assertIsInstance(term, bool)
            act = skill.step(obs)
            self.assertIsInstance(act, ActionV1)
            self.assertLessEqual(act.forward_speed_m_s, 0.35)
            self.assertLessEqual(abs(act.turn_rate_rad_s), 5.0)

    def test_observation_features_extraction(self):
        """Verify normalized 41-dim feature vector."""
        obs, _ = self.env.env.reset(seed=42)
        feat = extract_observation_features(obs)
        self.assertEqual(feat.shape, (41,))
        self.assertEqual(feat.dtype, np.float32)
        self.assertFalse(np.isnan(feat).any())
        self.assertFalse(np.isinf(feat).any())

    def test_smdp_env_execution(self):
        """Verify SMDP environment macro-stepping and trajectory recording."""
        feat, info = self.env.reset(seed=42)
        self.assertEqual(len(feat), 41)
        self.assertGreaterEqual(len(self.env.trajectory), 1)

        # Step through 5 SMDP macro-steps
        for act_idx in [0, 1, 2, 3, 7]:
            next_feat, r, term, trunc, step_info = self.env.step(act_idx)
            self.assertEqual(len(next_feat), 41)
            self.assertIsInstance(r, float)
            self.assertGreater(step_info["sub_steps"], 0)
            self.assertGreater(step_info["duration_sec"], 0.0)
            if term or trunc:
                break

        self.assertGreater(len(self.env.trajectory), 5)
        # Check first keyframe schema
        kf = self.env.trajectory[1]
        self.assertIn("pos_xyz", kf)
        self.assertIn("yaw_deg", kf)
        self.assertIn("skill", kf)
        self.assertIn("on_wheel", kf)

    def test_scripted_policy_decisions(self):
        """Verify ScriptedHomeostaticBaselinePolicy responds to physiological drive states."""
        policy = ScriptedHomeostaticBaselinePolicy()
        obs, _ = self.env.env.reset(seed=42)

        # High thirst -> drink
        obs.drives.thirst = 0.65
        skill_name = policy.select_skill(obs)
        self.assertEqual(skill_name, "drink")

        # High hunger -> approach_food or eat
        obs.drives.thirst = 0.05
        obs.drives.hunger = 0.70
        skill_name = policy.select_skill(obs)
        self.assertIn(skill_name, ["eat", "approach_food"])

        # High stress -> hide
        obs.drives.hunger = 0.05
        obs.drives.stress = 0.60
        skill_name = policy.select_skill(obs)
        self.assertEqual(skill_name, "hide")

    def test_ppo_actor_critic_model(self):
        """Verify PPO model forward pass, softmax normalization, and value output."""
        model = PPOActorCritic(obs_dim=41, act_dim=8, hidden_dim=64, seed=42)
        obs_batch = np.random.randn(4, 41).astype(np.float32)
        probs, values, _, _ = model.forward(obs_batch)
        self.assertEqual(probs.shape, (4, 8))
        self.assertEqual(values.shape, (4,))
        # Softmax check
        np.testing.assert_allclose(np.sum(probs, axis=-1), np.ones(4), atol=1e-5)

        # Single observation test
        single_obs = np.random.randn(41).astype(np.float32)
        act_idx, logp, val = model.sample_action(single_obs, deterministic=True)
        self.assertIn(act_idx, range(8))
        self.assertIsInstance(logp, float)
        self.assertIsInstance(val, float)


if __name__ == "__main__":
    unittest.main()
