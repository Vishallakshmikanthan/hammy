"""
HAMMY — Shared Command Handler Implementation (`services/commands/handler.py`).
Implements shared command execution for the API and Telegram bot.
Enforces client idempotency (Rule 4), command parameter validation, and atomic commits.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field
from pathlib import Path
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

MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "manifest.json"


def load_asset_manifest() -> Dict[str, Any]:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"items": [], "cage_bounds_m": {"min_x": -0.44, "max_x": 0.44, "min_y": -0.19, "max_y": 0.19, "floor_z": 0.155}}


def get_manifest_item_map() -> Dict[str, Dict[str, Any]]:
    manifest = load_asset_manifest()
    return {item["id"]: item for item in manifest.get("items", [])}



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
        elif command_type == "offer_food":
            res = self._handle_offer_food(session, user_id, pet_id, command_id, parameters, curr_time)
        elif command_type == "refill_water":
            res = self._handle_refill_water(session, user_id, pet_id, command_id, parameters, curr_time)
        elif command_type == "equip_costume":
            res = self._handle_equip_costume(session, user_id, pet_id, command_id, parameters, curr_time)
        elif command_type == "unequip_costume":
            res = self._handle_unequip_costume(session, user_id, pet_id, command_id, parameters, curr_time)
        elif command_type == "place_prop":
            res = self._handle_place_prop(session, user_id, pet_id, command_id, parameters, curr_time)
        elif command_type == "move_prop":
            res = self._handle_move_prop(session, user_id, pet_id, command_id, parameters, curr_time)
        elif command_type == "remove_prop":
            res = self._handle_remove_prop(session, user_id, pet_id, command_id, parameters, curr_time)
        elif command_type == "consume_food":
            res = self._handle_consume_food(session, user_id, pet_id, command_id, parameters, curr_time)
        elif command_type == "consume_water":
            res = self._handle_consume_water(session, user_id, pet_id, command_id, parameters, curr_time)
        elif command_type == "reset_clean_cage":
            res = self._handle_reset_clean_cage(session, user_id, pet_id, command_id, parameters, curr_time)
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

    # ==========================================================================
    # STEP 6: SHELF-BASED OPT-IN ASSET COMMANDS (Server-Authoritative & Idempotent)
    # ==========================================================================

    def _validate_cage_pose(
        self,
        session: Session,
        habitat: Habitat,
        pose_xyz_m: List[float],
        collision_radius_m: float,
        exclude_object_id: Optional[str] = None,
    ) -> List[float]:
        if not isinstance(pose_xyz_m, (list, tuple)) or len(pose_xyz_m) != 3:
            raise CommandValidationError("pose_xyz_m must be a 3-element [x, y, z] list in meters.")
        x, y, z = float(pose_xyz_m[0]), float(pose_xyz_m[1]), float(pose_xyz_m[2])
        bounds = habitat.floor_bounds or {"x_min": -0.44, "x_max": 0.44, "y_min": -0.19, "y_max": 0.19}
        x_min = max(-0.46, float(bounds.get("x_min", -0.44)))
        x_max = min(0.46, float(bounds.get("x_max", 0.44)))
        y_min = max(-0.22, float(bounds.get("y_min", -0.19)))
        y_max = min(0.22, float(bounds.get("y_max", 0.19)))

        if not (x_min <= x <= x_max and y_min <= y <= y_max):
            raise CommandValidationError(
                f"Placement [{x:.3f}, {y:.3f}] is outside cage bounds ([{x_min:.2f}, {x_max:.2f}] x [{y_min:.2f}, {y_max:.2f}] m)."
            )

        # Overlap validation against other placed props/decor/water items (excluding costume_equips and walkable patches)
        existing_objs = session.query(HabitatObject).filter_by(habitat_id=habitat.id).all()
        for other in existing_objs:
            if other.id == exclude_object_id:
                continue
            if other.object_type in ("costume_equip", "offered_food"):
                continue
            other_res = other.resource_state or {}
            if other_res.get("asset_id") == "decor_bedding_patch":
                continue
            ox, oy = float(other.pose_xyz_m[0]), float(other.pose_xyz_m[1])
            dist = math.hypot(x - ox, y - oy)
            min_sep = max(0.035, (collision_radius_m + float(other.interaction_radius_m)) * 0.55)
            if dist < min_sep:
                raise CommandValidationError(
                    f"Placement [{x:.3f}, {y:.3f}] overlaps existing item '{other.id}' at [{ox:.3f}, {oy:.3f}] (dist={dist:.3f}m < {min_sep:.3f}m)."
                )
        return [round(x, 4), round(y, 4), round(z, 4)]

    def _get_or_create_habitat(self, session: Session, pet_id: str, now: datetime.datetime) -> Habitat:
        habitat = session.query(Habitat).filter_by(pet_id=pet_id).first()
        if not habitat:
            habitat = Habitat(
                id="habitat_v1_main",
                pet_id=pet_id,
                environment_version="habitat_v1",
                name="Hammy's Habitat",
                dimensions_xyz={"length_x": 1.0, "width_y": 0.5, "wall_height_z": 0.4, "bedding_surface_z": 0.165},
                floor_bounds={"x_min": -0.44, "x_max": 0.44, "y_min": -0.19, "y_max": 0.19},
                created_at=now,
            )
            session.add(habitat)
            session.flush()
        return habitat

    def _handle_offer_food(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        item_id = str(params.get("item_id", ""))
        quantity = int(params.get("quantity", 1))
        if quantity < 1 or quantity > 10:
            raise CommandValidationError("quantity must be between 1 and 10 portions.")

        manifest_map = get_manifest_item_map()
        item_meta = manifest_map.get(item_id)
        if not item_meta:
            raise CommandValidationError(f"Unknown food item_id '{item_id}' (not in manifest.json).")
        if item_meta.get("category") != "food":
            raise CommandValidationError(f"Asset '{item_id}' is category '{item_meta.get('category')}', not 'food'.")
        if not item_meta.get("hamster_safe", False):
            raise CommandValidationError(f"Food '{item_id}' is not flagged hamster_safe in manifest.json.")

        habitat = self._get_or_create_habitat(session, pet_id, now)

        # If a food bowl is placed in the cage, place food at the bowl; otherwise place at offered spot
        bowl = (
            session.query(HabitatObject)
            .filter(
                HabitatObject.habitat_id == habitat.id,
                HabitatObject.object_type.in_(["food_bowl", "prop_food_bowl"]),
            )
            .first()
        )
        raw_pose = params.get("pose_xyz_m")
        if raw_pose and len(raw_pose) == 3:
            pose = [round(float(v), 4) for v in raw_pose]
        elif bowl:
            pose = [round(float(bowl.pose_xyz_m[0]), 4), round(float(bowl.pose_xyz_m[1]), 4), 0.168]
        else:
            pose = [0.18, -0.06, 0.165]

        bounds = habitat.floor_bounds or {"x_min": -0.44, "x_max": 0.44, "y_min": -0.19, "y_max": 0.19}
        if not (float(bounds.get("x_min", -0.46)) <= pose[0] <= float(bounds.get("x_max", 0.46)) and
                float(bounds.get("y_min", -0.22)) <= pose[1] <= float(bounds.get("y_max", 0.22))):
            raise CommandValidationError(f"Food offer position {pose} is outside cage bounds.")

        pet_state = session.get(PetState, pet_id)
        sim_time = pet_state.sim_time_sec if pet_state else 0.0
        spoil_after_sec = float(params.get("spoil_after_sec", 600.0))

        obj_id = f"offered_{item_id}_{command_id[:8]}"
        food_obj = HabitatObject(
            id=obj_id,
            habitat_id=habitat.id,
            object_type="offered_food",
            blender_name=item_id,
            pose_xyz_m=pose,
            interaction_radius_m=float(item_meta.get("collision_radius_m", 0.025)),
            affordances=["eat", "hoard"],
            resource_state={
                "asset_id": item_id,
                "name": item_meta["name"],
                "category": "food",
                "quantity": quantity,
                "initial_quantity": quantity,
                "hamster_safe": True,
                "offered_at_sim_sec": sim_time,
                "spoils_at_sim_sec": sim_time + spoil_after_sec,
                "spoiled": False,
                "rotation_y_rad": 0.0,
            },
            updated_at=now,
        )
        session.add(food_obj)

        if bowl:
            b_res = dict(bowl.resource_state or {})
            b_res["food_level"] = min(1.0, round(float(b_res.get("food_level", 0.0)) + 0.15 * quantity, 4))
            b_res["last_offered_food"] = item_id
            bowl.resource_state = b_res
            bowl.updated_at = now

        tick = self._next_world_tick(session, pet_id)
        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_offer_food_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="food_offered",
            skill_name="eat",
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={
                "object_id": obj_id,
                "item_id": item_id,
                "name": item_meta["name"],
                "quantity": quantity,
                "pose_xyz_m": pose,
                "spoils_at_sim_sec": sim_time + spoil_after_sec,
            },
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Offered {quantity}x {item_meta['name']} at {pose}.",
            result={
                "object_id": obj_id,
                "item_id": item_id,
                "name": item_meta["name"],
                "quantity": quantity,
                "pose_xyz_m": pose,
                "spoils_at_sim_sec": sim_time + spoil_after_sec,
            },
            idempotent_replay=False,
        )

    def _handle_refill_water(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        amount_ml = float(params.get("amount_ml", 150.0))
        if amount_ml <= 0.0 or amount_ml > 300.0:
            raise CommandValidationError("amount_ml must be in (0.0, 300.0].")

        habitat = self._get_or_create_habitat(session, pet_id, now)
        water_objs = (
            session.query(HabitatObject)
            .filter(
                HabitatObject.habitat_id == habitat.id,
                HabitatObject.object_type.in_(["water_bottle", "water_bowl"]),
            )
            .all()
        )
        if not water_objs:
            # Auto-restore basic default water bottle if missing
            default_bottle = HabitatObject(
                id="prop_bottle_main",
                habitat_id=habitat.id,
                object_type="water_bottle",
                blender_name="water_bottle",
                pose_xyz_m=[0.433, -0.02, 0.183],
                interaction_radius_m=0.045,
                affordances=["drink"],
                resource_state={"asset_id": "water_bottle", "water_level": 0.5, "capacity_ml": 150.0},
                updated_at=now,
            )
            session.add(default_bottle)
            session.flush()
            water_objs = [default_bottle]

        new_levels = {}
        for wobj in water_objs:
            res_state = dict(wobj.resource_state or {})
            cap = float(res_state.get("capacity_ml", 150.0))
            curr = float(res_state.get("water_level", 0.5)) * cap
            new_lvl = round(min(cap, curr + amount_ml) / cap, 4)
            res_state["water_level"] = new_lvl
            wobj.resource_state = res_state
            wobj.updated_at = now
            new_levels[wobj.id] = new_lvl

        primary_level = list(new_levels.values())[0]
        tick = self._next_world_tick(session, pet_id)
        pet_state = session.get(PetState, pet_id)
        sim_time = pet_state.sim_time_sec if pet_state else 0.0

        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_refill_water_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="water_refilled",
            skill_name="drink",
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={"amount_ml": amount_ml, "new_water_level": primary_level, "sources": new_levels},
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Refilled water to {primary_level * 100:.0f}%.",
            result={"amount_ml": amount_ml, "new_water_level": primary_level, "sources": new_levels},
            idempotent_replay=False,
        )

    def _handle_equip_costume(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        item_id = str(params.get("item_id", ""))
        manifest_map = get_manifest_item_map()
        item_meta = manifest_map.get(item_id)
        if not item_meta:
            raise CommandValidationError(f"Unknown costume item_id '{item_id}' (not in manifest.json).")
        if item_meta.get("category") != "costume":
            raise CommandValidationError(f"Asset '{item_id}' is category '{item_meta.get('category')}', not 'costume'.")

        slot = item_meta.get("attachment_slot")
        if slot not in ("head_slot", "neck_slot", "back_slot"):
            raise CommandValidationError(f"Invalid costume attachment_slot '{slot}'.")

        habitat = self._get_or_create_habitat(session, pet_id, now)
        slot_obj_id = f"equip_{slot}"
        equip_obj = session.get(HabitatObject, slot_obj_id)
        if not equip_obj:
            equip_obj = HabitatObject(
                id=slot_obj_id,
                habitat_id=habitat.id,
                object_type="costume_equip",
                blender_name=item_id,
                pose_xyz_m=[0.0, 0.0, 0.0],
                interaction_radius_m=0.01,
                affordances=["wear"],
                resource_state={
                    "asset_id": item_id,
                    "name": item_meta["name"],
                    "slot": slot,
                    "category": "costume",
                },
                updated_at=now,
            )
            session.add(equip_obj)
        else:
            equip_obj.blender_name = item_id
            equip_obj.resource_state = {
                "asset_id": item_id,
                "name": item_meta["name"],
                "slot": slot,
                "category": "costume",
            }
            equip_obj.updated_at = now

        tick = self._next_world_tick(session, pet_id)
        pet_state = session.get(PetState, pet_id)
        sim_time = pet_state.sim_time_sec if pet_state else 0.0

        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_equip_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="costume_equipped",
            skill_name=None,
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={"item_id": item_id, "name": item_meta["name"], "slot": slot},
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Equipped '{item_meta['name']}' to {slot}.",
            result={"item_id": item_id, "name": item_meta["name"], "slot": slot},
            idempotent_replay=False,
        )

    def _handle_unequip_costume(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        slot = params.get("slot")  # "head_slot" | "neck_slot" | "back_slot" | "all" | None
        item_id = params.get("item_id")
        habitat = self._get_or_create_habitat(session, pet_id, now)

        query = session.query(HabitatObject).filter(
            HabitatObject.habitat_id == habitat.id,
            HabitatObject.object_type == "costume_equip",
        )
        equips = query.all()
        removed_slots = []
        for eq in equips:
            eq_slot = (eq.resource_state or {}).get("slot")
            eq_asset = (eq.resource_state or {}).get("asset_id")
            if slot in (None, "all") or eq_slot == slot or (item_id and eq_asset == item_id):
                removed_slots.append(eq_slot or eq.id)
                session.delete(eq)

        tick = self._next_world_tick(session, pet_id)
        pet_state = session.get(PetState, pet_id)
        sim_time = pet_state.sim_time_sec if pet_state else 0.0

        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_unequip_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="costume_unequipped",
            skill_name=None,
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={"slot": slot or "all", "removed_slots": removed_slots},
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Unequipped costume slots: {removed_slots or ['none']}.",
            result={"removed_slots": removed_slots},
            idempotent_replay=False,
        )

    def _handle_place_prop(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        item_id = str(params.get("item_id", ""))
        manifest_map = get_manifest_item_map()
        item_meta = manifest_map.get(item_id)
        if not item_meta:
            raise CommandValidationError(f"Unknown asset item_id '{item_id}' (not in manifest.json).")
        cat = item_meta.get("category")
        if cat not in ("prop", "decor", "water"):
            raise CommandValidationError(f"Asset '{item_id}' (category '{cat}') cannot be placed as a habitat prop/decor.")

        habitat = self._get_or_create_habitat(session, pet_id, now)
        raw_pose = params.get("pose_xyz_m", [0.0, 0.0, 0.165])
        rotation_y_rad = float(params.get("rotation_y_rad", 0.0))
        col_r = float(item_meta.get("collision_radius_m", 0.045))

        valid_pose = self._validate_cage_pose(session, habitat, raw_pose, col_r)

        obj_id = str(params.get("object_id") or f"placed_{item_id}_{command_id[:8]}")
        obj_type = "water_bowl" if item_id == "water_bowl" else ("water_bottle" if item_id == "water_bottle" else ("food_bowl" if item_id == "prop_food_bowl" else f"placed_{cat}"))

        affordances = ["explore"]
        res_state: Dict[str, Any] = {
            "asset_id": item_id,
            "name": item_meta["name"],
            "category": cat,
            "rotation_y_rad": round(rotation_y_rad, 4),
            "dimensions_m": item_meta.get("dimensions_m", [0.08, 0.08, 0.08]),
            "collision_radius_m": col_r,
        }
        if item_id in ("water_bottle", "water_bowl"):
            affordances = ["drink"]
            res_state["water_level"] = 1.0
            res_state["capacity_ml"] = 150.0 if item_id == "water_bottle" else 60.0
        elif item_id == "prop_food_bowl":
            affordances = ["eat", "hoard"]
            res_state["food_level"] = 0.0
            res_state["capacity_grams"] = 25.0
        elif "wheel" in item_id:
            affordances = ["run_wheel", "explore"]
        elif "hideout" in item_id:
            affordances = ["rest", "hide", "sleep"]
        elif "tunnel" in item_id:
            affordances = ["enter_tunnel", "hide", "explore"]
        elif "chew" in item_id:
            affordances = ["gnaw", "explore"]

        placed_obj = HabitatObject(
            id=obj_id,
            habitat_id=habitat.id,
            object_type=obj_type,
            blender_name=item_id,
            pose_xyz_m=valid_pose,
            interaction_radius_m=col_r,
            affordances=affordances,
            resource_state=res_state,
            updated_at=now,
        )
        session.add(placed_obj)

        tick = self._next_world_tick(session, pet_id)
        pet_state = session.get(PetState, pet_id)
        sim_time = pet_state.sim_time_sec if pet_state else 0.0

        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_place_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="prop_placed",
            skill_name=None,
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={
                "object_id": obj_id,
                "item_id": item_id,
                "name": item_meta["name"],
                "category": cat,
                "pose_xyz_m": valid_pose,
                "rotation_y_rad": round(rotation_y_rad, 4),
            },
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Placed '{item_meta['name']}' at {valid_pose}.",
            result={
                "object_id": obj_id,
                "item_id": item_id,
                "name": item_meta["name"],
                "category": cat,
                "pose_xyz_m": valid_pose,
                "rotation_y_rad": round(rotation_y_rad, 4),
            },
            idempotent_replay=False,
        )

    def _handle_move_prop(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        object_id = str(params.get("object_id", ""))
        new_pose = params.get("pose_xyz_m") or params.get("new_pose_xyz_m")
        rotation_y_rad = params.get("rotation_y_rad")

        obj = session.get(HabitatObject, object_id)
        if not obj:
            raise CommandValidationError(f"Placed object '{object_id}' not found.")

        habitat = session.get(Habitat, obj.habitat_id) or self._get_or_create_habitat(session, pet_id, now)
        valid_pose = self._validate_cage_pose(
            session,
            habitat,
            new_pose,
            float(obj.interaction_radius_m),
            exclude_object_id=obj.id,
        )

        obj.pose_xyz_m = valid_pose
        if rotation_y_rad is not None:
            res = dict(obj.resource_state or {})
            res["rotation_y_rad"] = round(float(rotation_y_rad), 4)
            obj.resource_state = res
        obj.updated_at = now

        tick = self._next_world_tick(session, pet_id)
        pet_state = session.get(PetState, pet_id)
        sim_time = pet_state.sim_time_sec if pet_state else 0.0

        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_move_prop_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="prop_moved",
            skill_name=None,
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={
                "object_id": object_id,
                "pose_xyz_m": valid_pose,
                "rotation_y_rad": (obj.resource_state or {}).get("rotation_y_rad", 0.0),
            },
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Moved '{object_id}' to {valid_pose}.",
            result={
                "object_id": object_id,
                "pose_xyz_m": valid_pose,
                "rotation_y_rad": (obj.resource_state or {}).get("rotation_y_rad", 0.0),
            },
            idempotent_replay=False,
        )

    def _handle_remove_prop(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        object_id = str(params.get("object_id", ""))
        obj = session.get(HabitatObject, object_id)
        if not obj:
            raise CommandValidationError(f"Placed object '{object_id}' not found.")

        item_id = (obj.resource_state or {}).get("asset_id", obj.blender_name)
        session.delete(obj)

        tick = self._next_world_tick(session, pet_id)
        pet_state = session.get(PetState, pet_id)
        sim_time = pet_state.sim_time_sec if pet_state else 0.0

        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_remove_prop_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="prop_removed",
            skill_name=None,
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={"object_id": object_id, "item_id": item_id},
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Removed '{object_id}' back to shelf.",
            result={"object_id": object_id, "item_id": item_id},
            idempotent_replay=False,
        )

    def _handle_consume_food(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        """Server-authoritative eating interaction: decreases offered food quantity, lowers hunger, and fills cheek pouches."""
        object_id = params.get("object_id")
        habitat = self._get_or_create_habitat(session, pet_id, now)

        food_obj = session.get(HabitatObject, object_id) if object_id else None
        if not food_obj:
            food_obj = (
                session.query(HabitatObject)
                .filter(
                    HabitatObject.habitat_id == habitat.id,
                    HabitatObject.object_type == "offered_food",
                )
                .first()
            )
        if not food_obj:
            raise CommandValidationError("No offered food available in habitat to eat.")

        res_state = dict(food_obj.resource_state or {})
        item_id = res_state.get("asset_id", food_obj.blender_name)
        item_name = res_state.get("name", item_id)
        qty = int(res_state.get("quantity", 1))
        remaining = max(0, qty - 1)

        if remaining == 0:
            session.delete(food_obj)
        else:
            res_state["quantity"] = remaining
            food_obj.resource_state = res_state
            food_obj.updated_at = now

        pet_state = session.get(PetState, pet_id)
        new_pouch = 0.65
        new_hunger = 0.10
        sim_time = 0.0
        if pet_state:
            sim_time = pet_state.sim_time_sec
            drives = dict(pet_state.drives or {})
            new_hunger = round(max(0.0, float(drives.get("hunger", 0.35)) - 0.18), 4)
            drives["hunger"] = new_hunger
            pet_state.drives = drives
            new_pouch = round(min(1.0, float(pet_state.cheek_pouch_fill or 0.0) + 0.35), 4)
            pet_state.cheek_pouch_fill = new_pouch
            pet_state.active_skill = "eat"
            pet_state.version += 1
            pet_state.updated_at = now

        tick = self._next_world_tick(session, pet_id)
        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_eat_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="hamster_ate_food",
            skill_name="eat",
            origin=EventOrigin.OBSERVED_PHYSICS.value,
            behaviour_type=BehaviourType.SCRIPTED.value,  # ANIMATION-DRIVEN clip triggered by policy
            seed=0,
            payload={
                "object_id": food_obj.id,
                "item_id": item_id,
                "name": item_name,
                "remaining_quantity": remaining,
                "cheek_pouch_fill": new_pouch,
                "hunger": new_hunger,
                "honesty_label": "ANIMATION-DRIVEN",
            },
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Hammy ate {item_name} with both front paws (remaining={remaining}, cheek_pouch_fill={new_pouch:.2f}).",
            result={
                "object_id": food_obj.id,
                "item_id": item_id,
                "remaining_quantity": remaining,
                "cheek_pouch_fill": new_pouch,
                "hunger": new_hunger,
            },
            idempotent_replay=False,
        )

    def _handle_consume_water(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        """Server-authoritative drinking interaction: decreases water level and lowers thirst."""
        habitat = self._get_or_create_habitat(session, pet_id, now)
        wobj = (
            session.query(HabitatObject)
            .filter(
                HabitatObject.habitat_id == habitat.id,
                HabitatObject.object_type.in_(["water_bottle", "water_bowl"]),
            )
            .first()
        )
        if not wobj:
            raise CommandValidationError("No water source in habitat.")

        res_state = dict(wobj.resource_state or {})
        curr_lvl = float(res_state.get("water_level", 1.0))
        new_lvl = round(max(0.0, curr_lvl - 0.08), 4)
        res_state["water_level"] = new_lvl
        wobj.resource_state = res_state
        wobj.updated_at = now

        pet_state = session.get(PetState, pet_id)
        new_thirst = 0.08
        sim_time = 0.0
        if pet_state:
            sim_time = pet_state.sim_time_sec
            drives = dict(pet_state.drives or {})
            new_thirst = round(max(0.0, float(drives.get("thirst", 0.30)) - 0.20), 4)
            drives["thirst"] = new_thirst
            pet_state.drives = drives
            pet_state.active_skill = "drink"
            pet_state.version += 1
            pet_state.updated_at = now

        tick = self._next_world_tick(session, pet_id)
        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_drink_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=sim_time,
            event_type="hamster_drank_water",
            skill_name="drink",
            origin=EventOrigin.OBSERVED_PHYSICS.value,
            behaviour_type=BehaviourType.LEARNED.value,
            seed=0,
            payload={
                "object_id": wobj.id,
                "new_water_level": new_lvl,
                "thirst": new_thirst,
            },
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message=f"Hammy drank from {wobj.id} (water_level={new_lvl * 100:.0f}%).",
            result={"object_id": wobj.id, "new_water_level": new_lvl, "thirst": new_thirst},
            idempotent_replay=False,
        )

    def _handle_reset_clean_cage(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        command_id: str,
        params: Dict[str, Any],
        now: datetime.datetime,
    ) -> CommandResult:
        """
        Resets the cage to the core 3D habitat default state:
          - Hamster + Enclosure + Bedding
          - Home / Hideout (`prop_hideout_main`)
          - Logs / Tunnel (`prop_tunnel_main`)
          - Food Bowl (`prop_bowl_main`)
          - Water Tank / Bottle (`prop_bottle_main`)
          - Running Wheel (`prop_wheel_main`)
          - Chew Block (`prop_chew_block_main`)
        Clears all user-customized shelf additions (costumes, offered foods, extra placed props & decor).
        """
        habitat = self._get_or_create_habitat(session, pet_id, now)
        objs = session.query(HabitatObject).filter_by(habitat_id=habitat.id).all()
        for o in objs:
            session.delete(o)
        session.flush()

        default_core_objects = [
            HabitatObject(
                id="prop_bowl_main",
                habitat_id=habitat.id,
                object_type="food_bowl",
                blender_name="prop_bowl",
                pose_xyz_m=[0.28, -0.11, 0.165],
                interaction_radius_m=0.055,
                affordances=["eat", "hoard"],
                resource_state={"food_level": 1.0, "capacity_grams": 25.0},
                updated_at=now,
            ),
            HabitatObject(
                id="prop_bottle_main",
                habitat_id=habitat.id,
                object_type="water_bottle",
                blender_name="prop_bottle_spout",
                pose_xyz_m=[0.433, -0.02, 0.183],
                interaction_radius_m=0.045,
                affordances=["drink"],
                resource_state={
                    "asset_id": "water_bottle",
                    "name": "Ball-Spout Water Bottle",
                    "category": "water",
                    "water_level": 0.75,
                    "capacity_ml": 150.0,
                },
                updated_at=now,
            ),
            HabitatObject(
                id="prop_hideout_main",
                habitat_id=habitat.id,
                object_type="hideout",
                blender_name="prop_hideout",
                pose_xyz_m=[0.28, 0.11, 0.165],
                interaction_radius_m=0.065,
                affordances=["rest", "hide", "sleep", "nest"],
                resource_state={"hoard_food_level": 0.25, "bedding_comfort": 0.92},
                updated_at=now,
            ),
            HabitatObject(
                id="prop_tunnel_main",
                habitat_id=habitat.id,
                object_type="tunnel",
                blender_name="prop_tunnel_curve",
                pose_xyz_m=[-0.04, -0.05, 0.165],
                interaction_radius_m=0.055,
                affordances=["enter_tunnel", "hide", "explore"],
                resource_state={"resource_level": 1.0},
                updated_at=now,
            ),
            HabitatObject(
                id="prop_wheel_main",
                habitat_id=habitat.id,
                object_type="wheel",
                blender_name="prop_wheel_drum",
                pose_xyz_m=[-0.30, 0.13, 0.165],
                interaction_radius_m=0.085,
                affordances=["run_wheel", "explore"],
                resource_state={"resource_level": 1.0, "diameter_m": 0.28},
                updated_at=now,
            ),
            HabitatObject(
                id="prop_chew_block_main",
                habitat_id=habitat.id,
                object_type="chew_toy",
                blender_name="prop_chew_block",
                pose_xyz_m=[0.17, -0.05, 0.165],
                interaction_radius_m=0.035,
                affordances=["gnaw", "explore"],
                resource_state={"durability_level": 0.95},
                updated_at=now,
            ),
        ]
        for core_obj in default_core_objects:
            session.add(core_obj)

        pet_state = session.get(PetState, pet_id)
        if pet_state:
            pet_state.cheek_pouch_fill = 0.0
            pet_state.inside_hideout = False
            pet_state.inside_tunnel = False
            pet_state.on_wheel = False
            pet_state.version += 1
            pet_state.updated_at = now

        default_ids = [o.id for o in default_core_objects]
        tick = self._next_world_tick(session, pet_id)
        evt = WorldEvent(
            event_id=f"evt_{pet_id}_{tick}_clean_cage_{command_id[:12]}",
            pet_id=pet_id,
            world_tick=tick,
            sim_time_sec=pet_state.sim_time_sec if pet_state else 0.0,
            event_type="cage_reset_clean_minimal",
            skill_name=None,
            origin=EventOrigin.RULE.value,
            behaviour_type=BehaviourType.RULE.value,
            seed=0,
            payload={"default_objects": default_ids},
            created_at=now,
        )
        session.add(evt)

        return CommandResult(
            command_id=command_id,
            status="completed",
            message="Reset cage to default habitat (home, logs, food bowl, water tank, wheel) with extra custom props cleared.",
            result={"default_objects": default_ids},
            idempotent_replay=False,
        )
