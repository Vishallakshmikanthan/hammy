"""
HAMMY — Shared Command Handler Implementation (`services/commands/handler.py`).
Implements shared command execution for the API and Telegram bot.
Enforces client idempotency (Rule 4), command parameter validation, and atomic commits.
"""

from __future__ import annotations

import datetime
import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from contracts.schemas import BehaviourType, EventOrigin
from infrastructure.database.models import (
    CareAction,
    Command,
    Habitat,
    HabitatObject,
    Pet,
    PetState,
    WorldEvent,
)


class CommandValidationError(ValueError):
    """Raised when command parameters violate physical or business constraints."""


@dataclass
class CommandResult:
    command_id: str
    status: str  # 'completed' | 'failed' | 'ignored'
    message: str
    result: Dict[str, Any] = field(default_factory=dict)
    idempotent_replay: bool = False


class CommandHandler:
    """
    Decoupled command layer executed by both FastAPI routes and Telegram bot handlers.
    Never mutates database without verifying idempotency and parameter boundaries.
    """

    ALLOWED_ENRICHMENTS = {
        "chew_toy",
        "cardboard_tube",
        "foraging_scatter",
        "sprig",
        "tunnel_extension",
    }

    def execute_command(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        command_type: str,
        parameters: Dict[str, Any],
        now: Optional[datetime.datetime] = None,
    ) -> CommandResult:
        """
        Executes a validated command idempotently:
          - If command_id already completed: returns cached result (idempotent replay).
          - Otherwise executes mutation, logs care action & world event, and records completed command.
        """
        curr_time = now or datetime.datetime.now(datetime.timezone.utc)
        if curr_time.tzinfo is None:
            curr_time = curr_time.replace(tzinfo=datetime.timezone.utc)

        # 1. Idempotency Check (Rule 4 & P2.3 AC-3)
        existing = session.get(Command, command_id)
        if existing is not None:
            if existing.status == "completed":
                cached_res = existing.parameters.get("result", {})
                return CommandResult(
                    command_id=command_id,
                    status="completed",
                    message="Command already processed (idempotent replay)",
                    result=cached_res,
                    idempotent_replay=True,
                )

        # 2. Verify Pet Exists
        pet = session.get(Pet, pet_id)
        if not pet:
            raise CommandValidationError(f"Pet '{pet_id}' not found.")

        # Ensure Command row exists for FK references
        if existing is None:
            existing = Command(
                command_id=command_id,
                pet_id=pet_id,
                user_id=user_id,
                command_type=command_type,
                parameters=dict(parameters),
                status="processing",
                created_at=curr_time,
            )
            session.add(existing)
            session.flush()

        # 3. Dispatch to specific handler
        if command_type == "feed":
            res = self._handle_feed(session, user_id, pet_id, command_id, parameters, curr_time)
        elif command_type == "water":
            res = self._handle_water(session, user_id, pet_id, command_id, parameters, curr_time)
        elif command_type == "add_enrichment":
            res = self._handle_enrichment(session, user_id, pet_id, command_id, parameters, curr_time)
        elif command_type == "pause":
            res = self._handle_pause(session, user_id, pet_id, command_id, curr_time)
        elif command_type == "resume":
            res = self._handle_resume(session, user_id, pet_id, command_id, curr_time)
        elif command_type == "move_object":
            res = self._handle_move_object(session, user_id, pet_id, command_id, parameters, curr_time)
        else:
            raise CommandValidationError(f"Unsupported command type '{command_type}'.")

        # 4. Mark Command Completed
        existing.status = "completed"
        existing.parameters = {**parameters, "result": res.result}
        existing.processed_at = curr_time

        session.commit()
        return res

    def _next_world_tick(self, session: Session, pet_id: str) -> int:
        max_tick = (
            session.query(func.max(WorldEvent.world_tick))
            .filter(WorldEvent.pet_id == pet_id)
            .scalar()
        )
        return (max_tick or 0) + 1

    def _handle_feed(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        amount_grams = float(params.get("amount_grams", 0.0))
        if amount_grams <= 0.0:
            raise CommandValidationError("amount_grams must be strictly positive (> 0.0).")
        if amount_grams > 25.0:
            raise CommandValidationError("amount_grams cannot exceed 25.0 grams (bowl capacity).")

        # Find food bowl
        habitat = session.query(Habitat).filter_by(pet_id=pet_id).first()
        bowl = None
        if habitat:
            bowl = (
                session.query(HabitatObject)
                .filter(
                    HabitatObject.habitat_id == habitat.id,
                    HabitatObject.object_type == "food_bowl",
                )
                .first()
            )

        if not bowl:
            raise CommandValidationError("No food bowl found in pet habitat.")

        # Update food bowl resource level
        res_state = dict(bowl.resource_state)
        capacity = float(res_state.get("capacity_grams", 25.0))
        curr_level = float(res_state.get("food_level", 0.0))
        curr_grams = curr_level * capacity
        new_grams = min(capacity, curr_grams + amount_grams)
        new_level = round(new_grams / capacity, 4)

        res_state["food_level"] = new_level
        bowl.resource_state = res_state
        bowl.updated_at = now

        # Log CareAction
        care_act = CareAction(
            id=f"act_feed_{uuid.uuid4().hex[:12]}",
            command_id=command_id,
            user_id=user_id,
            pet_id=pet_id,
            action_type="feed",
            parameters={"amount_grams": amount_grams, "food_level": new_level},
            applied_at=now,
        )
        session.add(care_act)

        # Log WorldEvent
        tick = self._next_world_tick(session, pet_id)
        pet_state = session.get(PetState, pet_id)
        sim_time = pet_state.sim_time_sec if pet_state else 0.0

        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_feed_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="care_feed",
            skill_name=None,
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={"amount_grams": amount_grams, "new_food_level": new_level},
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Added {amount_grams:.1f}g food to bowl. Food level is now {new_level * 100:.1f}%.",
            result={"amount_grams": amount_grams, "new_food_level": new_level},
            idempotent_replay=False,
        )

    def _handle_water(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        amount_ml = float(params.get("amount_ml", 0.0))
        if amount_ml <= 0.0:
            raise CommandValidationError("amount_ml must be strictly positive (> 0.0).")
        if amount_ml > 150.0:
            raise CommandValidationError("amount_ml cannot exceed 150.0 ml (bottle capacity).")

        habitat = session.query(Habitat).filter_by(pet_id=pet_id).first()
        bottle = None
        if habitat:
            bottle = (
                session.query(HabitatObject)
                .filter(
                    HabitatObject.habitat_id == habitat.id,
                    HabitatObject.object_type == "water_bottle",
                )
                .first()
            )

        if not bottle:
            raise CommandValidationError("No water bottle found in pet habitat.")

        res_state = dict(bottle.resource_state)
        capacity = float(res_state.get("capacity_ml", 150.0))
        curr_level = float(res_state.get("water_level", 0.0))
        curr_ml = curr_level * capacity
        new_ml = min(capacity, curr_ml + amount_ml)
        new_level = round(new_ml / capacity, 4)

        res_state["water_level"] = new_level
        bottle.resource_state = res_state
        bottle.updated_at = now

        care_act = CareAction(
            id=f"act_water_{uuid.uuid4().hex[:12]}",
            command_id=command_id,
            user_id=user_id,
            pet_id=pet_id,
            action_type="water",
            parameters={"amount_ml": amount_ml, "water_level": new_level},
            applied_at=now,
        )
        session.add(care_act)

        tick = self._next_world_tick(session, pet_id)
        pet_state = session.get(PetState, pet_id)
        sim_time = pet_state.sim_time_sec if pet_state else 0.0

        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_water_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="care_water",
            skill_name=None,
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={"amount_ml": amount_ml, "new_water_level": new_level},
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Refilled {amount_ml:.1f}ml water. Water level is now {new_level * 100:.1f}%.",
            result={"amount_ml": amount_ml, "new_water_level": new_level},
            idempotent_replay=False,
        )

    def _handle_enrichment(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        enrichment_type = str(params.get("enrichment_type", ""))
        if enrichment_type not in self.ALLOWED_ENRICHMENTS:
            raise CommandValidationError(
                f"Invalid enrichment_type '{enrichment_type}'. Allowed types: {sorted(list(self.ALLOWED_ENRICHMENTS))}"
            )

        care_act = CareAction(
            id=f"act_enrich_{uuid.uuid4().hex[:12]}",
            command_id=command_id,
            user_id=user_id,
            pet_id=pet_id,
            action_type="add_enrichment",
            parameters={"enrichment_type": enrichment_type, "params": params},
            applied_at=now,
        )
        session.add(care_act)

        tick = self._next_world_tick(session, pet_id)
        pet_state = session.get(PetState, pet_id)
        sim_time = pet_state.sim_time_sec if pet_state else 0.0

        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_enrich_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="enrichment_added",
            skill_name=None,
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={"enrichment_type": enrichment_type},
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Added enrichment '{enrichment_type}'.",
            result={"enrichment_type": enrichment_type},
            idempotent_replay=False,
        )

    def _handle_pause(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        now: datetime.datetime,
    ) -> CommandResult:
        pet_state = session.get(PetState, pet_id)
        if not pet_state:
            raise CommandValidationError(f"PetState not found for '{pet_id}'.")

        pet_state.is_paused = True
        pet_state.version += 1
        pet_state.updated_at = now

        tick = self._next_world_tick(session, pet_id)
        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_pause_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=pet_state.sim_time_sec,
            event_type="simulation_paused",
            skill_name=None,
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={"is_paused": True},
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message="Simulation paused.",
            result={"is_paused": True},
            idempotent_replay=False,
        )

    def _handle_resume(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        now: datetime.datetime,
    ) -> CommandResult:
        pet_state = session.get(PetState, pet_id)
        if not pet_state:
            raise CommandValidationError(f"PetState not found for '{pet_id}'.")

        pet_state.is_paused = False
        pet_state.last_simulated_at = now  # Reset catchup baseline upon unpausing
        pet_state.version += 1
        pet_state.updated_at = now

        tick = self._next_world_tick(session, pet_id)
        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_resume_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=pet_state.sim_time_sec,
            event_type="simulation_resumed",
            skill_name=None,
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={"is_paused": False},
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message="Simulation resumed.",
            result={"is_paused": False},
            idempotent_replay=False,
        )

    def _handle_move_object(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        object_id = str(params.get("object_id", ""))
        new_pos = params.get("new_pose_xyz_m")
        if not object_id or not new_pos or len(new_pos) != 3:
            raise CommandValidationError("move_object requires object_id and new_pose_xyz_m [x, y, z].")

        obj = session.get(HabitatObject, object_id)
        if not obj:
            raise CommandValidationError(f"Object '{object_id}' not found.")

        habitat = session.get(Habitat, obj.habitat_id)
        if habitat and habitat.floor_bounds:
            bounds = habitat.floor_bounds
            x, y = float(new_pos[0]), float(new_pos[1])
            x_min, x_max = float(bounds.get("x_min", -0.5)), float(bounds.get("x_max", 0.5))
            y_min, y_max = float(bounds.get("y_min", -0.25)), float(bounds.get("y_max", 0.25))
            if not (x_min <= x <= x_max and y_min <= y <= y_max):
                raise CommandValidationError(f"Coordinates [{x}, {y}] outside habitat bounds.")

        obj.pose_xyz_m = [float(v) for v in new_pos]
        obj.updated_at = now

        tick = self._next_world_tick(session, pet_id)
        pet_state = session.get(PetState, pet_id)
        sim_time = pet_state.sim_time_sec if pet_state else 0.0

        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_move_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="object_moved",
            skill_name=None,
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={"object_id": object_id, "new_pose_xyz_m": obj.pose_xyz_m},
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Object '{object_id}' moved to {obj.pose_xyz_m}.",
            result={"object_id": object_id, "new_pose_xyz_m": obj.pose_xyz_m},
            idempotent_replay=False,
        )
