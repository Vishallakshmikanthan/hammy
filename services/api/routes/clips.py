"""
HAMMY P5.1 — Trajectory Clips Routes (`services/api/routes/clips.py`).
Serves stored episode clips from object storage and generates deterministic
continuation clips when reconnecting after being offline.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from infrastructure.database.models import Pet, PetState, User
from services.api.auth import get_db, verify_pet_access
from services.api.rate_limit import rate_limit_dependency
from services.simulation_worker.clip_generator import generate_episode_clip
from services.simulation_worker.storage import LocalObjectStorage

router = APIRouter(dependencies=[Depends(rate_limit_dependency)])
_storage = LocalObjectStorage()


@router.get("/pets/{pet_id}/clips")
def list_pet_clips(
    since_sim_time: Optional[float] = Query(default=None, ge=0.0),
    ensure_continuation: bool = Query(default=True),
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    pet, _ = pet_and_user
    clips = _storage.list_clips(pet.id)
    if since_sim_time is not None:
        clips = [c for c in clips if c["end_sim_time_sec"] > since_sim_time]

    if ensure_continuation and not clips:
        state = db.query(PetState).filter(PetState.pet_id == pet.id).first()
        start_t = float(state.sim_time_sec) if state else float(since_sim_time or 0.0)
        skill = state.active_skill if state and state.active_skill else "explore_area"
        seed = int(start_t * 10) % 100000 + 42
        clip = generate_episode_clip(
            pet_id=pet.id,
            skill_id=skill,
            seed=seed,
            start_sim_time_sec=start_t,
            duration_sec=4.0,
        )
        _storage.upload_clip(clip)
        clips = [c for c in _storage.list_clips(pet.id) if c["clip_id"] == clip.clip_id]

    return {"pet_id": pet.id, "clips": clips}


@router.get("/pets/{pet_id}/clips/{clip_id}")
def get_pet_clip(
    clip_id: str,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
) -> Dict[str, Any]:
    pet, _ = pet_and_user
    clip = _storage.get_clip(pet.id, clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip '{clip_id}' not found for pet '{pet.id}'")
    return clip.model_dump()

