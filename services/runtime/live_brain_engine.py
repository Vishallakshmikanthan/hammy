"""
HAMMY — Live Authoritative Neuro-Physical Brain Engine (`services/runtime/live_brain_engine.py`).

Unifies:
  1. Homeostatic physiology ticking (`HomeostaticDrives` + circadian + cheek-pouch/hoard + startle)
  2. Learned High-Level Cognitive Brain (`high_level_brain_v2.onnx`, GRU-Recurrent PPO + RND)
  3. Real-time MuJoCo Motor Brain status (`motor_amp_v2.onnx` / `best_policy.onnx`)
  4. Persistent Spatial & Object Memory + Social Trust (`Memory` rows in SQLite)
  5. Live WebSocket broadcasting of state snapshots, brain telemetry (top-5 skill probabilities,
     entropy, RND novelty, spatial familiarity heatmap, policy versions), and honest `WorldEvent`s.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import math
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from ai.cognition.cognitive_brain import (
    COGNITIVE_POLICY_VERSION,
    COGNITIVE_SKILLS_V2,
    CORE_PROP_IDS,
    DEFAULT_CORE_PROP_POS,
    SKILL_BASE_DURATIONS_SEC,
    SKILL_TARGET_PROP,
    CognitiveBrainDecision,
    CognitiveBrainONNX,
    CognitiveObservationInput,
)
from ai.cognition.drives import HomeostaticDrives
from ai.policies.skills import ScriptedHomeostaticBaselinePolicy
from contracts.schemas import BehaviourType, DriveVectorV1, EventOrigin, ObservationV1
from infrastructure.database.connection import get_db_session
from infrastructure.database.models import Habitat, HabitatObject, Memory, Pet, PetState, WorldEvent
from services.api.websocket import ws_manager

logger = logging.getLogger("hammy.live_brain")

DEFAULT_BRAIN_V2_ONNX = Path("training/runs/brain_v2/high_level_brain_v2.onnx")
DEFAULT_RND_V2_ONNX = Path("training/runs/brain_v2/rnd_curiosity_v2.onnx")
DEFAULT_MOTOR_V2_ONNX = Path("training/runs/motor_v2/motor_amp_v2.onnx")
DEFAULT_MOTOR_V1_ONNX = Path("training/runs/stage3/best_policy.onnx")


COZY_CORNER_SPOTS_XY: List[Tuple[float, float]] = [
    (-0.36, -0.145),  # Front-left cozy corner (in front of wheel)
    (-0.04, 0.172),   # Back-middle cozy nook (behind the 1.22x hollow log, between wheel & house)
    (-0.16, -0.148),  # Front-center viewing nook
    (0.37, -0.160),   # Front-right cozy corner (beside bowl)
]

# 4x2 obstacle-free sector waypoints (Blender Z-up X, Y -> Three.js X, -Y)
SECTOR_SAFE_WAYPOINTS_XY: List[Tuple[float, float]] = [
    (-0.36, -0.145),  # col 0, row 0 (left-front)
    (-0.32, 0.020),   # col 0, row 1 (left-mid in front of wheel)
    (-0.16, -0.148),  # col 1, row 0 (mid-left-front)
    (-0.04, 0.172),   # col 1, row 1 (back-center nook behind log)
    (0.18, -0.025),   # col 2, row 0 (mid-right open aisle)
    (0.11, 0.170),    # col 2, row 1 (back-right open)
    (0.37, -0.160),   # col 3, row 0 (front-right corner)
    (0.35, -0.035),   # col 3, row 1 (right-mid near water)
]


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _ensure_utc(dt: Optional[datetime.datetime]) -> datetime.datetime:
    if dt is None:
        return _utc_now()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


@dataclass
class PetRuntimeMemory:
    """In-memory fast cognitive state persisted periodically into SQLite `memories` table."""

    familiarity: float = 0.18
    trust_trend: float = 0.0
    startle_level: float = 0.0
    nest_hoard_level: float = 0.25
    boldness: float = 0.58
    wheel_affinity: float = 0.68
    interaction_count: int = 0
    last_parent_ts: float = 0.0
    prev_skill: Optional[str] = None
    prev_skill_streak: int = 0
    skill_remaining_wall_sec: float = 0.0
    skill_remaining_sim_sec: float = 0.0
    spatial_sectors: List[float] = field(default_factory=lambda: [0.35] * 8)
    object_memory: Dict[str, List[float]] = field(
        default_factory=lambda: {pid: [0.5, 0.4] for pid in CORE_PROP_IDS}
    )
    known_prop_ids: set[str] = field(default_factory=set)
    novel_prop_id: Optional[str] = None
    novel_prop_xy: Optional[Tuple[float, float]] = None
    last_decision: Optional[Dict[str, Any]] = None
    last_target_xy: Optional[List[float]] = None


class LiveBrainEngine:
    """Authoritative live cognitive + physiological simulation engine for HAMMY."""

    def __init__(
        self,
        brain_onnx_path: Path = DEFAULT_BRAIN_V2_ONNX,
        rnd_onnx_path: Path = DEFAULT_RND_V2_ONNX,
    ) -> None:
        self.brain_onnx_path = Path(brain_onnx_path)
        self.rnd_onnx_path = Path(rnd_onnx_path)
        self.brain: Optional[CognitiveBrainONNX] = None
        self.fallback_policy = ScriptedHomeostaticBaselinePolicy()
        self.policy_version: str = "scripted_homeostatic_v1"
        self.behaviour_mode: str = "scripted"
        self.motor_policy_version: str = "none"
        self.motor_onnx_path: Optional[str] = None
        self._pet_mem: Dict[str, PetRuntimeMemory] = {}
        self._rng = np.random.default_rng(int(time.time()) % (2**31 - 1))
        self._last_wall_tick: float = time.monotonic()
        self._task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self.reload_policies()

    def reload_policies(self) -> None:
        """Hot-loads trained ONNX cognitive and motor policies when present on disk."""
        if self.brain_onnx_path.exists():
            try:
                self.brain = CognitiveBrainONNX(
                    policy_onnx_path=self.brain_onnx_path,
                    rnd_onnx_path=self.rnd_onnx_path if self.rnd_onnx_path.exists() else None,
                    temperature=1.0,
                )
                self.policy_version = self.brain.policy_version
                self.behaviour_mode = "learned"
                logger.info("Loaded LEARNED cognitive brain ONNX: %s (%s)", self.policy_version, self.brain_onnx_path)
            except Exception as e:
                logger.warning("Failed to load cognitive ONNX (%s), falling back to scripted: %s", self.brain_onnx_path, e)
                self.brain = None
                self.policy_version = "scripted_homeostatic_v1"
                self.behaviour_mode = "scripted"
        else:
            self.brain = None
            self.policy_version = "scripted_homeostatic_v1"
            self.behaviour_mode = "scripted"

        if DEFAULT_MOTOR_V2_ONNX.exists():
            self.motor_policy_version = "ll_amp_ppo_v2.0.0"
            self.motor_onnx_path = str(DEFAULT_MOTOR_V2_ONNX).replace("\\", "/")
        elif DEFAULT_MOTOR_V1_ONNX.exists():
            self.motor_policy_version = "ll_ppo_stage3b_v1.0.0"
            self.motor_onnx_path = str(DEFAULT_MOTOR_V1_ONNX).replace("\\", "/")
        else:
            self.motor_policy_version = "procedural_fallback"
            self.motor_onnx_path = None

    def _get_mem(self, session: Session, pet_id: str) -> PetRuntimeMemory:
        mem = self._pet_mem.get(pet_id)
        if mem is not None:
            return mem
        mem = PetRuntimeMemory()
        # Hydrate persisted social_trust & spatial_grid memories from DB if present
        rows = session.query(Memory).filter(Memory.pet_id == pet_id).all()
        for row in rows:
            if row.memory_type == "social_trust" and row.estimated_value is not None:
                mem.familiarity = float(np.clip(row.estimated_value, 0.0, 1.0))
            elif row.memory_type == "spatial_grid" and isinstance(row.spatial_familiarity, list) and len(row.spatial_familiarity) == 8:
                mem.spatial_sectors = [float(np.clip(v, 0.0, 1.0)) for v in row.spatial_familiarity]
            elif row.memory_type == "object_appraisal" and row.target_id in mem.object_memory:
                ev = float(row.estimated_value if row.estimated_value is not None else 0.5)
                rec = float(np.clip((row.time_since_last_visit_sec or 600.0) / 3600.0, 0.0, 1.0))
                mem.object_memory[row.target_id] = [ev, rec]
        self._pet_mem[pet_id] = mem
        return mem

    def _persist_mem(self, session: Session, pet_id: str, mem: PetRuntimeMemory, now: datetime.datetime) -> None:
        trust_id = f"mem_{pet_id}_social_trust"
        trust_row = session.get(Memory, trust_id)
        if trust_row is None:
            trust_row = Memory(
                id=trust_id,
                pet_id=pet_id,
                memory_type="social_trust",
                target_id="parent",
                estimated_value=round(mem.familiarity, 4),
                confidence=round(min(1.0, 0.2 + 0.08 * mem.interaction_count), 4),
                updated_at=now,
            )
            session.add(trust_row)
        else:
            trust_row.estimated_value = round(mem.familiarity, 4)
            trust_row.confidence = round(min(1.0, 0.2 + 0.08 * mem.interaction_count), 4)
            trust_row.updated_at = now

        grid_id = f"mem_{pet_id}_spatial_grid"
        grid_row = session.get(Memory, grid_id)
        rounded_grid = [round(v, 4) for v in mem.spatial_sectors]
        if grid_row is None:
            grid_row = Memory(
                id=grid_id,
                pet_id=pet_id,
                memory_type="spatial_grid",
                target_id="habitat_v1",
                spatial_familiarity=rounded_grid,
                updated_at=now,
            )
            session.add(grid_row)
        else:
            grid_row.spatial_familiarity = rounded_grid
            grid_row.updated_at = now

    def _sector_index(self, x: float, y: float) -> int:
        col = int(np.clip(((x + 0.46) / 0.92) * 4.0, 0, 3))
        row = int(np.clip(((y + 0.21) / 0.42) * 2.0, 0, 1))
        return col * 2 + row

    def _least_familiar_xy(self, sectors: List[float]) -> Tuple[float, float]:
        idx = int(np.argmin(sectors))
        tx, ty = SECTOR_SAFE_WAYPOINTS_XY[idx % len(SECTOR_SAFE_WAYPOINTS_XY)]
        return (round(tx, 4), round(ty, 4))

    def _build_obs_input(
        self,
        pet_state: PetState,
        objects: List[HabitatObject],
        mem: PetRuntimeMemory,
        *,
        parent_active: bool = False,
        parent_action: Optional[str] = None,
    ) -> Tuple[CognitiveObservationInput, Dict[str, HabitatObject]]:
        obj_by_id = {o.id: o for o in objects}
        core_props: Dict[str, Tuple[float, float, float]] = {}
        for pid in CORE_PROP_IDS:
            o = obj_by_id.get(pid)
            if o is not None and o.pose_xyz_m:
                rs = o.resource_state or {}
                rlvl = float(rs.get("food_level", rs.get("water_level", rs.get("resource_level", 1.0))))
                core_props[pid] = (float(o.pose_xyz_m[0]), float(o.pose_xyz_m[1]), rlvl)
            else:
                dxyz = DEFAULT_CORE_PROP_POS[pid]
                core_props[pid] = (dxyz[0], dxyz[1], 1.0)

        # Detect offered food and any newly placed shelf prop!
        offered_food_xy: Optional[Tuple[float, float]] = None
        current_custom_ids = set()
        for o in objects:
            if o.object_type == "offered_food" and o.pose_xyz_m:
                offered_food_xy = (float(o.pose_xyz_m[0]), float(o.pose_xyz_m[1]))
            elif o.id not in CORE_PROP_IDS and not o.object_type.startswith("costume") and o.object_type != "offered_food":
                current_custom_ids.add(o.id)
                if o.id not in mem.known_prop_ids and o.pose_xyz_m:
                    mem.known_prop_ids.add(o.id)
                    mem.novel_prop_id = o.id
                    mem.novel_prop_xy = (float(o.pose_xyz_m[0]), float(o.pose_xyz_m[1]))

        if mem.novel_prop_id and mem.novel_prop_id not in current_custom_ids:
            mem.novel_prop_id = None
            mem.novel_prop_xy = None

        hideout = obj_by_id.get("prop_hideout_main")
        if hideout and hideout.resource_state:
            mem.nest_hoard_level = float(hideout.resource_state.get("hoard_food_level", mem.nest_hoard_level))

        d = pet_state.drives or {}
        pos = pet_state.position_xyz or [0.0, 0.0, 0.165]
        vel = pet_state.velocity_xy or [0.0, 0.0]
        sec_idx = self._sector_index(float(pos[0]), float(pos[1]))
        curr_fam = mem.spatial_sectors[sec_idx]
        mean_fam = float(np.mean(mem.spatial_sectors))

        # Check if drives are uninitialized/all-zero from legacy state -> normalize smoothly on first tick
        time_since_p = min(1.0, max(0.0, (time.monotonic() - mem.last_parent_ts) / 120.0)) if mem.last_parent_ts > 0 else 1.0

        inp = CognitiveObservationInput(
            hunger=float(d.get("hunger", 0.22)),
            thirst=float(d.get("thirst", 0.20)),
            energy=float(d.get("energy", 0.80)),
            comfort=float(d.get("comfort", 0.78)),
            stress=float(d.get("stress", 0.12)),
            curiosity=float(d.get("curiosity", 0.35)),
            familiarity=mem.familiarity,
            circadian_phase=float(d.get("circadian_phase", 0.85)) % 1.0,
            cheek_pouch_fill=float(pet_state.cheek_pouch_fill or 0.0),
            nest_hoard_level=mem.nest_hoard_level,
            startle_level=mem.startle_level,
            pos_xy=(float(pos[0]), float(pos[1])),
            yaw_rad=float(pet_state.yaw_rad or 0.0),
            vel_xy=(float(vel[0]), float(vel[1])),
            inside_hideout=bool(pet_state.inside_hideout),
            inside_tunnel=bool(pet_state.inside_tunnel),
            on_wheel=bool(pet_state.on_wheel),
            core_props=core_props,
            offered_food_xy=offered_food_xy,
            novel_prop_xy=mem.novel_prop_xy,
            object_memory={k: (v[0], v[1]) for k, v in mem.object_memory.items()},
            curr_cell_familiarity=curr_fam,
            mean_familiarity=mean_fam,
            least_familiar_xy=self._least_familiar_xy(mem.spatial_sectors),
            parent_active=parent_active,
            parent_action=parent_action,
            trust_trend=mem.trust_trend,
            time_since_parent_norm=time_since_p,
            prev_skill=mem.prev_skill or pet_state.active_skill,
            prev_skill_streak=mem.prev_skill_streak,
            boldness=mem.boldness,
            wheel_affinity=mem.wheel_affinity,
        )
        return inp, obj_by_id

    def get_brain_telemetry(self, session: Session, pet_id: str) -> Dict[str, Any]:
        """Returns rich live telemetry for `GET /pets/{pet_id}/state` & `Brain & Telemetry` UI."""
        mem = self._get_mem(session, pet_id)
        return {
            "policy_version": self.policy_version,
            "behaviour_mode": self.behaviour_mode,
            "motor_policy_version": self.motor_policy_version,
            "familiarity": round(mem.familiarity, 4),
            "nest_hoard_level": round(mem.nest_hoard_level, 4),
            "startle_level": round(mem.startle_level, 4),
            "rnd_novelty": (mem.last_decision or {}).get("rnd_novelty", 0.0),
            "entropy": (mem.last_decision or {}).get("entropy", 0.0),
            "value_ext": (mem.last_decision or {}).get("value_ext", 0.0),
            "value_int": (mem.last_decision or {}).get("value_int", 0.0),
            "top_skills": (mem.last_decision or {}).get("top_skills", []),
            "spatial_familiarity": [round(v, 3) for v in mem.spatial_sectors],
            "target_xy": mem.last_target_xy,
        }

    def _next_world_tick(self, session: Session, pet_id: str) -> int:
        max_tick = (
            session.query(func.max(WorldEvent.world_tick))
            .filter(WorldEvent.pet_id == pet_id)
            .scalar()
        )
        return int(max_tick or 0) + 1

    def step_pet_live(
        self,
        session: Session,
        pet_id: str,
        dt_wall_sec: float,
        *,
        force_decision: bool = False,
        now: Optional[datetime.datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Advances one authoritative live physiological + learned-brain tick for `pet_id`."""
        pet = session.get(Pet, pet_id)
        pet_state = session.get(PetState, pet_id)
        if not pet or not pet_state or pet_state.is_paused:
            return None

        curr_time = _ensure_utc(now)
        mem = self._get_mem(session, pet_id)
        habitat = session.query(Habitat).filter_by(pet_id=pet_id).first()
        objects = session.query(HabitatObject).filter_by(habitat_id=habitat.id).all() if habitat else []

        # Reload ONNX automatically if a newly trained brain just appeared on disk!
        if self.brain is None and self.brain_onnx_path.exists():
            self.reload_policies()
        elif self.motor_policy_version != "ll_amp_ppo_v2.0.0" and DEFAULT_MOTOR_V2_ONNX.exists():
            self.reload_policies()

        scale = float(np.clip(pet_state.real_time_scale or 1.0, 0.5, 600.0))
        dt_sim = max(0.2, dt_wall_sec * scale)
        # Ensure live 1x viewing still displays subtle alive micro-breathing of drives without exaggerating
        # (at 1x real-time: real biological drift per second; at 60x: 1 sim hour/min!)
        drives_raw = dict(pet_state.drives or {})
        hd = HomeostaticDrives(
            hunger=float(drives_raw.get("hunger", 0.22)),
            thirst=float(drives_raw.get("thirst", 0.18)),
            energy=float(drives_raw.get("energy", 0.80)),
            comfort=float(drives_raw.get("comfort", 0.78)),
            stress=float(drives_raw.get("stress", 0.12)),
            curiosity=float(drives_raw.get("curiosity", 0.35)),
            circadian_phase=float(drives_raw.get("circadian_phase", 0.85)) % 1.0,
        )

        # Heal legacy frozen-0% state smoothly if hunger+thirst+curiosity+stress were all stuck at 0.0
        if hd.hunger == 0.0 and hd.thirst == 0.0 and hd.curiosity == 0.0 and hd.stress == 0.0:
            hd.hunger = 0.24
            hd.thirst = 0.21
            hd.curiosity = 0.42
            hd.stress = 0.11

        cur_skill = pet_state.active_skill or "explore_area"
        is_sleeping = cur_skill in ("rest", "nesting")
        is_sheltered = bool(pet_state.inside_hideout or pet_state.inside_tunnel or cur_skill in ("rest", "nesting", "hide", "enter_tunnel"))

        # 1. Step homeostatic physiology continuously over dt_sim!
        # Passive drift integrates full dt_sim; active skill drain is bounded per tick
        # so accelerated clocks (60x / 300x) don't instantly slam drives to 0.0% in one tick.
        active_dt = min(dt_sim, 6.0)
        passive_dt = max(0.0, dt_sim - active_dt)
        if passive_dt > 0.0:
            hd.step(
                passive_dt,
                is_eating=False,
                is_drinking=False,
                is_sleeping=is_sleeping,
                is_sheltered=is_sheltered,
                is_running_wheel=False,
                is_exploring=False,
            )
        hd.step(
            active_dt,
            is_eating=(cur_skill == "eat"),
            is_drinking=(cur_skill == "drink"),
            is_sleeping=is_sleeping,
            is_sheltered=is_sheltered,
            is_running_wheel=(cur_skill == "run_on_wheel"),
            is_exploring=(cur_skill in ("explore_area", "digging", "hind_leg_standing", "enter_tunnel")),
        )
        # Mild passive curiosity replenishment while awake & not exhausting curiosity
        if not is_sleeping and cur_skill not in ("explore_area", "run_on_wheel", "digging"):
            hd.curiosity = float(np.clip(hd.curiosity + 0.14 * (dt_sim / 3600.0), 0.0, 1.0))

        # Decay startle smoothly
        mem.startle_level = float(max(0.0, mem.startle_level - 0.04 * dt_wall_sec))

        # Advance simulation clock & age
        pet_state.sim_time_sec = round(float(pet_state.sim_time_sec or 0.0) + dt_sim, 3)
        pet_state.simulated_age_days = round(float(pet_state.simulated_age_days or 30.0) + (dt_sim / 86400.0), 5)
        pet_state.last_simulated_at = curr_time
        pet_state.drives = hd.to_contract().model_dump()

        # Check whether it is time for the learned brain to choose the next skill bout
        mem.skill_remaining_wall_sec -= dt_wall_sec
        mem.skill_remaining_sim_sec -= dt_sim

        # Detect newly placed prop or offered food to interrupt idle bout organically!
        obs_inp, obj_by_id = self._build_obs_input(pet_state, objects, mem)
        novel_interrupt = mem.novel_prop_xy is not None and cur_skill != "explore_area"
        food_interrupt = obs_inp.offered_food_xy is not None and cur_skill not in ("eat", "approach_food", "cheek_stuffing")

        emitted_event: Optional[Dict[str, Any]] = None
        should_decide = (
            force_decision
            or mem.last_decision is None
            or mem.skill_remaining_wall_sec <= 0.0
            or mem.skill_remaining_sim_sec <= 0.0
            or novel_interrupt
            or food_interrupt
        )

        if should_decide:
            if novel_interrupt:
                # Novel object spikes curiosity genuinely!
                hd.curiosity = float(np.clip(hd.curiosity + 0.25, 0.0, 1.0))
                pet_state.drives = hd.to_contract().model_dump()
                obs_inp.curiosity = hd.curiosity

            if self.brain is not None:
                dec: CognitiveBrainDecision = self.brain.decide(pet_id, obs_inp, rng=self._rng, deterministic=False)
                chosen_skill = dec.skill_name
                behaviour_type = BehaviourType.LEARNED
                decision_payload = {
                    "policy_version": dec.policy_version,
                    "motor_policy_version": self.motor_policy_version,
                    "top_skills": dec.top_skills,
                    "entropy": dec.entropy,
                    "value_ext": dec.value_ext,
                    "value_int": dec.value_int,
                    "rnd_novelty": dec.rnd_novelty,
                }
            else:
                # Honest scripted fallback only if ONNX hasn't finished training yet
                obs_v1 = ObservationV1(
                    sim_time_sec=pet_state.sim_time_sec,
                    position_xyz=list(pet_state.position_xyz or [0.0, 0.0, 0.165]),
                    yaw_rad=float(pet_state.yaw_rad or 0.0),
                    velocity_xy=list(pet_state.velocity_xy or [0.0, 0.0]),
                    angular_velocity_z=float(pet_state.angular_velocity_z or 0.0),
                    inside_hideout=bool(pet_state.inside_hideout),
                    inside_tunnel=bool(pet_state.inside_tunnel),
                    on_wheel=bool(pet_state.on_wheel),
                    cheek_pouch_fill=float(pet_state.cheek_pouch_fill or 0.0),
                    drives=hd.to_contract(),
                    nearby_objects=[],
                )
                chosen_skill = self.fallback_policy.select_skill(obs_v1)
                behaviour_type = BehaviourType.SCRIPTED
                decision_payload = {
                    "policy_version": "scripted_homeostatic_v1",
                    "motor_policy_version": self.motor_policy_version,
                    "top_skills": [{"skill": chosen_skill, "prob": 1.0}],
                    "entropy": 0.0,
                    "value_ext": 0.0,
                    "value_int": 0.0,
                    "rnd_novelty": 0.0,
                }

            # Apply biological skill effects & spatial target
            target_xy = self._apply_skill_execution(pet_state, hd, chosen_skill, obj_by_id, obs_inp, mem, curr_time)
            pet_state.drives = hd.to_contract().model_dump()
            pet_state.active_skill = chosen_skill
            pet_state.active_skill_started_at = curr_time

            if chosen_skill == mem.prev_skill:
                mem.prev_skill_streak += 1
            else:
                mem.prev_skill_streak = 0
                mem.prev_skill = chosen_skill

            base_sim_dur = SKILL_BASE_DURATIONS_SEC.get(chosen_skill, 55.0) * float(self._rng.uniform(0.85, 1.15))
            mem.skill_remaining_sim_sec = base_sim_dur
            # Give the 3D hamster enough real-time wall seconds (9..16s at 1x, faster at 10x..300x)
            # to walk cleanly around obstacles via doorway/entry points and complete the activity!
            min_wall = 9.0 if scale <= 2.0 else (4.5 if scale <= 20.0 else 2.5)
            max_wall = 16.0 if scale <= 2.0 else (8.0 if scale <= 20.0 else 5.0)
            mem.skill_remaining_wall_sec = float(np.clip(base_sim_dur / max(scale, 1.0), min_wall, max_wall))
            mem.last_decision = decision_payload
            mem.last_target_xy = target_xy

            # Update spatial & object memory
            px, py = float(pet_state.position_xyz[0]), float(pet_state.position_xyz[1])
            sec_idx = self._sector_index(px, py)
            mem.spatial_sectors = [max(0.05, v * 0.992) for v in mem.spatial_sectors]
            mem.spatial_sectors[sec_idx] = min(1.0, mem.spatial_sectors[sec_idx] + 0.20)
            for pid in CORE_PROP_IDS:
                est_v, rec = mem.object_memory[pid]
                ox, oy, rlvl = obs_inp.core_props[pid]
                if math.hypot(ox - px, oy - py) < 0.14:
                    mem.object_memory[pid] = [0.6 * est_v + 0.4 * rlvl, 0.0]
                else:
                    mem.object_memory[pid] = [est_v, min(1.0, rec + 0.05)]

            self._persist_mem(session, pet_id, mem, curr_time)

            # Record honest WorldEvent
            tick = self._next_world_tick(session, pet_id)
            seed_val = int(self._rng.integers(1, 2**31 - 1))
            evt = WorldEvent(
                event_id=f"evt_{pet_id}_{tick}_brain_{uuid.uuid4().hex[:10]}",
                pet_id=pet_id,
                world_tick=tick,
                sim_time_sec=pet_state.sim_time_sec,
                event_type="brain_skill_selected",
                skill_name=chosen_skill,
                origin=EventOrigin.OBSERVED_PHYSICS.value,
                behaviour_type=behaviour_type.value,
                seed=seed_val,
                payload={
                    **decision_payload,
                    "target_xy": target_xy,
                    "drives": pet_state.drives,
                    "familiarity": round(mem.familiarity, 4),
                    "cheek_pouch_fill": round(float(pet_state.cheek_pouch_fill), 4),
                    "nest_hoard_level": round(mem.nest_hoard_level, 4),
                },
                created_at=curr_time,
            )
            session.add(evt)
            emitted_event = {
                "event_id": evt.event_id,
                "pet_id": evt.pet_id,
                "world_tick": evt.world_tick,
                "sim_time_sec": evt.sim_time_sec,
                "event_type": evt.event_type,
                "skill_name": evt.skill_name,
                "origin": evt.origin,
                "behaviour_type": evt.behaviour_type,
                "seed": evt.seed,
                "payload": evt.payload,
                "created_at": curr_time.isoformat(),
            }

        pet_state.version = int(pet_state.version or 0) + 1
        pet_state.updated_at = curr_time
        session.commit()

        snapshot = {
            "type": "snapshot",
            "pet_id": pet_id,
            "version": pet_state.version,
            "sim_time_sec": pet_state.sim_time_sec,
            "simulated_age_days": pet_state.simulated_age_days,
            "real_time_scale": pet_state.real_time_scale,
            "drives": pet_state.drives,
            "position_xyz": pet_state.position_xyz,
            "yaw_rad": pet_state.yaw_rad,
            "inside_hideout": pet_state.inside_hideout,
            "inside_tunnel": pet_state.inside_tunnel,
            "on_wheel": pet_state.on_wheel,
            "cheek_pouch_fill": pet_state.cheek_pouch_fill,
            "active_skill": pet_state.active_skill,
            "is_paused": pet_state.is_paused,
            "last_simulated_at": curr_time.isoformat(),
            "policy_version": self.policy_version,
            "motor_policy_version": self.motor_policy_version,
            "brain_telemetry": self.get_brain_telemetry(session, pet_id),
        }
        return {"snapshot": snapshot, "event": emitted_event}

    def _apply_skill_execution(
        self,
        pet_state: PetState,
        hd: HomeostaticDrives,
        skill: str,
        obj_by_id: Dict[str, HabitatObject],
        obs_inp: CognitiveObservationInput,
        mem: PetRuntimeMemory,
        now: datetime.datetime,
    ) -> List[float]:
        """Moves authoritative pet state & applies physically grounded resource/drive updates."""
        cur_pos = list(pet_state.position_xyz or [0.0, 0.0, 0.165])
        target_prop = SKILL_TARGET_PROP.get(skill)
        tx, ty = float(cur_pos[0]), float(cur_pos[1])

        rest_in_corner = (
            skill == "rest"
            and hd.energy >= 0.50
            and hd.stress < 0.35
            and float(self._rng.random()) < 0.48
        )

        if skill in ("approach_food", "eat", "cheek_stuffing"):
            if obs_inp.offered_food_xy is not None:
                fx, fy = obs_inp.offered_food_xy
                tx, ty = (fx - 0.095, fy - 0.005)
            else:
                bx, by, _ = obs_inp.core_props["prop_bowl_main"]
                # Clean exterior stand-off in front-left of ceramic bowl rim
                tx, ty = (bx - 0.098, by - 0.005)
        elif skill == "drink":
            sx, sy, _ = obs_inp.core_props["prop_bottle_main"]
            # Clean exterior stand-off at water spout tip (no glass/bottle clipping)
            tx, ty = (sx - 0.076, sy - 0.022)
        elif skill == "enter_tunnel":
            # Approach one of the two hollow log mouth entrances
            tx, ty = (0.084, -0.168) if float(self._rng.random()) < 0.5 else (-0.230, -0.018)
        elif skill == "explore_area":
            if mem.novel_prop_xy is not None:
                tx, ty = mem.novel_prop_xy
                mem.novel_prop_id = None
                mem.novel_prop_xy = None
                hd.curiosity = float(np.clip(hd.curiosity - 0.24, 0.0, 1.0))
            else:
                tx, ty = self._least_familiar_xy(mem.spatial_sectors)
                hd.curiosity = float(np.clip(hd.curiosity - 0.14, 0.0, 1.0))
        elif skill in ("cautious_sniff", "accept_petting"):
            tx, ty = (0.0, -0.145)
        elif rest_in_corner:
            tx, ty = COZY_CORNER_SPOTS_XY[int(self._rng.integers(0, len(COZY_CORNER_SPOTS_XY)))]
        elif skill in ("digging", "hind_leg_standing", "grooming"):
            # Pick a cozy cage corner or open bedding nook (never inside hideout/wheel/bowl)
            if float(self._rng.random()) < 0.65:
                tx, ty = COZY_CORNER_SPOTS_XY[int(self._rng.integers(0, len(COZY_CORNER_SPOTS_XY)))]
            else:
                tx, ty = SECTOR_SAFE_WAYPOINTS_XY[int(self._rng.integers(0, len(SECTOR_SAFE_WAYPOINTS_XY)))]
        elif target_prop and target_prop in obs_inp.core_props:
            tx, ty, _ = obs_inp.core_props[target_prop]

        # Slight natural position jitter only on open floor/corner targets
        if skill not in ("rest", "hide", "nesting", "unload_hoard", "run_on_wheel", "eat", "drink", "enter_tunnel"):
            tx = float(np.clip(tx + float(self._rng.uniform(-0.018, 0.018)), -0.39, 0.39))
            ty = float(np.clip(ty + float(self._rng.uniform(-0.015, 0.015)), -0.155, 0.155))

        dx, dy = tx - float(cur_pos[0]), ty - float(cur_pos[1])
        if math.hypot(dx, dy) > 0.01:
            pet_state.yaw_rad = round(math.atan2(dy, dx), 4)
        pet_state.position_xyz = [round(tx, 4), round(ty, 4), 0.165]

        pet_state.inside_hideout = (skill in ("nesting", "hide", "unload_hoard")) or (skill == "rest" and not rest_in_corner)
        pet_state.inside_tunnel = skill == "enter_tunnel"
        pet_state.on_wheel = skill == "run_on_wheel"

        # Skill-specific physiological & resource effects
        if skill == "eat":
            hd.hunger = float(np.clip(hd.hunger - 0.22, 0.0, 1.0))
            hd.comfort = float(np.clip(hd.comfort + 0.04, 0.0, 1.0))
            bowl = obj_by_id.get("prop_bowl_main")
            if bowl and bowl.resource_state:
                rs = dict(bowl.resource_state)
                rs["food_level"] = round(max(0.0, float(rs.get("food_level", 1.0)) - 0.06), 4)
                bowl.resource_state = rs
                bowl.updated_at = now
        elif skill == "cheek_stuffing":
            hd.hunger = float(np.clip(hd.hunger - 0.06, 0.0, 1.0))
            pet_state.cheek_pouch_fill = round(min(1.0, float(pet_state.cheek_pouch_fill or 0.0) + 0.30), 4)
            bowl = obj_by_id.get("prop_bowl_main")
            if bowl and bowl.resource_state:
                rs = dict(bowl.resource_state)
                rs["food_level"] = round(max(0.0, float(rs.get("food_level", 1.0)) - 0.08), 4)
                bowl.resource_state = rs
                bowl.updated_at = now
        elif skill == "unload_hoard":
            amt = float(pet_state.cheek_pouch_fill or 0.0)
            pet_state.cheek_pouch_fill = 0.0
            mem.nest_hoard_level = float(np.clip(mem.nest_hoard_level + 0.65 * amt, 0.0, 1.0))
            hd.comfort = float(np.clip(hd.comfort + 0.10 * amt, 0.0, 1.0))
            hd.stress = float(np.clip(hd.stress - 0.06 * amt, 0.0, 1.0))
            hideout = obj_by_id.get("prop_hideout_main")
            if hideout:
                rs = dict(hideout.resource_state or {})
                rs["hoard_food_level"] = round(mem.nest_hoard_level, 4)
                hideout.resource_state = rs
                hideout.updated_at = now
        elif skill == "drink":
            hd.thirst = float(np.clip(hd.thirst - 0.28, 0.0, 1.0))
            bottle = obj_by_id.get("prop_bottle_main")
            if bottle and bottle.resource_state:
                rs = dict(bottle.resource_state)
                rs["water_level"] = round(max(0.0, float(rs.get("water_level", 0.75)) - 0.04), 4)
                bottle.resource_state = rs
                bottle.updated_at = now
        elif skill == "run_on_wheel":
            hd.curiosity = float(np.clip(hd.curiosity - 0.18, 0.0, 1.0))
            hd.stress = float(np.clip(hd.stress - 0.12, 0.0, 1.0))
            hd.energy = float(np.clip(hd.energy - 0.07, 0.0, 1.0))
        elif skill == "digging":
            hd.curiosity = float(np.clip(hd.curiosity - 0.15, 0.0, 1.0))
            hd.comfort = float(np.clip(hd.comfort + 0.06, 0.0, 1.0))
            hd.energy = float(np.clip(hd.energy - 0.04, 0.0, 1.0))
        elif skill == "hind_leg_standing":
            hd.curiosity = float(np.clip(hd.curiosity - 0.10, 0.0, 1.0))
        elif skill == "grooming":
            hd.stress = float(np.clip(hd.stress - 0.11, 0.0, 1.0))
            hd.comfort = float(np.clip(hd.comfort + 0.10, 0.0, 1.0))
        elif skill == "nesting":
            hd.comfort = float(np.clip(hd.comfort + 0.14, 0.0, 1.0))
            hd.stress = float(np.clip(hd.stress - 0.08, 0.0, 1.0))
        elif skill == "rest":
            hd.energy = float(np.clip(hd.energy + 0.16, 0.0, 1.0))
            hd.comfort = float(np.clip(hd.comfort + 0.08, 0.0, 1.0))
            hd.stress = float(np.clip(hd.stress - 0.12, 0.0, 1.0))
        elif skill == "hide":
            hd.stress = float(np.clip(hd.stress - 0.22, 0.0, 1.0))
            hd.comfort = float(np.clip(hd.comfort + 0.06, 0.0, 1.0))
        elif skill == "enter_tunnel":
            hd.curiosity = float(np.clip(hd.curiosity - 0.14, 0.0, 1.0))
            hd.stress = float(np.clip(hd.stress - 0.08, 0.0, 1.0))

        return [round(tx, 4), round(ty, 4)]

    def handle_parent_interaction(
        self,
        session: Session,
        pet_id: str,
        action: str,
    ) -> Dict[str, Any]:
        """Routes Parent Interaction directly through the LEARNED GRU-PPO brain + unified SQLite PetState!"""
        pet_state = session.get(PetState, pet_id)
        if not pet_state:
            raise ValueError(f"PetState '{pet_id}' not found")

        now = _utc_now()
        mem = self._get_mem(session, pet_id)
        habitat = session.query(Habitat).filter_by(pet_id=pet_id).first()
        objects = session.query(HabitatObject).filter_by(habitat_id=habitat.id).all() if habitat else []

        if self.brain is None and self.brain_onnx_path.exists():
            self.reload_policies()

        obs_inp, _ = self._build_obs_input(
            pet_state, objects, mem, parent_active=True, parent_action=action
        )
        fam_before = mem.familiarity
        d_raw = dict(pet_state.drives or {})
        stress_before = float(d_raw.get("stress", 0.15))

        mem.interaction_count += 1
        mem.last_parent_ts = time.monotonic()

        # Restrict decision head cleanly to the 3 social response options so the LEARNED neural brain
        # chooses organically between retreat (`hide`), `cautious_sniff`, and `accept_petting`!
        if self.brain is not None:
            dec = self.brain.decide(pet_id, obs_inp, rng=self._rng, deterministic=True)
            social_probs = {
                "avoid_and_retreat": dec.skill_probs.get("hide", 0.01),
                "cautious_sniff": dec.skill_probs.get("cautious_sniff", 0.01),
                "accept_petting": dec.skill_probs.get("accept_petting", 0.01),
            }
            response = max(social_probs.keys(), key=lambda k: social_probs[k])
            selection_label = "LEARNED"
            behaviour_type = BehaviourType.LEARNED
            rationale = (
                f"Learned {self.policy_version} social policy chose {response} "
                f"(p_retreat={social_probs['avoid_and_retreat']:.2f}, "
                f"p_sniff={social_probs['cautious_sniff']:.2f}, "
                f"p_accept={social_probs['accept_petting']:.2f})."
            )
            mem.last_decision = {
                "policy_version": dec.policy_version,
                "motor_policy_version": self.motor_policy_version,
                "top_skills": dec.top_skills,
                "entropy": dec.entropy,
                "value_ext": dec.value_ext,
                "value_int": dec.value_int,
                "rnd_novelty": dec.rnd_novelty,
            }
        else:
            treat_bonus = 0.22 if action == "offer_treat" else 0.0
            trust_score = fam_before + treat_bonus - 0.55 * stress_before
            if trust_score < 0.12:
                response = "avoid_and_retreat"
            elif trust_score < 0.42:
                response = "cautious_sniff"
            else:
                response = "accept_petting"
            selection_label = "RULE-BASED"
            behaviour_type = BehaviourType.RULE
            rationale = f"Fallback trust rule ({trust_score:.2f}): {response}."

        # Apply unified physiological & familiarity progression on the real PetState!
        if response == "avoid_and_retreat":
            mem.familiarity = float(np.clip(fam_before + (0.14 if action == "offer_treat" else 0.04), 0.0, 1.0))
            stress_after = float(np.clip(stress_before + (-0.05 if action == "offer_treat" else 0.08), 0.0, 1.0))
            target_obj = "prop_hideout_main"
            pet_state.inside_hideout = True
            pet_state.active_skill = "hide"
            pet_state.position_xyz = [0.28, 0.11, 0.165]
        elif response == "cautious_sniff":
            mem.familiarity = float(np.clip(fam_before + (0.16 if action == "offer_treat" else 0.11), 0.0, 1.0))
            stress_after = float(np.clip(stress_before - (0.08 if action == "offer_treat" else 0.04), 0.0, 1.0))
            d_raw["curiosity"] = round(max(0.0, float(d_raw.get("curiosity", 0.35)) - 0.08), 4)
            target_obj = "prop_treat_zone"
            pet_state.inside_hideout = False
            pet_state.active_skill = "cautious_sniff"
            pet_state.position_xyz = [0.0, -0.14, 0.165]
        else:
            mem.familiarity = float(np.clip(fam_before + 0.10, 0.0, 1.0))
            stress_after = float(np.clip(stress_before - 0.14, 0.0, 1.0))
            d_raw["comfort"] = round(min(1.0, float(d_raw.get("comfort", 0.78)) + 0.12), 4)
            if action == "offer_treat":
                d_raw["hunger"] = round(max(0.0, float(d_raw.get("hunger", 0.25)) - 0.10), 4)
            target_obj = "prop_treat_zone"
            pet_state.inside_hideout = False
            pet_state.active_skill = "accept_petting"
            pet_state.position_xyz = [0.0, -0.15, 0.165]

        mem.trust_trend = float(np.clip((mem.familiarity - fam_before) * 5.0, -1.0, 1.0))
        d_raw["stress"] = round(stress_after, 4)
        pet_state.drives = d_raw
        pet_state.version = int(pet_state.version or 0) + 1
        pet_state.updated_at = now
        self._persist_mem(session, pet_id, mem, now)

        tick = self._next_world_tick(session, pet_id)
        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_parent_{uuid.uuid4().hex[:10]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=pet_state.sim_time_sec,
            event_type="parent_interaction_response",
            skill_name=response,
            origin=EventOrigin.OBSERVED_PHYSICS.value,
            behaviour_type=behaviour_type.value,
            seed=int(self._rng.integers(1, 2**31 - 1)),
            payload={
                "action_requested": action,
                "hamster_response": response,
                "policy_version": self.policy_version,
                "selection_label": selection_label,
                "familiarity_before": round(fam_before, 4),
                "familiarity_after": round(mem.familiarity, 4),
                "stress_before": round(stress_before, 4),
                "stress_after": round(stress_after, 4),
                "rationale": rationale,
            },
            created_at=now,
        )
        session.add(evt)
        session.commit()

        return {
            "outcome": {
                "action_requested": action,
                "hamster_response": response,
                "target_object_id": target_obj,
                "locomotion_label": "LEARNED",
                "interaction_label": selection_label,
                "policy_version": self.policy_version,
                "familiarity_before": round(fam_before, 4),
                "familiarity_after": round(mem.familiarity, 4),
                "stress_before": round(stress_before, 4),
                "stress_after": round(stress_after, 4),
                "rationale": rationale,
            },
            "drives": {**pet_state.drives, "familiarity": round(mem.familiarity, 4)},
            "snapshot": {
                "type": "snapshot",
                "pet_id": pet_id,
                "version": pet_state.version,
                "sim_time_sec": pet_state.sim_time_sec,
                "simulated_age_days": pet_state.simulated_age_days,
                "real_time_scale": pet_state.real_time_scale,
                "drives": pet_state.drives,
                "position_xyz": pet_state.position_xyz,
                "inside_hideout": pet_state.inside_hideout,
                "inside_tunnel": pet_state.inside_tunnel,
                "on_wheel": pet_state.on_wheel,
                "cheek_pouch_fill": pet_state.cheek_pouch_fill,
                "active_skill": pet_state.active_skill,
                "is_paused": pet_state.is_paused,
                "policy_version": self.policy_version,
                "motor_policy_version": self.motor_policy_version,
                "brain_telemetry": self.get_brain_telemetry(session, pet_id),
            },
            "event": {
                "event_id": evt.event_id,
                "pet_id": evt.pet_id,
                "world_tick": evt.world_tick,
                "sim_time_sec": evt.sim_time_sec,
                "event_type": evt.event_type,
                "skill_name": evt.skill_name,
                "origin": evt.origin,
                "behaviour_type": evt.behaviour_type,
                "seed": evt.seed,
                "payload": evt.payload,
                "created_at": now.isoformat(),
            },
        }

    async def start_background_loop(self, interval_sec: float = 1.5) -> None:
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("HAMMY_DISABLE_LIVE_LOOP") == "1":
            logger.info("Skipping live background brain loop (test/disabled environment).")
            return
        if self._task is not None and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._last_wall_tick = time.monotonic()
        self._task = asyncio.create_task(self._loop(interval_sec))
        logger.info("Started LiveBrainEngine loop (policy=%s, interval=%.1fs)", self.policy_version, interval_sec)

    async def stop_background_loop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self, interval_sec: float) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(interval_sec)
                now_mono = time.monotonic()
                dt_wall = max(0.1, min(10.0, now_mono - self._last_wall_tick))
                self._last_wall_tick = now_mono

                payloads_to_broadcast: List[Tuple[str, Dict[str, Any]]] = []
                with get_db_session() as session:
                    pet_ids = [r[0] for r in session.query(Pet.id).all()]
                    for pid in pet_ids:
                        res = self.step_pet_live(session, pid, dt_wall_sec=dt_wall)
                        if res is not None:
                            payloads_to_broadcast.append((pid, res))

                for pid, res in payloads_to_broadcast:
                    await ws_manager.broadcast_to_pet(pid, res["snapshot"])
                    if res.get("event") is not None:
                        await ws_manager.broadcast_to_pet(pid, {"type": "event", "event": res["event"]})
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("LiveBrainEngine tick error: %s", exc)


live_brain_engine = LiveBrainEngine()
