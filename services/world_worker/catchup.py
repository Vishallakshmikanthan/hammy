"""
HAMMY — Bounded Catch-Up Simulation Engine (`services/world_worker/catchup.py`).
Executes bounded catch-up simulation chunks using:
  - Empirical skill-outcome models (`sample_skill_outcome`) with explicit `origin = sampled_from_skill_model`.
  - Deterministic event IDs derived from `(pet_id, world_tick, event_type, seed)`.
  - Pause/resume state enforcement.
  - Configurable catch-up capping per run with summary events.
"""

from __future__ import annotations

import datetime
import hashlib
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from contracts.schemas import (
    BehaviourType,
    DriveVectorV1,
    EventOrigin,
    ObservationV1,
)
from infrastructure.database.models import Pet, PetState, WorldEvent
from ai.policies.skills import ScriptedHomeostaticBaselinePolicy
from ai.cognition.skill_outcome_model import SkillOutcome, sample_skill_outcome


def _ensure_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def generate_deterministic_event_id(
    pet_id: str,
    world_tick: int,
    event_type: str,
    seed: int,
) -> str:
    """
    Derives deterministic event IDs from (pet_id, world_tick, event_type, seed)
    so retries or duplicate runs cannot duplicate events (P2.2 Criterion 2).
    """
    raw = f"{pet_id}:{world_tick}:{event_type}:{seed}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:20]
    return f"evt_{pet_id}_{world_tick}_{digest}"


class CatchUpSimulator:
    """
    Simulates elapsed time in bounded chunks using the empirical skill models
    and the high-level policy.
    """

    def __init__(
        self,
        max_sim_sec_per_run: float = 3600.0,  # 1 hour simulated time cap per worker run
        max_steps_per_run: int = 50,          # max skills to evaluate per run
        min_step_elapsed_sec: float = 1.0,    # minimum elapsed real seconds to trigger a step
    ):
        self.max_sim_sec_per_run = max_sim_sec_per_run
        self.max_steps_per_run = max_steps_per_run
        self.min_step_elapsed_sec = min_step_elapsed_sec
        self.policy = ScriptedHomeostaticBaselinePolicy()

    def simulate_catchup(
        self,
        pet_state: PetState,
        pet: Pet,
        current_tick: int,
        now: Optional[datetime.datetime] = None,
        seed_base: int = 42,
    ) -> Dict[str, Any]:
        """
        Calculates elapsed time, steps simulation up to the configured budget,
        and returns updated state attributes and generated WorldEvents.
        """
        curr_time = _ensure_utc(now or datetime.datetime.now(datetime.timezone.utc))
        last_sim = _ensure_utc(pet_state.last_simulated_at)
        elapsed_real_sec = max(0.0, (curr_time - last_sim).total_seconds())

        # 1. Check Pause State (P2.2 Criterion 4)
        if pet_state.is_paused:
            # When paused, elapsed time does not advance simulation time.
            # last_simulated_at is caught up to curr_time so unpausing later resumes cleanly.
            return {
                "steps_executed": 0,
                "simulated_sec": 0.0,
                "remaining_sim_sec": 0.0,
                "events": [],
                "new_last_simulated_at": curr_time,
                "new_sim_time_sec": pet_state.sim_time_sec,
                "new_simulated_age_days": pet_state.simulated_age_days,
                "new_drives": dict(pet_state.drives),
                "new_position_xyz": list(pet_state.position_xyz),
                "new_flags": {
                    "inside_hideout": pet_state.inside_hideout,
                    "inside_tunnel": pet_state.inside_tunnel,
                    "on_wheel": pet_state.on_wheel,
                    "cheek_pouch_fill": pet_state.cheek_pouch_fill,
                },
                "status": "paused",
            }

        # 2. Time Scaling (P2.2 Criterion 3)
        target_sim_sec = elapsed_real_sec * pet_state.real_time_scale
        if target_sim_sec < self.min_step_elapsed_sec:
            # Too short to run a macro-step
            return {
                "steps_executed": 0,
                "simulated_sec": 0.0,
                "remaining_sim_sec": 0.0,
                "events": [],
                "new_last_simulated_at": last_sim,
                "new_sim_time_sec": pet_state.sim_time_sec,
                "new_simulated_age_days": pet_state.simulated_age_days,
                "new_drives": dict(pet_state.drives),
                "new_position_xyz": list(pet_state.position_xyz),
                "new_flags": {
                    "inside_hideout": pet_state.inside_hideout,
                    "inside_tunnel": pet_state.inside_tunnel,
                    "on_wheel": pet_state.on_wheel,
                    "cheek_pouch_fill": pet_state.cheek_pouch_fill,
                },
                "status": "no_catchup_needed",
            }

        # 3. Bounded Catch-Up Cap (P2.2 Criterion 5)
        sim_sec_budget = min(target_sim_sec, self.max_sim_sec_per_run)

        # Initialize simulation loop state
        sim_time = pet_state.sim_time_sec
        drives = DriveVectorV1(**pet_state.drives)
        pos = list(pet_state.position_xyz)
        cheek_pouch_fill = pet_state.cheek_pouch_fill
        inside_hideout = pet_state.inside_hideout
        inside_tunnel = pet_state.inside_tunnel
        on_wheel = pet_state.on_wheel

        simulated_sec_accum = 0.0
        events: List[WorldEvent] = []
        tick = current_tick
        step_count = 0

        while simulated_sec_accum < sim_sec_budget and step_count < self.max_steps_per_run:
            # Lightweight observation
            obs = ObservationV1(
                sim_time_sec=sim_time,
                position_xyz=pos,
                yaw_rad=pet_state.yaw_rad,
                velocity_xy=list(pet_state.velocity_xy),
                angular_velocity_z=pet_state.angular_velocity_z,
                inside_hideout=inside_hideout,
                inside_tunnel=inside_tunnel,
                on_wheel=on_wheel,
                cheek_pouch_fill=cheek_pouch_fill,
                drives=drives,
                nearby_objects=[],
            )

            # High-level policy selects next skill
            skill_name = self.policy.select_skill(obs)

            # Step context for empirical model
            ctx = {
                "dist_to_target_m": 0.25,
                "drives": drives.model_dump(),
                "position_xyz": pos,
                "cheek_pouch_fill": cheek_pouch_fill,
            }

            step_seed = int((seed_base + tick * 1009) % (2**31 - 1))
            rng = np.random.default_rng(step_seed)

            # Sample skill outcome (Rule 2: origin enforcement)
            outcome: SkillOutcome = sample_skill_outcome(skill_name, ctx, rng=rng)

            # Deterministic Event ID (P2.2 Criterion 2)
            event_id = generate_deterministic_event_id(
                pet_id=pet_state.pet_id,
                world_tick=tick,
                event_type="skill_completed",
                seed=step_seed,
            )

            # Record event
            event = WorldEvent(
                event_id=event_id,
                pet_id=pet_state.pet_id,
                world_tick=tick,
                sim_time_sec=round(sim_time + outcome.duration_sec, 3),
                event_type="skill_completed",
                skill_name=skill_name,
                origin=outcome.origin.value,
                behaviour_type=outcome.behaviour_type.value,
                seed=step_seed,
                payload={
                    "duration_sec": round(outcome.duration_sec, 2),
                    "success": outcome.success,
                    "energy_cost": round(outcome.energy_cost, 4),
                    "collision_count": outcome.collision_count,
                    "delta_drives": {k: round(v, 4) for k, v in outcome.delta_drives.items()},
                    "final_drives": outcome.final_drives.model_dump(),
                    "final_pos_xyz": [round(x, 4) for x in outcome.final_pos_xyz],
                },
                created_at=curr_time,
            )
            events.append(event)

            # Advance loop state
            sim_time += outcome.duration_sec
            simulated_sec_accum += outcome.duration_sec
            drives = outcome.final_drives
            pos = outcome.final_pos_xyz
            cheek_pouch_fill = outcome.final_cheek_pouch_fill
            inside_hideout = outcome.final_flags.get("inside_hideout", False)
            inside_tunnel = outcome.final_flags.get("inside_tunnel", False)
            on_wheel = outcome.final_flags.get("on_wheel", False)

            tick += 1
            step_count += 1

        # Calculate remaining catchup
        remaining_sim_sec = max(0.0, target_sim_sec - simulated_sec_accum)

        # 4. Write Catch-Up Summary Event (P2.2 Criterion 5)
        if step_count > 0:
            summary_type = (
                "catch_up_in_progress" if remaining_sim_sec > 15.0 else "catch_up_completed"
            )
            summary_seed = int((seed_base + tick * 1009) % (2**31 - 1))
            summary_event_id = generate_deterministic_event_id(
                pet_id=pet_state.pet_id,
                world_tick=tick,
                event_type=summary_type,
                seed=summary_seed,
            )

            summary_event = WorldEvent(
                event_id=summary_event_id,
                pet_id=pet_state.pet_id,
                world_tick=tick,
                sim_time_sec=round(sim_time, 3),
                event_type=summary_type,
                skill_name=None,
                origin=EventOrigin.RULE.value,
                behaviour_type=BehaviourType.RULE.value,
                seed=summary_seed,
                payload={
                    "simulated_sec": round(simulated_sec_accum, 2),
                    "remaining_sim_sec": round(remaining_sim_sec, 2),
                    "steps_executed": step_count,
                    "real_time_scale": pet_state.real_time_scale,
                },
                created_at=curr_time,
            )
            events.append(summary_event)
            tick += 1

        # Advance real-time tracker proportionally to simulated time consumed
        real_sec_consumed = simulated_sec_accum / max(1e-4, pet_state.real_time_scale)
        new_last_simulated_at = last_sim + datetime.timedelta(seconds=real_sec_consumed)

        # Compute age in days
        birth = _ensure_utc(pet.birth_date) if pet.birth_date else curr_time - datetime.timedelta(days=30)
        base_age_days = max(0.0, (last_sim - birth).total_seconds() / 86400.0)
        new_simulated_age_days = round(base_age_days + (sim_time / 86400.0), 4)

        return {
            "steps_executed": step_count,
            "simulated_sec": simulated_sec_accum,
            "remaining_sim_sec": remaining_sim_sec,
            "events": events,
            "new_last_simulated_at": new_last_simulated_at,
            "new_sim_time_sec": round(sim_time, 3),
            "new_simulated_age_days": new_simulated_age_days,
            "new_drives": drives.model_dump(),
            "new_position_xyz": pos,
            "new_flags": {
                "inside_hideout": inside_hideout,
                "inside_tunnel": inside_tunnel,
                "on_wheel": on_wheel,
                "cheek_pouch_fill": cheek_pouch_fill,
            },
            "status": "in_progress" if remaining_sim_sec > 15.0 else "completed",
        }

