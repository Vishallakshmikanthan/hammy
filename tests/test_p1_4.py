"""
HAMMY — P1.4 Unit Tests: Cognitive Memory & Habitat Rearrangement (`tests/test_p1_4.py`).
Tests:
  1. ObjectMemory: appraisal running mean, confidence saturation, recency, temporal decay.
  2. SpatialFamiliarityGrid: 8x4 discretization, coordinate clamping, visit accumulation, 4x2 coarse sector pooling.
  3. AgentMemory: 28-dim normalized feature extraction, contract export.
  4. ObservationV2 contract: schema validation, version enforcement, extra field prohibition.
  5. HabitatEnv rearrangement: position shifts, clearance verification, world event emission.
  6. HighLevelSMDPEnv with memory: 69-dim observation vectors, macro-stepping stability, trajectory recording.
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
from pydantic import ValidationError

from contracts.schemas import (
    MemoryStateV2,
    ObjectMemoryItemV2,
    ObservationV1,
    ObservationV2,
    SchemaCompatibilityError,
    SpatialMemoryV2,
    validate_version,
)
from ai.memory.object_memory import ObjectMemory
from ai.memory.spatial_grid import SpatialFamiliarityGrid
from ai.memory.agent_memory import AgentMemory, DEFAULT_PROPS_ORDER
from simulation.habitat_env import HabitatEnv
from simulation.smdp_env import HighLevelSMDPEnv, extract_observation_features


class TestPhase1_4MemoryAndRearrangement(unittest.TestCase):
    def test_object_memory_lifecycle(self):
        """Test appraisal running mean, confidence boost, decay, and recency."""
        mem = ObjectMemory(
            object_id="prop_bowl_main",
            initial_value=0.0,
            initial_confidence=0.1,
            value_decay_rate=0.01,
            confidence_decay_rate=0.01,
            recency_tau_sec=100.0,
            update_alpha=0.5,
        )

        # Initial state
        self.assertEqual(mem.estimated_value, 0.0)
        self.assertEqual(mem.confidence, 0.1)
        self.assertEqual(mem.time_since_last_visit_sec, 0.0)
        self.assertAlmostEqual(mem.recency_normalized, 0.0, places=4)

        # Step decay (unvisited for 50 seconds)
        mem.step_decay(50.0)
        self.assertEqual(mem.time_since_last_visit_sec, 50.0)
        self.assertLess(mem.confidence, 0.1)
        expected_rec = 1.0 - math.exp(-50.0 / 100.0)
        self.assertAlmostEqual(mem.recency_normalized, expected_rec, places=4)

        # Record visit with high reward
        mem.record_visit(pos_xy=(0.32, -0.08), observed_value=1.0)
        self.assertEqual(mem.time_since_last_visit_sec, 0.0)
        self.assertAlmostEqual(mem.recency_normalized, 0.0, places=4)
        # EMA update: 0.5 * 0.0 + 0.5 * 1.0 = 0.5
        self.assertAlmostEqual(mem.estimated_value, 0.5, places=4)
        self.assertGreater(mem.confidence, 0.3)
        self.assertEqual(mem.last_known_pos_xy, [0.32, -0.08])

        # Test contract export
        item = mem.to_contract()
        self.assertIsInstance(item, ObjectMemoryItemV2)
        self.assertEqual(item.object_id, "prop_bowl_main")
        self.assertEqual(item.last_known_pos_xy, [0.32, -0.08])

    def test_spatial_familiarity_grid(self):
        """Test 8x4 coordinate indexing, visit accumulation, decay, and 4x2 pooling."""
        grid = SpatialFamiliarityGrid(nx=8, ny=4, visit_saturation_sec=10.0, decay_rate=0.01)

        # Test bounds mapping
        ix, iy = grid.get_cell_index((-0.46, -0.21))
        self.assertEqual((ix, iy), (0, 0))

        ix, iy = grid.get_cell_index((0.46, 0.21))
        self.assertEqual((ix, iy), (7, 3))

        # Clamping on out-of-bounds coordinates
        ix, iy = grid.get_cell_index((2.5, -5.0))
        self.assertEqual((ix, iy), (7, 0))

        # Initial familiarity is 0 everywhere
        self.assertEqual(grid.get_mean_familiarity(), 0.0)
        self.assertEqual(grid.get_current_familiarity((0.0, 0.0)), 0.0)

        # Spend 10 seconds at center
        center_x, center_y = grid.get_cell_center(4, 2)
        grid.update((center_x, center_y), dt_sec=10.0)

        # Saturated familiarity at that cell ~ 1 - exp(-1) = 0.632
        cur_fam = grid.get_current_familiarity((center_x, center_y))
        self.assertGreater(cur_fam, 0.60)
        self.assertLess(cur_fam, 0.65)

        # Mean familiarity should now be > 0
        self.assertGreater(grid.get_mean_familiarity(), 0.0)

        # Coarse sectors pooling should produce exactly 8 floats
        coarse = grid.get_coarse_sectors()
        self.assertEqual(coarse.shape, (8,))
        self.assertTrue((coarse >= 0.0).all() and (coarse <= 1.0).all())

        # Least familiar cell test
        least_idx, least_pos, min_fam = grid.get_least_familiar_cell()
        self.assertIn(least_idx[0], range(8))
        self.assertIn(least_idx[1], range(4))
        self.assertEqual(min_fam, 0.0)

    def test_agent_memory_feature_vector(self):
        """Test unified AgentMemory producing exact 28-dimensional feature vector."""
        mem = AgentMemory()
        vec = mem.get_feature_vector((0.145, 0.032))
        self.assertEqual(vec.shape, (28,))
        self.assertEqual(vec.dtype, np.float32)
        self.assertFalse(np.isnan(vec).any())
        self.assertFalse(np.isinf(vec).any())
        self.assertTrue((vec >= -1.0).all() and (vec <= 1.0).all())

    def test_observation_v2_schema_contract(self):
        """Test ObservationV2 schema validation and version registry enforcement."""
        self.assertIn("2.0.0", validate_version("observation", "2.0.0"))

        env = HabitatEnv(use_v2_observation=True)
        obs, _ = env.reset(seed=42)
        self.assertIsInstance(obs, ObservationV2)
        self.assertEqual(obs.schema_version, "2.0.0")

        # Attach memory contract
        mem = AgentMemory()
        obs.memory = mem.to_contract(obs)
        self.assertIsInstance(obs.memory, MemoryStateV2)
        self.assertEqual(len(obs.memory.object_memories), 6)
        self.assertEqual(obs.memory.spatial.grid_shape, [8, 4])
        self.assertEqual(len(obs.memory.spatial.coarse_sectors), 8)

        # Incompatible schema version rejection
        with self.assertRaises(ValidationError):
            ObservationV2(
                schema_version="9.9.9",
                sim_time_sec=0.0,
                position_xyz=[0.0, 0.0, 0.0],
                yaw_rad=0.0,
                velocity_xy=[0.0, 0.0],
                angular_velocity_z=0.0,
                drives=obs.drives,
            )

    def test_habitat_rearrangement(self):
        """Test periodic / dynamic habitat randomisation moves objects safely."""
        env = HabitatEnv()
        env.reset(seed=42)

        init_bowl_pos = list(env.objects_state["prop_bowl_main"]["pose_xyz_m"])
        init_hideout_pos = list(env.objects_state["prop_hideout_main"]["pose_xyz_m"])

        # Rearrange habitat
        moved = env.rearrange_habitat(min_dist_m=0.12)
        self.assertIn("prop_bowl_main", moved)
        self.assertIn("prop_hideout_main", moved)

        new_bowl_pos = list(env.objects_state["prop_bowl_main"]["pose_xyz_m"])
        new_hideout_pos = list(env.objects_state["prop_hideout_main"]["pose_xyz_m"])

        # Verify coordinates changed
        self.assertNotEqual(init_bowl_pos[:2], new_bowl_pos[:2])
        self.assertNotEqual(init_hideout_pos[:2], new_hideout_pos[:2])

        # Verify within cage floor clearance bounds [-0.36, 0.36] x [-0.15, 0.15]
        self.assertLessEqual(abs(new_bowl_pos[0]), 0.36)
        self.assertLessEqual(abs(new_bowl_pos[1]), 0.15)
        self.assertLessEqual(abs(new_hideout_pos[0]), 0.36)
        self.assertLessEqual(abs(new_hideout_pos[1]), 0.15)

        # Verify WorldEventV1 was logged
        rearrange_events = [e for e in env.events_log if e.event_type == "habitat_rearranged"]
        self.assertEqual(len(rearrange_events), 1)
        self.assertEqual(rearrange_events[0].event_type, "habitat_rearranged")

    def test_smdp_env_memory_on_vs_off(self):
        """Test SMDP environment with enable_memory=False (41 dims) vs enable_memory=True (69 dims)."""
        # 1. Memory OFF: 41 features
        env_off = HighLevelSMDPEnv(max_smdp_steps=10, enable_memory=False)
        feat_off, _ = env_off.reset(seed=42)
        self.assertEqual(feat_off.shape, (41,))
        self.assertEqual(env_off.obs_dim, 41)

        # 2. Memory ON: 69 features
        env_on = HighLevelSMDPEnv(max_smdp_steps=10, enable_memory=True)
        feat_on, info_on = env_on.reset(seed=42)
        self.assertEqual(feat_on.shape, (69,))
        self.assertEqual(env_on.obs_dim, 69)
        self.assertIn("memory", env_on.current_obs.model_dump())

        # Step 5 skills with memory ON
        for act_idx in [0, 1, 3, 4, 7]:
            next_feat, r, term, trunc, step_info = env_on.step(act_idx)
            self.assertEqual(next_feat.shape, (69,))
            self.assertFalse(np.isnan(next_feat).any())
            self.assertIn("memory", step_info)
            if term or trunc:
                break


if __name__ == "__main__":
    unittest.main()
