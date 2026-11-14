"""
HAMMY — P1.5: Headless Skill-Outcome Dataset Collector (`simulation/skill_outcome_collector.py`).
Executes low-level controllers for all 8 skills across varied initial conditions:
  - Starting position & distance to target landmarks
  - Physiological drive states (hunger, thirst, energy, comfort, stress, curiosity)
  - Day/night circadian phases
  - Habitat arrangements
Logs:
  - success flag, duration (sec), energy cost, collision count, delta drives, final state
Saves dataset to Parquet format with version metadata (`environment_version="habitat_v1"`, `skill_version="v1"`).
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from contracts.schemas import ActionV1, BehaviourType, EventOrigin, ObservationV1
from simulation.habitat_env import HabitatEnv
from ai.policies.skills import SKILLS_BY_NAME, SKILL_NAMES, Skill

TARGET_PROPS = {
    "approach_food": "prop_bowl_main",
    "eat": "prop_bowl_main",
    "drink": "prop_bottle_main",
    "explore_area": "prop_chew_block_main",
    "rest": "prop_hideout_main",
    "hide": "prop_tunnel_main",
    "enter_tunnel": "prop_tunnel_main",
    "run_on_wheel": "prop_wheel_main",
}


def run_single_skill_rollout(
    env: HabitatEnv,
    skill: Skill,
    seed: int,
    sub_dt_sec: float = 2.0,
) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)

    # 1. Randomize agent initial position within cage
    rand_x = float(rng.uniform(-0.35, 0.35))
    rand_y = float(rng.uniform(-0.15, 0.15))
    rand_yaw = float(rng.uniform(-math.pi, math.pi))

    env.pos[0] = rand_x
    env.pos[1] = rand_y
    env.yaw = rand_yaw
    env.vel_xy.fill(0.0)
    env.ang_vel_z = 0.0

    # 2. Randomize initial drives
    env.drives.hunger = float(rng.uniform(0.05, 0.70))
    env.drives.thirst = float(rng.uniform(0.05, 0.65))
    env.drives.energy = float(rng.uniform(0.15, 0.95))
    env.drives.comfort = float(rng.uniform(0.40, 0.95))
    env.drives.stress = float(rng.uniform(0.02, 0.50))
    env.drives.curiosity = float(rng.uniform(0.05, 0.75))
    env.drives.circadian_phase = float(rng.uniform(0.0, 1.0))

    # For eating, place closer if testing eat skill so can_initiate passes often
    if skill.name == "eat":
        bowl_pos = env.objects_state["prop_bowl_main"]["pose_xyz_m"]
        offset = rng.uniform(-0.06, 0.06, size=2)
        env.pos[0] = float(bowl_pos[0] + offset[0])
        env.pos[1] = float(bowl_pos[1] + offset[1])

    obs_init = env._build_observation()

    # Determine initial distance to target landmark
    target_oid = TARGET_PROPS.get(skill.name)
    init_dist = 0.30
    if target_oid:
        for o in obs_init.nearby_objects:
            if o.object_id == target_oid:
                init_dist = o.distance_m
                break

    init_drives = {
        "hunger": obs_init.drives.hunger,
        "thirst": obs_init.drives.thirst,
        "energy": obs_init.drives.energy,
        "comfort": obs_init.drives.comfort,
        "stress": obs_init.drives.stress,
        "curiosity": obs_init.drives.curiosity,
        "circadian_phase": obs_init.drives.circadian_phase,
    }

    sub_steps = 0
    time_in_skill = 0.0
    collision_count = 0
    success = False
    cur_obs = obs_init

    # Fallback if cannot initiate
    if not skill.can_initiate(cur_obs):
        action = ActionV1(
            forward_speed_m_s=0.0,
            turn_rate_rad_s=0.0,
            interact_flag=False,
            behaviour_type=skill.behaviour_type,
        )
        next_obs, r, term, trunc, info = env.step(action)
        sub_steps = 1
        time_in_skill = sub_dt_sec
        cur_obs = next_obs
        success = False
    else:
        # Loop skill controller until termination condition
        while True:
            act = skill.step(cur_obs)
            next_obs, r, term, trunc, info = env.step(act)

            sub_steps += 1
            time_in_skill += sub_dt_sec

            # Check boundary collision (position clamped at borders)
            if abs(next_obs.position_xyz[0]) >= 0.450 or abs(next_obs.position_xyz[1]) >= 0.200:
                collision_count += 1

            # Check interaction successes
            interacts = info.get("interactions", {})
            if skill.name == "eat" and interacts.get("eating"):
                success = True
            elif skill.name == "drink" and interacts.get("drinking"):
                success = True
            elif skill.name == "rest" and (interacts.get("sleeping") or next_obs.inside_hideout):
                success = True
            elif skill.name == "hide" and (next_obs.inside_hideout or next_obs.inside_tunnel):
                success = True
            elif skill.name == "run_on_wheel" and next_obs.on_wheel:
                success = True
            elif skill.name == "approach_food":
                dist_bowl = [o.distance_m for o in next_obs.nearby_objects if o.object_id == "prop_bowl_main"]
                if dist_bowl and dist_bowl[0] <= 0.055:
                    success = True
            elif skill.name in ("explore_area", "enter_tunnel"):
                if time_in_skill >= 10.0:
                    success = True

            cur_obs = next_obs
            if term or trunc or skill.is_terminated(cur_obs, sub_steps, time_in_skill):
                break

    final_d = cur_obs.drives
    delta_hunger = final_d.hunger - init_drives["hunger"]
    delta_thirst = final_d.thirst - init_drives["thirst"]
    delta_energy = final_d.energy - init_drives["energy"]
    delta_comfort = final_d.comfort - init_drives["comfort"]
    delta_stress = final_d.stress - init_drives["stress"]
    delta_curiosity = final_d.curiosity - init_drives["curiosity"]

    energy_cost = max(0.0, -delta_energy)

    return {
        "skill_name": skill.name,
        "skill_version": "v1",
        "environment_version": "habitat_v1",
        "seed": seed,
        "init_dist_to_target_m": round(float(init_dist), 4),
        "init_hunger": round(float(init_drives["hunger"]), 4),
        "init_thirst": round(float(init_drives["thirst"]), 4),
        "init_energy": round(float(init_drives["energy"]), 4),
        "init_comfort": round(float(init_drives["comfort"]), 4),
        "init_stress": round(float(init_drives["stress"]), 4),
        "init_curiosity": round(float(init_drives["curiosity"]), 4),
        "init_circadian_phase": round(float(init_drives["circadian_phase"]), 4),
        "init_pos_x": round(float(rand_x), 4),
        "init_pos_y": round(float(rand_y), 4),
        "success": bool(success),
        "duration_sec": round(float(time_in_skill), 2),
        "sub_steps": int(sub_steps),
        "energy_cost": round(float(energy_cost), 4),
        "collision_count": int(collision_count),
        "delta_hunger": round(float(delta_hunger), 4),
        "delta_thirst": round(float(delta_thirst), 4),
        "delta_energy": round(float(delta_energy), 4),
        "delta_comfort": round(float(delta_comfort), 4),
        "delta_stress": round(float(delta_stress), 4),
        "delta_curiosity": round(float(delta_curiosity), 4),
        "final_pos_x": round(float(cur_obs.position_xyz[0]), 4),
        "final_pos_y": round(float(cur_obs.position_xyz[1]), 4),
        "final_inside_hideout": bool(cur_obs.inside_hideout),
        "final_inside_tunnel": bool(cur_obs.inside_tunnel),
        "final_on_wheel": bool(cur_obs.on_wheel),
        "final_cheek_pouch_fill": round(float(cur_obs.cheek_pouch_fill), 4),
    }


def collect_dataset(
    episodes_per_skill: int = 150,
    base_seed: int = 2026,
    output_path: str | Path = "simulation/datasets/skill_outcomes.parquet",
) -> pd.DataFrame:
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    env = HabitatEnv(max_episode_steps=5000, dt_sec=2.0)
    records = []

    print(f">> Collecting skill outcome dataset: {episodes_per_skill} rollouts x {len(SKILL_NAMES)} skills = {episodes_per_skill * len(SKILL_NAMES)} total rollouts...")

    count = 0
    for skill_name in SKILL_NAMES:
        skill = SKILLS_BY_NAME[skill_name]
        for i in range(episodes_per_skill):
            seed = base_seed + count
            # Every 30 rollouts, slightly rearrange habitat to introduce varied layouts
            if i % 30 == 0:
                env.reset(seed=seed)
                env.rearrange_habitat()
            else:
                env.reset(seed=seed)

            row = run_single_skill_rollout(env, skill, seed=seed)
            row["episode_id"] = count
            records.append(row)
            count += 1

    df = pd.DataFrame(records)
    # Save as standard Parquet
    df.to_parquet(out_file, engine="pyarrow", index=False)
    print(f">> Dataset successfully saved to {out_file} ({len(df)} rows, {len(df.columns)} columns)")
    return df


if __name__ == "__main__":
    collect_dataset()

