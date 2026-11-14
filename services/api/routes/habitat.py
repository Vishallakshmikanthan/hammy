"""
HAMMY — Habitat and Objects Routes (`services/api/routes/habitat.py`).
"""

from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from infrastructure.database.models import Habitat, HabitatObject, Pet, User
from services.api.auth import get_db, verify_pet_access
from services.api.rate_limit import rate_limit_dependency
from services.commands.handler import CommandHandler, CommandValidationError

router = APIRouter(dependencies=[Depends(rate_limit_dependency)])
command_handler = CommandHandler()


class MoveObjectRequest(BaseModel):
    command_id: str = Field(..., min_length=4, description="Unique client idempotency key")
    object_id: str = Field(..., min_length=1)
    new_pose_xyz_m: List[float] = Field(..., min_length=3, max_length=3)


@router.get("/pets/{pet_id}/habitat")
def get_habitat(
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns habitat geometry and floor boundaries."""
    pet, _ = pet_and_user
    habitat = session.query(Habitat).filter_by(pet_id=pet.id).first()
    if not habitat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Habitat not found for pet '{pet.id}'.",
        )

    return {
        "id": habitat.id,
        "pet_id": habitat.pet_id,
        "name": habitat.name,
        "environment_version": habitat.environment_version,
        "dimensions_xyz": habitat.dimensions_xyz,
        "floor_bounds": habitat.floor_bounds,
        "created_at": habitat.created_at.isoformat() if habitat.created_at else None,
    }


@router.get("/pets/{pet_id}/habitat/objects")
def get_habitat_objects(
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Returns all interactive props in the pet's habitat."""
    pet, _ = pet_and_user
    habitat = session.query(Habitat).filter_by(pet_id=pet.id).first()
    if not habitat:
        return []

    objects = session.query(HabitatObject).filter_by(habitat_id=habitat.id).all()
    return [
        {
            "id": obj.id,
            "habitat_id": obj.habitat_id,
            "object_type": obj.object_type,
            "blender_name": obj.blender_name,
            "pose_xyz_m": obj.pose_xyz_m,
            "interaction_radius_m": obj.interaction_radius_m,
            "affordances": obj.affordances,
            "resource_state": obj.resource_state,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
        }
        for obj in objects
    ]


@router.post("/pets/{pet_id}/habitat/objects")
def move_habitat_object(
    body: MoveObjectRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Rearranges an object within habitat floor boundaries."""
    pet, user = pet_and_user
    try:
        res = command_handler.execute_command(
            session=session,
            user_id=user.id,
            pet_id=pet.id,
            command_id=body.command_id,
            command_type="move_object",
            parameters={"object_id": body.object_id, "new_pose_xyz_m": body.new_pose_xyz_m},
        )
        return {
            "command_id": res.command_id,
            "status": res.status,
            "message": res.message,
            "result": res.result,
            "idempotent_replay": res.idempotent_replay,
        }
    except CommandValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

