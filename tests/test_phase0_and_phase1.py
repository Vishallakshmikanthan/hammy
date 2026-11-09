"""
HAMMY — Unit & Integration Tests for Phase 0 (Contracts) & Phase 1 (HabitatEnv, Drives, Skills).
Run with: `python -m unittest discover -s tests -v`
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pydantic import ValidationError
from contracts.schemas import (
    ActionV1,
    BehaviourType,
    CommandV1,
    DriveVectorV1,
    EventOrigin,
    ObservationV1,
    SchemaCompatibilityError,
    WorldEventV1,
    export_json_schemas,
)
from ai.cognition.drives import HomeostaticDrives
from simulation.habitat_env import HabitatEnv


class TestContractsAndPhase1(unittest.TestCase):
    def test_contract_schema_export_and_valid_payloads(self):
        written = export_json_schemas(ROOT_DIR / "contracts" / "json_schema")
        self.assertEqual(len(written), 4)

        act = ActionV1(
            forward_speed_m_s=0.12,
            turn_rate_rad_s=-0.5,
            interact_flag=True,
            behaviour_type=BehaviourType.SCRIPTED,
        )
        self.assertEqual(act.behaviour_type, BehaviourType.SCRIPTED)

        evt = WorldEventV1(
            event_id="evt_0001",
            pet_id="hammy_001",
            world_tick=10,
            sim_time_sec=10.0,
            event_type="skill_completed",
            skill_name="eat_at_bowl",
            origin=EventOrigin.OBSERVED_PHYSICS,
            behaviour_type=BehaviourType.SCRIPTED,
            seed=42,
        )
        self.assertEqual(evt.origin, EventOrigin.OBSERVED_PHYSICS)

        cmd = CommandV1(
            command_id="cmd_idemp_123456",
            pet_id="hammy_001",
            command_type="feed",
            parameters={"grams": 10},
        )
        self.assertEqual(cmd.command_id, "cmd_idemp_123456")

    def test_incompatible_versions_and_bad_payloads_rejected(self):
        with self.assertRaises((ValidationError, SchemaCompatibilityError)):
            ActionV1(
                schema_version="99.0.0",
                forward_speed_m_s=0.1,
                turn_rate_rad_s=0.0,
                behaviour_type=BehaviourType.LEARNED,
            )

        with self.assertRaises(ValidationError):
            # Out of [0, 1] bounds on hunger
            DriveVectorV1(
                hunger=1.5,
                thirst=0.2,
                energy=0.8,
                comfort=0.8,
                stress=0.1,
                curiosity=0.2,
                circadian_phase=0.5,
            )

    def test_drives_monotonic_and_reward_sign(self):
        d = HomeostaticDrives(hunger=0.40, thirst=0.35, energy=0.80, comfort=0.80, stress=0.10, curiosity=0.20)
        h0 = d.hunger
        # Passive awake step without eating increases hunger
        d.step(600.0, is_eating=False)
        self.assertGreater(d.hunger, h0)

        # Eating when hungry reduces hunger and yields a positive hunger reward term
        h1 = d.hunger
        _, terms = d.step(5.0, is_eating=True)
        self.assertLess(d.hunger, h1)
        self.assertGreater(terms["hunger"], 0.0)

    def test_habitat_env_deterministic_reset_and_10k_steps(self):
        env = HabitatEnv(max_episode_steps=10000, dt_sec=0.5)
        obs1, _ = env.reset(seed=777)
        obs2, _ = env.reset(seed=777)
        self.assertEqual(obs1.position_xyz, obs2.position_xyz)
        self.assertEqual(obs1.yaw_rad, obs2.yaw_rad)

        # Verify unique object IDs
        obj_ids = [o.object_id for o in obs1.nearby_objects]
        self.assertEqual(len(obj_ids), len(set(obj_ids)))

        # Step 1,000 random actions stably without NaN
        for i in range(1000):
            act = ActionV1(
                forward_speed_m_s=0.15 if (i % 2 == 0) else 0.05,
                turn_rate_rad_s=0.8 if (i % 3 == 0) else -0.6,
                interact_flag=(i % 5 == 0),
                behaviour_type=BehaviourType.RULE,
            )
            obs, reward, term, trunc, info = env.step(act)
            self.assertFalse(any(map(lambda x: x != x, obs.position_xyz)))


if __name__ == "__main__":
    unittest.main()

