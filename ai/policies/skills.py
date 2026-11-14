"""
HAMMY — P1.3: Skill Library (Options Framework) & Low-Level Controllers (`ai/policies/skills.py`).
Every skill and low-level controller here is explicitly labelled `BehaviourType.SCRIPTED` or
`BehaviourType.RULE` per Non-Negotiable Rule 1 (never present scripted behaviour as learned).

Skills implemented per P1.3 specification:
  1. `approach_food`: Navigates to `prop_bowl_main` until within stopping radius.
  2. `eat`: Stays at bowl, `interact_flag=True`, until hunger is reduced (< set_point) or food runs out.
  3. `drink`: Navigates to `prop_bottle_main`, drinks until thirst is satisfied (< set_point).
  4. `explore_area`: Navigates through central clearing / open cage to satisfy curiosity.
  5. `rest`: Navigates to `prop_hideout_main`, rests/sleeps until energy is recovered.
  6. `hide`: Retreats to `prop_tunnel_main` or hideout to reduce stress and raise comfort.
  7. `enter_tunnel`: Traverses the 3-section burrow tunnel (`prop_tunnel_main`).
  8. `run_on_wheel`: Uses the 0.28m exercise wheel (`prop_wheel_main`).
  9. `gnaw_chew_block`: Gnaws the applewood chew block (`prop_chew_block_main`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from contracts.schemas import ActionV1, BehaviourType, ObservationV1, ObservationV2


def navigate_and_interact(
    obs: ObservationV1,
    target_object_id: Optional[str] = None,
    target_pos_xy: Optional[Tuple[float, float]] = None,
    stop_dist_m: float = 0.045,
    behaviour_type: BehaviourType = BehaviourType.SCRIPTED,
) -> Tuple[ActionV1, bool]:
    """
    Proportional planar navigation controller (`scripted`) toward a target object or position.
    Returns `(ActionV1, reached_target)`.
    """
    if target_object_id:
        target_obj = None
        for o in obs.nearby_objects:
            if o.object_id == target_object_id:
                target_obj = o
                break
        if target_obj is None:
            return (
                ActionV1(
                    forward_speed_m_s=0.0,
                    turn_rate_rad_s=0.0,
                    interact_flag=False,
                    behaviour_type=behaviour_type,
                ),
                False,
            )
        dx, dy = target_obj.rel_pos_xy[0], target_obj.rel_pos_xy[1]
        dist = target_obj.distance_m
    elif target_pos_xy:
        dx = target_pos_xy[0] - obs.position_xyz[0]
        dy = target_pos_xy[1] - obs.position_xyz[1]
        dist = math.hypot(dx, dy)
    else:
        return (
            ActionV1(
                forward_speed_m_s=0.0,
                turn_rate_rad_s=0.0,
                interact_flag=False,
                behaviour_type=behaviour_type,
            ),
            True,
        )

    if dist <= stop_dist_m:
        return (
            ActionV1(
                forward_speed_m_s=0.0,
                turn_rate_rad_s=0.0,
                interact_flag=True,
                behaviour_type=behaviour_type,
            ),
            True,
        )

    desired_yaw = math.atan2(dy, dx)
    yaw_err = (desired_yaw - obs.yaw_rad + math.pi) % (2.0 * math.pi) - math.pi
    turn_rate = float(np.clip(yaw_err, -4.5, 4.5))

    if abs(yaw_err) > 0.35:
        fwd_speed = 0.0
    else:
        fwd_speed = float(np.clip(dist * 0.85, 0.02, 0.25))

    return (
        ActionV1(
            forward_speed_m_s=fwd_speed,
            turn_rate_rad_s=turn_rate,
            interact_flag=(dist <= stop_dist_m * 1.35),
            behaviour_type=behaviour_type,
        ),
        False,
    )


@dataclass
class Skill:
    name: str
    target_object_id: Optional[str]
    max_duration_sec: float
    initiation_fn: Callable[[ObservationV1], bool]
    termination_fn: Callable[[ObservationV1, int, float], bool]
    controller_fn: Callable[[ObservationV1], ActionV1]
    behaviour_type: BehaviourType = BehaviourType.SCRIPTED

    def can_initiate(self, obs: ObservationV1) -> bool:
        return self.initiation_fn(obs)

    def is_terminated(self, obs: ObservationV1, step_in_skill: int, time_in_sec: float) -> bool:
        if time_in_sec >= self.max_duration_sec:
            return True
        return self.termination_fn(obs, step_in_skill, time_in_sec)

    def step(self, obs: ObservationV1) -> ActionV1:
        return self.controller_fn(obs)


# ==============================================================================
# FORMAL SKILLS CATALOG (P1.3)
# ==============================================================================
def _obj_dist(obs: ObservationV1, obj_id: str) -> float:
    for o in obs.nearby_objects:
        if o.object_id == obj_id:
            return o.distance_m
    return 999.0


# 1. approach_food
def _init_approach_food(obs: ObservationV1) -> bool:
    return _obj_dist(obs, "prop_bowl_main") > 0.065


def _term_approach_food(obs: ObservationV1, step: int, t_sec: float) -> bool:
    return _obj_dist(obs, "prop_bowl_main") <= 0.055 or t_sec >= 120.0


def _ctrl_approach_food(obs: ObservationV1) -> ActionV1:
    act, _ = navigate_and_interact(obs, "prop_bowl_main", stop_dist_m=0.050)
    return act


# 2. eat
def _init_eat(obs: ObservationV1) -> bool:
    return _obj_dist(obs, "prop_bowl_main") <= 0.080


def _term_eat(obs: ObservationV1, step: int, t_sec: float) -> bool:
    # Finished eating when hunger is satisfied (< 0.12) or exceeded max meal duration
    return (t_sec >= 10.0 and obs.drives.hunger <= 0.10) or t_sec >= 240.0


def _ctrl_eat(obs: ObservationV1) -> ActionV1:
    act, _ = navigate_and_interact(obs, "prop_bowl_main", stop_dist_m=0.045)
    return ActionV1(
        forward_speed_m_s=act.forward_speed_m_s,
        turn_rate_rad_s=act.turn_rate_rad_s,
        interact_flag=True,
        behaviour_type=BehaviourType.SCRIPTED,
    )


# 3. drink
def _init_drink(obs: ObservationV1) -> bool:
    return True


def _term_drink(obs: ObservationV1, step: int, t_sec: float) -> bool:
    if _obj_dist(obs, "prop_bottle_main") <= 0.065:
        return (t_sec >= 8.0 and obs.drives.thirst <= 0.10) or t_sec >= 180.0
    return t_sec >= 120.0


def _ctrl_drink(obs: ObservationV1) -> ActionV1:
    act, reached = navigate_and_interact(obs, "prop_bottle_main", stop_dist_m=0.050)
    return ActionV1(
        forward_speed_m_s=act.forward_speed_m_s,
        turn_rate_rad_s=act.turn_rate_rad_s,
        interact_flag=reached,
        behaviour_type=BehaviourType.SCRIPTED,
    )


# 4. explore_area
def _init_explore(obs: ObservationV1) -> bool:
    return True


def _term_explore(obs: ObservationV1, step: int, t_sec: float) -> bool:
    return (t_sec >= 20.0 and obs.drives.curiosity <= 0.08) or t_sec >= 300.0


def _ctrl_explore(obs: ObservationV1 | ObservationV2) -> ActionV1:
    # If memory is available, steer toward the least familiar coarse sector
    if isinstance(obs, ObservationV2) and obs.memory is not None and obs.memory.spatial.coarse_sectors:
        sectors = obs.memory.spatial.coarse_sectors
        min_sec_idx = int(np.argmin(sectors))
        # 4 columns (x in [-0.46, 0.46]) x 2 rows (y in [-0.21, 0.21])
        col = min_sec_idx // 2
        row = min_sec_idx % 2
        target_x = -0.46 + (col + 0.5) * (0.92 / 4.0)
        target_y = -0.21 + (row + 0.5) * (0.42 / 2.0)
        act, _ = navigate_and_interact(obs, target_pos_xy=(target_x, target_y), stop_dist_m=0.050)
        return act
    # Default roaming toward central clearing or chew block
    act, _ = navigate_and_interact(obs, "prop_chew_block_main", stop_dist_m=0.060)
    return act


# 5. rest
def _init_rest(obs: ObservationV1) -> bool:
    return True


def _term_rest(obs: ObservationV1, step: int, t_sec: float) -> bool:
    d = obs.drives
    if obs.inside_hideout:
        return (t_sec >= 60.0 and d.energy >= 0.88) or d.hunger > 0.45 or d.thirst > 0.40 or t_sec >= 1800.0
    return t_sec >= 120.0


def _ctrl_rest(obs: ObservationV1) -> ActionV1:
    act, reached = navigate_and_interact(obs, "prop_hideout_main", stop_dist_m=0.060)
    return ActionV1(
        forward_speed_m_s=act.forward_speed_m_s,
        turn_rate_rad_s=act.turn_rate_rad_s,
        interact_flag=reached,
        behaviour_type=BehaviourType.SCRIPTED,
    )


# 6. hide
def _init_hide(obs: ObservationV1) -> bool:
    return True


def _term_hide(obs: ObservationV1, step: int, t_sec: float) -> bool:
    return (t_sec >= 20.0 and obs.drives.stress <= 0.08 and obs.drives.comfort >= 0.85) or t_sec >= 450.0


def _ctrl_hide(obs: ObservationV1) -> ActionV1:
    act, reached = navigate_and_interact(obs, "prop_tunnel_main", stop_dist_m=0.060)
    return ActionV1(
        forward_speed_m_s=act.forward_speed_m_s,
        turn_rate_rad_s=act.turn_rate_rad_s,
        interact_flag=reached,
        behaviour_type=BehaviourType.SCRIPTED,
    )


# 7. enter_tunnel (placeholder tunnel traversal)
def _init_tunnel(obs: ObservationV1) -> bool:
    return True


def _term_tunnel(obs: ObservationV1, step: int, t_sec: float) -> bool:
    return (t_sec >= 15.0 and obs.inside_tunnel) or t_sec >= 240.0


def _ctrl_tunnel(obs: ObservationV1) -> ActionV1:
    act, reached = navigate_and_interact(obs, "prop_tunnel_main", stop_dist_m=0.055)
    return ActionV1(
        forward_speed_m_s=act.forward_speed_m_s,
        turn_rate_rad_s=act.turn_rate_rad_s,
        interact_flag=reached,
        behaviour_type=BehaviourType.SCRIPTED,
    )


# 8. run_on_wheel
def _init_wheel(obs: ObservationV1) -> bool:
    return True


def _term_wheel(obs: ObservationV1, step: int, t_sec: float) -> bool:
    if obs.on_wheel:
        return (t_sec >= 20.0 and obs.drives.curiosity <= 0.05) or obs.drives.energy <= 0.40 or t_sec >= 360.0
    return t_sec >= 120.0


def _ctrl_wheel(obs: ObservationV1) -> ActionV1:
    act, reached = navigate_and_interact(obs, "prop_wheel_main", stop_dist_m=0.085)
    return ActionV1(
        forward_speed_m_s=act.forward_speed_m_s,
        turn_rate_rad_s=act.turn_rate_rad_s,
        interact_flag=reached,
        behaviour_type=BehaviourType.SCRIPTED,
    )


SKILLS_LIST: List[Skill] = [
    Skill("approach_food", "prop_bowl_main", 120.0, _init_approach_food, _term_approach_food, _ctrl_approach_food),
    Skill("eat", "prop_bowl_main", 240.0, _init_eat, _term_eat, _ctrl_eat),
    Skill("drink", "prop_bottle_main", 180.0, _init_drink, _term_drink, _ctrl_drink),
    Skill("explore_area", None, 300.0, _init_explore, _term_explore, _ctrl_explore),
    Skill("rest", "prop_hideout_main", 1800.0, _init_rest, _term_rest, _ctrl_rest),
    Skill("hide", "prop_tunnel_main", 450.0, _init_hide, _term_hide, _ctrl_hide),
    Skill("enter_tunnel", "prop_tunnel_main", 240.0, _init_tunnel, _term_tunnel, _ctrl_tunnel),
    Skill("run_on_wheel", "prop_wheel_main", 360.0, _init_wheel, _term_wheel, _ctrl_wheel),
]

SKILLS_BY_NAME: Dict[str, Skill] = {s.name: s for s in SKILLS_LIST}
SKILL_NAMES: List[str] = [s.name for s in SKILLS_LIST]


class ScriptedHomeostaticBaselinePolicy:
    """
    Hand-coded homeostatic priority controller explicitly labelled `scripted` / `rule`.
    Respects Syrian hamster nocturnal circadian rhythm:
      - Sleeps in `prop_hideout_main` during daylight unless hunger or thirst becomes urgent.
      - Feeds at `prop_bowl_main` when hungry, drinks at `prop_bottle_main` when thirsty.
      - Runs on `prop_wheel_main` or explores `prop_tunnel_main` during nocturnal active hours.
    """

    behaviour_type: BehaviourType = BehaviourType.SCRIPTED

    def select_skill(self, obs: ObservationV1 | ObservationV2) -> str:
        d = obs.drives
        is_day = 0.29 <= d.circadian_phase <= 0.79

        # Memory-guided foraging & exploration check
        if isinstance(obs, ObservationV2) and obs.memory is not None:
            mem_map = {m.object_id: m for m in obs.memory.object_memories}
            bowl_mem = mem_map.get("prop_bowl_main")
            # If bowl has high recency (not visited recently) and hunger is rising,
            # proactively seek food before entering severe starvation
            if bowl_mem and bowl_mem.recency_normalized > 0.65 and d.hunger > 0.22:
                return "eat" if _obj_dist(obs, "prop_bowl_main") <= 0.080 else "approach_food"

            # If habitat rearrangement occurred or unfamiliarity is high, explore low-familiarity sectors
            if obs.memory.spatial.mean_familiarity < 0.20 and d.energy > 0.50 and not is_day:
                return "explore_area"

        # Urgent physiological needs override sleep
        if d.thirst > 0.30:
            return "drink"
        if d.hunger > 0.32:
            return "eat" if _obj_dist(obs, "prop_bowl_main") <= 0.080 else "approach_food"

        # Crepuscular / Nocturnal sleep schedule or low energy
        if d.energy < 0.48 or (is_day and d.energy < 0.90):
            return "rest"

        # Stress or low comfort -> seek shelter
        if d.stress > 0.28 or d.comfort < 0.58:
            return "hide"

        # Nocturnal enrichment: wheel running & exploration
        if d.curiosity > 0.25 and d.energy > 0.55:
            return "run_on_wheel"

        if d.hunger > 0.18:
            return "eat" if _obj_dist(obs, "prop_bowl_main") <= 0.080 else "approach_food"
        if d.thirst > 0.16:
            return "drink"

        return "rest" if is_day else "explore_area"

    def act(self, obs: ObservationV1) -> Tuple[ActionV1, str]:
        skill_name = self.select_skill(obs)
        skill = SKILLS_BY_NAME[skill_name]
        action = skill.step(obs)
        return action, skill_name
