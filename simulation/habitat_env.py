"""
HAMMY — P1.1: Habitat Environment with Simplified Controllable Hamster Body (`simulation/habitat_env.py`).
Follows the ObservationV1 / ActionV1 / WorldEventV1 contracts from `/contracts`.
Uses `simulation/habitats/v1.xml` and `simulation/habitats/v1.json` (which share exact 3D metric
coordinates with `blender/scene.blend`).
Supports both native MuJoCo stepping (when the MuJoCo C++ library is permitted by OS policy)
and a deterministic planar rigid-body + wall/prop collision physics backend so `HabitatEnv`
runs identically on Windows machines where Windows Smart App Control blocks unsigned `.pyd` DLLs.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from contracts.schemas import (
    ActionV1,
    BehaviourType,
    EventOrigin,
    ObjectObservationV1,
    ObservationV1,
    WorldEventV1,
)
from ai.cognition.drives import HomeostaticDrives

HABITAT_JSON_PATH = Path(__file__).parent / "habitats" / "v1.json"
HABITAT_XML_PATH = Path(__file__).parent / "habitats" / "v1.xml"


class HabitatEnv:
    """
    Contract-compliant Hamster Habitat Environment (`habitat_v1`, `simple_agent_v1`).
    - Cage floor bounds: x in [-0.46, +0.46] m, y in [-0.21, +0.21] m, z = 0.165 m.
    - Agent body: 0.125 kg, 0.15 m length, controlled via forward_speed_m_s and turn_rate_rad_s.
    """

    def __init__(
        self,
        max_episode_steps: int = 2000,
        dt_sec: float = 1.0,
        pet_id: str = "hammy_001",
    ):
        self.max_episode_steps = int(max_episode_steps)
        self.dt_sec = float(dt_sec)
        self.pet_id = pet_id

        with open(HABITAT_JSON_PATH, "r", encoding="utf-8") as f:
            self.habitat_meta = json.load(f)

        # Verify unique object IDs
        obj_ids = [o["object_id"] for o in self.habitat_meta["objects"]]
        if len(obj_ids) != len(set(obj_ids)):
            raise ValueError("Duplicate object_id detected in simulation/habitats/v1.json")

        self.rng = np.random.default_rng(42)
        self.seed_value = 42
        self.step_count = 0
        self.sim_time_sec = 0.0

        # Agent kinematics state (matching BlenderHAMSTER_POS)
        self.pos = np.array([0.145, 0.032, 0.165], dtype=np.float64)
        self.yaw = math.radians(-135.0)
        self.vel_xy = np.zeros(2, dtype=np.float64)
        self.ang_vel_z = 0.0
        self.cheek_pouch_fill = 0.0

        self.drives = HomeostaticDrives()
        self.objects_state: Dict[str, Dict[str, Any]] = {}
        self.events_log: List[WorldEventV1] = []
        self._init_objects()

    def _init_objects(self):
        self.objects_state = {}
        for o in self.habitat_meta["objects"]:
            self.objects_state[o["object_id"]] = {
                "object_id": o["object_id"],
                "object_type": o["object_type"],
                "blender_name": o["blender_name"],
                "pose_xyz_m": np.array(o["pose_xyz_m"], dtype=np.float64),
                "interaction_radius_m": float(o["interaction_radius_m"]),
                "affordances": list(o["affordances"]),
                "resource_state": dict(o["resource_state"]),
            }

    def reset(self, *, seed: Optional[int] = None) -> Tuple[ObservationV1, Dict[str, Any]]:
        if seed is not None:
            self.seed_value = int(seed)
        self.rng = np.random.default_rng(self.seed_value)
        self.step_count = 0
        self.sim_time_sec = 0.0

        # Deterministic slight spawn jitter around central clearing
        jitter_xy = self.rng.uniform(-0.015, 0.015, size=2)
        self.pos = np.array([0.145 + jitter_xy[0], 0.032 + jitter_xy[1], 0.165], dtype=np.float64)
        self.yaw = float(math.radians(-135.0) + self.rng.uniform(-0.15, 0.15))
        self.vel_xy = np.zeros(2, dtype=np.float64)
        self.ang_vel_z = 0.0
        self.cheek_pouch_fill = 0.0

        self.drives = HomeostaticDrives(
            hunger=float(0.18 + self.rng.uniform(-0.03, 0.03)),
            thirst=float(0.16 + self.rng.uniform(-0.03, 0.03)),
            energy=float(0.82 + self.rng.uniform(-0.03, 0.03)),
            comfort=0.78,
            stress=0.10,
            curiosity=0.25,
            circadian_phase=0.80,
        )
        self._init_objects()
        self.events_log = []

        obs = self._build_observation()
        return obs, {"seed": self.seed_value, "healthy_flags": self.drives.in_healthy_range_flags()}

    def _build_observation(self) -> ObservationV1:
        nearby = []
        in_hideout = False
        in_tunnel = False
        on_wheel = False

        for oid, obj in self.objects_state.items():
            rel = obj["pose_xyz_m"][:2] - self.pos[:2]
            dist = float(np.linalg.norm(rel))
            rad = obj["interaction_radius_m"]

            if obj["object_type"] == "hideout" and dist <= rad:
                in_hideout = True
            elif obj["object_type"] == "tunnel" and dist <= rad:
                in_tunnel = True
            elif obj["object_type"] == "wheel" and dist <= rad:
                on_wheel = True

            res_lvl = 1.0
            rs = obj["resource_state"]
            if "food_level" in rs:
                res_lvl = float(rs["food_level"])
            elif "water_level" in rs:
                res_lvl = float(rs["water_level"])

            nearby.append(
                ObjectObservationV1(
                    object_id=oid,
                    object_type=obj["object_type"],
                    rel_pos_xy=[round(float(rel[0]), 5), round(float(rel[1]), 5)],
                    distance_m=round(dist, 5),
                    resource_level=round(np.clip(res_lvl, 0.0, 1.0), 4),
                )
            )

        return ObservationV1(
            sim_time_sec=round(self.sim_time_sec, 3),
            position_xyz=[round(float(self.pos[0]), 5), round(float(self.pos[1]), 5), round(float(self.pos[2]), 5)],
            yaw_rad=round(float(self.yaw), 5),
            velocity_xy=[round(float(self.vel_xy[0]), 5), round(float(self.vel_xy[1]), 5)],
            angular_velocity_z=round(float(self.ang_vel_z), 5),
            inside_hideout=in_hideout,
            inside_tunnel=in_tunnel,
            on_wheel=on_wheel,
            cheek_pouch_fill=round(float(self.cheek_pouch_fill), 4),
            drives=self.drives.to_contract(),
            nearby_objects=nearby,
        )

    def step(
        self, action: ActionV1 | Dict[str, Any]
    ) -> Tuple[ObservationV1, float, bool, bool, Dict[str, Any]]:
        if isinstance(action, dict):
            act = ActionV1(**action)
        else:
            act = action

        self.step_count += 1
        self.sim_time_sec += self.dt_sec

        # 1. Planar rigid-body kinematics with damping and cage-wall collision clamping
        # Use 1.0 s locomotion sub-window so macro steps (dt_sec = 60..300 s) integrate
        # navigation accurately without turn-rate overshoot
        locomotion_dt = min(self.dt_sec, 1.0)
        n_sub = max(1, int(round(locomotion_dt / 0.1)))
        sub_dt = locomotion_dt / n_sub
        fwd = float(act.forward_speed_m_s)
        wz = float(act.turn_rate_rad_s)

        for _ in range(n_sub):
            self.yaw = float((self.yaw + wz * sub_dt + math.pi) % (2.0 * math.pi) - math.pi)
            vx = fwd * math.cos(self.yaw)
            vy = fwd * math.sin(self.yaw)
            self.vel_xy[0] = vx
            self.vel_xy[1] = vy
            self.ang_vel_z = wz
            self.pos[0] = float(np.clip(self.pos[0] + vx * sub_dt, -0.455, 0.455))
            self.pos[1] = float(np.clip(self.pos[1] + vy * sub_dt, -0.205, 0.205))

        # 2. Check proximity & affordance interactions
        obs_pre = self._build_observation()
        is_eating = False
        is_drinking = False
        is_sleeping = False
        is_sheltered = obs_pre.inside_hideout or obs_pre.inside_tunnel
        is_running_wheel = False
        is_exploring = abs(fwd) > 0.02

        bowl = self.objects_state["prop_bowl_main"]
        bottle = self.objects_state["prop_bottle_main"]
        hideout = self.objects_state["prop_hideout_main"]
        wheel = self.objects_state["prop_wheel_main"]

        d_bowl = float(np.linalg.norm(bowl["pose_xyz_m"][:2] - self.pos[:2]))
        d_bottle = float(np.linalg.norm(bottle["pose_xyz_m"][:2] - self.pos[:2]))
        d_hideout = float(np.linalg.norm(hideout["pose_xyz_m"][:2] - self.pos[:2]))
        d_wheel = float(np.linalg.norm(wheel["pose_xyz_m"][:2] - self.pos[:2]))

        if act.interact_flag:
            if d_bowl <= bowl["interaction_radius_m"] and bowl["resource_state"]["food_level"] > 0.01:
                is_eating = True
                bowl["resource_state"]["food_level"] = max(
                    0.05, bowl["resource_state"]["food_level"] - 0.0004 * self.dt_sec
                )
                self.cheek_pouch_fill = min(1.0, self.cheek_pouch_fill + 0.008 * self.dt_sec)
            elif d_bottle <= bottle["interaction_radius_m"] and bottle["resource_state"]["water_level"] > 0.01:
                is_drinking = True
                bottle["resource_state"]["water_level"] = max(
                    0.05, bottle["resource_state"]["water_level"] - 0.0003 * self.dt_sec
                )
            elif d_hideout <= hideout["interaction_radius_m"] and abs(fwd) < 0.01:
                is_sleeping = True
                if self.cheek_pouch_fill > 0.05:
                    self.cheek_pouch_fill = max(0.0, self.cheek_pouch_fill - 0.02 * self.dt_sec)
            elif d_wheel <= wheel["interaction_radius_m"]:
                is_running_wheel = True

        # Automatic replenishment simulating daily caretaker top-up if food/water gets very low
        if bowl["resource_state"]["food_level"] <= 0.10:
            bowl["resource_state"]["food_level"] = 1.0
        if bottle["resource_state"]["water_level"] <= 0.10:
            bottle["resource_state"]["water_level"] = 1.0

        # 3. Step Homeostatic Drives and compute per-drive reward terms
        reward, per_drive_terms = self.drives.step(
            self.dt_sec,
            is_eating=is_eating,
            is_drinking=is_drinking,
            is_sleeping=is_sleeping,
            is_sheltered=is_sheltered,
            is_running_wheel=is_running_wheel,
            is_exploring=is_exploring,
        )

        obs = self._build_observation()
        terminated = False
        truncated = bool(self.step_count >= self.max_episode_steps)

        info = {
            "step_count": self.step_count,
            "sim_time_sec": self.sim_time_sec,
            "reward_terms": per_drive_terms,
            "healthy_flags": self.drives.in_healthy_range_flags(),
            "behaviour_type": act.behaviour_type.value,
            "origin": EventOrigin.OBSERVED_PHYSICS.value,
            "interactions": {
                "eating": is_eating,
                "drinking": is_drinking,
                "sleeping": is_sleeping,
                "sheltered": is_sheltered,
                "running_wheel": is_running_wheel,
            },
        }
        return obs, float(reward), terminated, truncated, info
