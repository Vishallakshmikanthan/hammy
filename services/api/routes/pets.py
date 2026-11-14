"""
HAMMY — Pets, State, Events, and Memories Routes (`services/api/routes/pets.py`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from infrastructure.database.models import Memory, Pet, PetState, User, WorldEvent
from services.api.auth import get_db, verify_pet_access
from services.api.rate_limit import rate_limit_dependency

router = APIRouter(dependencies=[Depends(rate_limit_dependency)])


@router.get("/pets/{pet_id}")
def get_pet_details(
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
) -> Dict[str, Any]:
    """Returns basic pet metadata."""
    pet, _ = pet_and_user
    return {
        "id": pet.id,
        "user_id": pet.user_id,
        "name": pet.name,
        "species": pet.species,
        "morphology_version": pet.morphology_version,
        "birth_date": pet.birth_date.isoformat() if pet.birth_date else None,
        "created_at": pet.created_at.isoformat() if pet.created_at else None,
    }


@router.get("/pets/{pet_id}/state")
def get_pet_state(
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns current live simulation state snapshot."""
    pet, _ = pet_and_user
    state = session.get(PetState, pet.id)
    if not state:
        return {"pet_id": pet.id, "state": None}

    return {
        "pet_id": state.pet_id,
        "version": state.version,
        "schema_version": state.schema_version,
        "environment_version": state.environment_version,
        "sim_time_sec": state.sim_time_sec,
        "simulated_age_days": state.simulated_age_days,
        "real_time_scale": state.real_time_scale,
        "last_simulated_at": state.last_simulated_at.isoformat() if state.last_simulated_at else None,
        "is_paused": state.is_paused,
        "drives": state.drives,
        "position_xyz": state.position_xyz,
        "yaw_rad": state.yaw_rad,
        "velocity_xy": state.velocity_xy,
        "angular_velocity_z": state.angular_velocity_z,
        "inside_hideout": state.inside_hideout,
        "inside_tunnel": state.inside_tunnel,
        "on_wheel": state.on_wheel,
        "cheek_pouch_fill": state.cheek_pouch_fill,
        "active_skill": state.active_skill,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }


@router.get("/pets/{pet_id}/events")
def get_pet_events(
    limit: int = Query(50, ge=1, le=500),
    since_tick: Optional[int] = Query(None, ge=0),
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Returns historical event stream for the pet."""
    pet, _ = pet_and_user
    query = session.query(WorldEvent).filter(WorldEvent.pet_id == pet.id)
    if since_tick is not None:
        query = query.filter(WorldEvent.world_tick > since_tick)

    events = query.order_by(WorldEvent.world_tick.desc()).limit(limit).all()
    return [
        {
            "event_id": e.event_id,
            "pet_id": e.pet_id,
            "world_tick": e.world_tick,
            "sim_time_sec": e.sim_time_sec,
            "event_type": e.event_type,
            "skill_name": e.skill_name,
            "origin": e.origin,
            "behaviour_type": e.behaviour_type,
            "seed": e.seed,
            "payload": e.payload,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


@router.get("/pets/{pet_id}/memories")
def get_pet_memories(
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Returns active cognitive memories (appraisals and spatial familiarity)."""
    pet, _ = pet_and_user
    memories = session.query(Memory).filter(Memory.pet_id == pet.id).all()
    return [
        {
            "id": m.id,
            "pet_id": m.pet_id,
            "memory_type": m.memory_type,
            "target_id": m.target_id,
            "estimated_value": m.estimated_value,
            "confidence": m.confidence,
            "time_since_last_visit_sec": m.time_since_last_visit_sec,
            "last_known_pos": m.last_known_pos,
            "spatial_familiarity": m.spatial_familiarity,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
        for m in memories
    ]

