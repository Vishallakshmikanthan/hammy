"""
HAMMY — Step 6: Shelf-Based Opt-In Asset & Layout API Routes (`services/api/routes/shelves.py`).
Exposes authoritative endpoints for:
  - GET  /api/v1/assets/manifest
  - GET  /api/v1/pets/{pet_id}/shelves/state
  - POST /api/v1/pets/{pet_id}/shelves/offer_food
  - POST /api/v1/pets/{pet_id}/shelves/refill_water
  - POST /api/v1/pets/{pet_id}/shelves/equip_costume
  - POST /api/v1/pets/{pet_id}/shelves/unequip_costume
  - POST /api/v1/pets/{pet_id}/shelves/place_prop
  - POST /api/v1/pets/{pet_id}/shelves/move_prop
  - POST /api/v1/pets/{pet_id}/shelves/remove_prop
  - POST /api/v1/pets/{pet_id}/shelves/consume_food
  - POST /api/v1/pets/{pet_id}/shelves/consume_water
  - POST /api/v1/pets/{pet_id}/shelves/reset_clean_cage
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from infrastructure.database.models import Habitat, HabitatObject, Pet, PetState, User
from services.api.auth import get_db, verify_pet_access
from services.api.rate_limit import rate_limit_dependency
from services.commands.handler import (
    CommandHandler,
    CommandValidationError,
    load_asset_manifest,
)

router = APIRouter(dependencies=[Depends(rate_limit_dependency)])
command_handler = CommandHandler()


class OfferFoodRequest(BaseModel):
    command_id: str = Field(..., min_length=4)
    item_id: str = Field(..., min_length=2)
    quantity: int = Field(default=1, ge=1, le=10)
    pose_xyz_m: Optional[List[float]] = None


class RefillWaterRequest(BaseModel):
    command_id: str = Field(..., min_length=4)
    amount_ml: float = Field(default=150.0, gt=0.0, le=300.0)


class RefillFoodRequest(BaseModel):
    command_id: str = Field(..., min_length=4)
    amount_grams: float = Field(default=25.0, gt=0.0, le=50.0)


class EquipCostumeRequest(BaseModel):
    command_id: str = Field(..., min_length=4)
    item_id: str = Field(..., min_length=2)


class UnequipCostumeRequest(BaseModel):
    command_id: str = Field(..., min_length=4)
    slot: Optional[str] = None
    item_id: Optional[str] = None


class PlacePropRequest(BaseModel):
    command_id: str = Field(..., min_length=4)
    item_id: str = Field(..., min_length=2)
    pose_xyz_m: List[float] = Field(..., min_length=3, max_length=3)
    rotation_y_rad: float = 0.0
    object_id: Optional[str] = None


class MovePropRequest(BaseModel):
    command_id: str = Field(..., min_length=4)
    object_id: str = Field(..., min_length=2)
    pose_xyz_m: List[float] = Field(..., min_length=3, max_length=3)
    rotation_y_rad: Optional[float] = None


class RemovePropRequest(BaseModel):
    command_id: str = Field(..., min_length=4)
    object_id: str = Field(..., min_length=2)


class ConsumeFoodRequest(BaseModel):
    command_id: str = Field(..., min_length=4)
    object_id: Optional[str] = None


class ConsumeWaterRequest(BaseModel):
    command_id: str = Field(..., min_length=4)


class ResetCleanCageRequest(BaseModel):
    command_id: str = Field(..., min_length=4)


@router.get("/assets/manifest")
def get_assets_manifest() -> Dict[str, Any]:
    """Returns the full 30-asset manifest (`assets/manifest.json`)."""
    return load_asset_manifest()


@router.get("/pets/{pet_id}/shelves/state")
def get_shelves_layout_state(
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns the complete server-authoritative habitat layout:
      - `equipped_costumes`: dict mapping `head_slot`, `neck_slot`, `back_slot` -> item metadata
      - `offered_foods`: active offered food items in the cage (with remaining quantity & spoilage timer)
      - `water_sources`: active water bottle/bowl items with `water_level` (0..1)
      - `placed_items`: opt-in placed props & decor items (only items explicitly placed by the user)
      - `cheek_pouch_fill`: 0..1 fullness value stored in `pet_state`
    """
    pet, _ = pet_and_user
    habitat = session.query(Habitat).filter_by(pet_id=pet.id).first()
    pet_state = session.get(PetState, pet.id)
    sim_time = pet_state.sim_time_sec if pet_state else 0.0

    equipped_costumes: Dict[str, Any] = {}
    offered_foods: List[Dict[str, Any]] = []
    water_sources: List[Dict[str, Any]] = []
    placed_items: List[Dict[str, Any]] = []
    primary_food_level: Optional[float] = None

    if habitat:
        objs = session.query(HabitatObject).filter_by(habitat_id=habitat.id).all()
        for o in objs:
            res = dict(o.resource_state or {})
            if o.object_type == "costume_equip":
                slot = res.get("slot", "head_slot")
                equipped_costumes[slot] = {
                    "object_id": o.id,
                    "item_id": res.get("asset_id", o.blender_name),
                    "name": res.get("name", o.blender_name),
                    "slot": slot,
                }
            elif o.object_type == "offered_food":
                spoils_at = float(res.get("spoils_at_sim_sec", sim_time + 600.0))
                is_spoiled = bool(res.get("spoiled", False) or (sim_time > spoils_at and sim_time > 0))
                offered_foods.append({
                    "object_id": o.id,
                    "item_id": res.get("asset_id", o.blender_name),
                    "name": res.get("name", o.blender_name),
                    "quantity": int(res.get("quantity", 1)),
                    "pose_xyz_m": o.pose_xyz_m,
                    "spoils_at_sim_sec": spoils_at,
                    "spoiled": is_spoiled,
                })
            elif o.object_type in ("water_bottle", "water_bowl"):
                water_sources.append({
                    "object_id": o.id,
                    "item_id": res.get("asset_id", "water_bottle" if o.object_type == "water_bottle" else "water_bowl"),
                    "name": res.get("name", "Water Bottle" if o.object_type == "water_bottle" else "Water Bowl"),
                    "pose_xyz_m": o.pose_xyz_m,
                    "water_level": float(res.get("water_level", 1.0)),
                    "capacity_ml": float(res.get("capacity_ml", 150.0)),
                })
            elif o.object_type == "food_bowl" and not res.get("asset_id"):
                # Core habitat food bowl tracks server-authoritative food level (0..1)
                if o.id == "prop_bowl_main" or primary_food_level is None:
                    primary_food_level = float(res.get("food_level", 1.0))
            elif o.object_type in ("placed_prop", "placed_decor") or res.get("asset_id"):
                # Opt-in placed items from Props / Decor shelves
                placed_items.append({
                    "object_id": o.id,
                    "item_id": res.get("asset_id", o.blender_name),
                    "name": res.get("name", o.blender_name),
                    "category": res.get("category", "prop"),
                    "pose_xyz_m": o.pose_xyz_m,
                    "rotation_y_rad": float(res.get("rotation_y_rad", 0.0)),
                    "collision_radius_m": float(o.interaction_radius_m),
                })

    primary_water_level = water_sources[0]["water_level"] if water_sources else 0.75
    food_level = primary_food_level if primary_food_level is not None else 1.0

    return {
        "pet_id": pet.id,
        "sim_time_sec": sim_time,
        "cheek_pouch_fill": float(pet_state.cheek_pouch_fill) if pet_state else 0.0,
        "food_level": food_level,
        "water_level": primary_water_level,
        "equipped_costumes": equipped_costumes,
        "offered_foods": offered_foods,
        "water_sources": water_sources,
        "placed_items": placed_items,
    }


def _exec(
    session: Session,
    pet_and_user: tuple[Pet, User],
    command_id: str,
    command_type: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    pet, user = pet_and_user
    try:
        res = command_handler.execute_command(
            session=session,
            user_id=user.id,
            pet_id=pet.id,
            command_id=command_id,
            command_type=command_type,
            parameters=params,
        )
        layout = get_shelves_layout_state(pet_and_user=pet_and_user, session=session)
        return {
            "command_id": res.command_id,
            "status": res.status,
            "message": res.message,
            "result": res.result,
            "idempotent_replay": res.idempotent_replay,
            "layout": layout,
        }
    except CommandValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/pets/{pet_id}/shelves/offer_food")
def offer_food_route(
    body: OfferFoodRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    return _exec(
        session,
        pet_and_user,
        body.command_id,
        "offer_food",
        {"item_id": body.item_id, "quantity": body.quantity, "pose_xyz_m": body.pose_xyz_m},
    )


@router.post("/pets/{pet_id}/shelves/refill_food")
def refill_food_route(
    body: RefillFoodRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    return _exec(
        session,
        pet_and_user,
        body.command_id,
        "refill_food",
        {"amount_grams": body.amount_grams},
    )


@router.post("/pets/{pet_id}/shelves/refill_water")
def refill_water_route(
    body: RefillWaterRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    return _exec(
        session,
        pet_and_user,
        body.command_id,
        "refill_water",
        {"amount_ml": body.amount_ml},
    )


@router.post("/pets/{pet_id}/shelves/equip_costume")
def equip_costume_route(
    body: EquipCostumeRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    return _exec(
        session,
        pet_and_user,
        body.command_id,
        "equip_costume",
        {"item_id": body.item_id},
    )


@router.post("/pets/{pet_id}/shelves/unequip_costume")
def unequip_costume_route(
    body: UnequipCostumeRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    return _exec(
        session,
        pet_and_user,
        body.command_id,
        "unequip_costume",
        {"slot": body.slot, "item_id": body.item_id},
    )


@router.post("/pets/{pet_id}/shelves/place_prop")
def place_prop_route(
    body: PlacePropRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    return _exec(
        session,
        pet_and_user,
        body.command_id,
        "place_prop",
        {
            "item_id": body.item_id,
            "pose_xyz_m": body.pose_xyz_m,
            "rotation_y_rad": body.rotation_y_rad,
            "object_id": body.object_id,
        },
    )


@router.post("/pets/{pet_id}/shelves/move_prop")
def move_prop_route(
    body: MovePropRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    return _exec(
        session,
        pet_and_user,
        body.command_id,
        "move_prop",
        {
            "object_id": body.object_id,
            "pose_xyz_m": body.pose_xyz_m,
            "rotation_y_rad": body.rotation_y_rad,
        },
    )


@router.post("/pets/{pet_id}/shelves/remove_prop")
def remove_prop_route(
    body: RemovePropRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    return _exec(
        session,
        pet_and_user,
        body.command_id,
        "remove_prop",
        {"object_id": body.object_id},
    )


@router.post("/pets/{pet_id}/shelves/consume_food")
def consume_food_route(
    body: ConsumeFoodRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    return _exec(
        session,
        pet_and_user,
        body.command_id,
        "consume_food",
        {"object_id": body.object_id},
    )


@router.post("/pets/{pet_id}/shelves/consume_water")
def consume_water_route(
    body: ConsumeWaterRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    return _exec(
        session,
        pet_and_user,
        body.command_id,
        "consume_water",
        {},
    )


@router.post("/pets/{pet_id}/shelves/reset_clean_cage")
def reset_clean_cage_route(
    body: ResetCleanCageRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    return _exec(
        session,
        pet_and_user,
        body.command_id,
        "reset_clean_cage",
        {},
    )
