"""
HAMMY — P1.3: Semi-Markov Decision Process (SMDP) High-Level Environment (`simulation/smdp_env.py`).
Implements a semi-Markov environment where:
  - One high-level step = one skill execution (variable duration tau >= 1 sub-steps).
  - Low-level stepping runs in `HabitatEnv` using the skill's low-level controller.
  - Sub-steps accumulate true homeostatic rewards: R = sum_{t=0}^{tau-1} r_t.
  - Returns compact normalized observation feature vectors, cumulative reward, termination flags,
    and trajectory keyframes for rendering in Blender.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from contracts.schemas import ActionV1, ObservationV1, ObservationV2
from simulation.habitat_env import HabitatEnv
from ai.policies.skills import SKILLS_LIST, SKILL_NAMES, Skill
from ai.memory.agent_memory import AgentMemory


PROPS_ORDER = [
    "prop_bowl_main",
    "prop_bottle_main",
    "prop_hideout_main",
    "prop_tunnel_main",
    "prop_wheel_main",
    "prop_chew_block_main",
]


def extract_observation_features(
    obs: ObservationV1 | ObservationV2,
    memory: Optional[AgentMemory] = None,
) -> np.ndarray:
    """
    Extracts a normalized numerical feature vector from `ObservationV1` (41 dims)
    or `ObservationV2` with cognitive memory features (69 dims)
    for neural network / high-level policy inference.
    """
    feats = []
    # 1. Drives (7 floats in [0, 1])
    d = obs.drives
    feats.extend([d.hunger, d.thirst, d.energy, d.comfort, d.stress, d.curiosity, d.circadian_phase])

    # 2. Key habitat objects relative pose & distance (6 props * 4 = 24 floats)
    obj_map = {o.object_id: o for o in obs.nearby_objects}
    for pid in PROPS_ORDER:
        if pid in obj_map:
            o = obj_map[pid]
            feats.extend([o.rel_pos_xy[0] / 0.50, o.rel_pos_xy[1] / 0.25, o.distance_m / 0.60, o.resource_level])
        else:
            feats.extend([0.0, 0.0, 1.0, 0.0])

    # 3. Agent physical & interaction state (10 floats)
    feats.extend([
        obs.position_xyz[0] / 0.50,
        obs.position_xyz[1] / 0.25,
        math.cos(obs.yaw_rad),
        math.sin(obs.yaw_rad),
        obs.velocity_xy[0] / 0.30,
        obs.velocity_xy[1] / 0.30,
        1.0 if obs.inside_hideout else 0.0,
        1.0 if obs.inside_tunnel else 0.0,
        1.0 if obs.on_wheel else 0.0,
        obs.cheek_pouch_fill,
    ])

    # 4. Cognitive memory features (28 floats, if memory is provided or present in obs)
    if memory is not None:
        mem_vec = memory.get_feature_vector(obs.position_xyz[:2])
        feats.extend(mem_vec.tolist())
    elif isinstance(obs, ObservationV2) and obs.memory is not None:
        m = obs.memory
        mem_obj_map = {item.object_id: item for item in m.object_memories}
        for pid in PROPS_ORDER:
            if pid in mem_obj_map:
                it = mem_obj_map[pid]
                feats.extend([it.estimated_value, it.confidence, it.recency_normalized])
            else:
                feats.extend([0.0, 0.0, 1.0])
        feats.append(m.spatial.current_cell_familiarity)
        feats.append(m.spatial.mean_familiarity)
        feats.extend(m.spatial.coarse_sectors)

    return np.array(feats, dtype=np.float32)


class HighLevelSMDPEnv:
    """
    Semi-Markov Decision Process Environment for HAMMY High-Level Policies.
    Action Space: Discrete(len(SKILLS_LIST)) = 8 skills.
    Observation Space:
      - enable_memory=False: Box(shape=(41,), dtype=np.float32) from ObservationV1
      - enable_memory=True: Box(shape=(69,), dtype=np.float32) from ObservationV2 + AgentMemory
    """

    def __init__(
        self,
        max_smdp_steps: int = 500,
        sub_dt_sec: float = 2.0,
        record_trajectory: bool = False,
        enable_memory: bool = False,
        rearrange_interval_smdp_steps: Optional[int] = None,
    ):
        self.max_smdp_steps = int(max_smdp_steps)
        self.sub_dt_sec = float(sub_dt_sec)
        self.record_trajectory = bool(record_trajectory)
        self.enable_memory = bool(enable_memory)
        self.rearrange_interval_smdp_steps = rearrange_interval_smdp_steps

        self.skills: List[Skill] = list(SKILLS_LIST)
        self.num_actions = len(self.skills)
        self.obs_dim = 69 if self.enable_memory else 41

        self.memory: Optional[AgentMemory] = AgentMemory() if self.enable_memory else None

        # Max sub-steps per episode in low-level environment
        max_low_level_steps = max_smdp_steps * 1000
        self.env = HabitatEnv(
            max_episode_steps=max_low_level_steps,
            dt_sec=self.sub_dt_sec,
            use_v2_observation=self.enable_memory,
        )

        self.current_obs: Optional[ObservationV1 | ObservationV2] = None
        self.smdp_step_count = 0
        self.total_sim_time = 0.0
        self.trajectory: List[Dict[str, Any]] = []

    def reset(self, *, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        self.smdp_step_count = 0
        self.total_sim_time = 0.0
        self.trajectory = []

        if self.memory is not None:
            self.memory.reset()

        obs, info = self.env.reset(seed=seed)
        if self.memory is not None:
            self.memory.update(obs, dt_sec=0.0)
            if isinstance(obs, ObservationV2):
                obs.memory = self.memory.to_contract(obs)

        self.current_obs = obs

        if self.record_trajectory:
            self._record_keyframe(obs, skill_name="init", interact_flags={})

        features = extract_observation_features(obs, memory=self.memory)
        return features, info

    def _record_keyframe(self, obs: ObservationV1 | ObservationV2, skill_name: str, interact_flags: Dict[str, bool]):
        self.trajectory.append({
            "sim_time_sec": round(obs.sim_time_sec, 2),
            "pos_xyz": [round(v, 4) for v in obs.position_xyz],
            "yaw_rad": round(obs.yaw_rad, 4),
            "yaw_deg": round(math.degrees(obs.yaw_rad), 2),
            "skill": skill_name,
            "on_wheel": obs.on_wheel,
            "inside_hideout": obs.inside_hideout,
            "inside_tunnel": obs.inside_tunnel,
            "cheek_pouch_fill": obs.cheek_pouch_fill,
            "eating": interact_flags.get("eating", False),
            "drinking": interact_flags.get("drinking", False),
            "sleeping": interact_flags.get("sleeping", False),
        })

    def step(self, action_idx: int) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        if self.current_obs is None:
            raise RuntimeError("Call reset() before step().")

        action_idx = int(action_idx) % self.num_actions
        skill = self.skills[action_idx]
        self.smdp_step_count += 1

        cumulative_reward = 0.0
        sub_steps = 0
        time_in_skill = 0.0
        sub_terminated = False
        sub_truncated = False
        last_info: Dict[str, Any] = {}

        # Fallback initiation check
        if not skill.can_initiate(self.current_obs):
            # Cannot initiate: take 1 idle sub-step and penalize opportunity cost
            action = ActionV1(
                forward_speed_m_s=0.0,
                turn_rate_rad_s=0.0,
                interact_flag=False,
                behaviour_type=skill.behaviour_type,
            )
            next_obs, r, sub_term, sub_trunc, last_info = self.env.step(action)
            cumulative_reward += (r - 0.02)
            sub_steps = 1
            time_in_skill = self.sub_dt_sec

            if self.memory is not None:
                self.memory.update(
                    next_obs,
                    dt_sec=self.sub_dt_sec,
                    reward=r,
                    interactions=last_info.get("interactions", {}),
                )
                if isinstance(next_obs, ObservationV2):
                    next_obs.memory = self.memory.to_contract(next_obs)

            self.current_obs = next_obs
            sub_terminated = sub_term
            sub_truncated = sub_trunc
            if self.record_trajectory:
                self._record_keyframe(next_obs, skill.name, last_info.get("interactions", {}))
        else:
            # Execute the skill options controller loop: guaranteed at least 1 sub-step
            while True:
                action = skill.step(self.current_obs)
                next_obs, r, sub_term, sub_trunc, last_info = self.env.step(action)

                cumulative_reward += r
                sub_steps += 1
                time_in_skill += self.sub_dt_sec

                if self.memory is not None:
                    self.memory.update(
                        next_obs,
                        dt_sec=self.sub_dt_sec,
                        reward=r,
                        interactions=last_info.get("interactions", {}),
                    )
                    if isinstance(next_obs, ObservationV2):
                        next_obs.memory = self.memory.to_contract(next_obs)

                self.current_obs = next_obs

                if self.record_trajectory:
                    self._record_keyframe(next_obs, skill.name, last_info.get("interactions", {}))

                if sub_term or sub_trunc or skill.is_terminated(self.current_obs, sub_steps, time_in_skill):
                    sub_terminated = sub_term
                    sub_truncated = sub_trunc
                    break

        rearranged = None
        if self.rearrange_interval_smdp_steps and (self.smdp_step_count % self.rearrange_interval_smdp_steps == 0):
            rearranged = self.env.rearrange_habitat()

        self.total_sim_time += time_in_skill
        features = extract_observation_features(self.current_obs, memory=self.memory)

        terminated = sub_terminated
        truncated = sub_truncated or bool(self.smdp_step_count >= self.max_smdp_steps)

        smdp_info = {
            "smdp_step": self.smdp_step_count,
            "skill_name": skill.name,
            "skill_idx": action_idx,
            "sub_steps": sub_steps,
            "duration_sec": time_in_skill,
            "sim_time_sec": self.current_obs.sim_time_sec,
            "healthy_flags": self.env.drives.in_healthy_range_flags(),
            "drives": self.current_obs.drives.model_dump(),
            "trajectory_len": len(self.trajectory),
            "rearranged_objects": rearranged,
        }
        if self.memory is not None:
            smdp_info["memory"] = self.memory.to_contract(self.current_obs).model_dump()

        return features, float(cumulative_reward), terminated, truncated, smdp_info
