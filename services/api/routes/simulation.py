"""
HAMMY — Simulation Control Routes (`services/api/routes/simulation.py`).
"""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from infrastructure.database.models import Pet, User
from services.api.auth import get_db, verify_pet_access
from services.api.rate_limit import rate_limit_dependency
from services.commands.handler import CommandHandler, CommandValidationError

router = APIRouter(dependencies=[Depends(rate_limit_dependency)])
command_handler = CommandHandler()


class SimulationCommandRequest(BaseModel):
    command_id: str = Field(..., min_length=4, description="Unique client idempotency key")


@router.post("/pets/{pet_id}/simulation/pause")
def pause_simulation(
    body: SimulationCommandRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Pauses temporal progression for the pet. Idempotent by command_id."""
    pet, user = pet_and_user
    try:
        res = command_handler.execute_command(
            session=session,
            user_id=user.id,
            pet_id=pet.id,
            command_id=body.command_id,
            command_type="pause",
            parameters={},
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


@router.post("/pets/{pet_id}/simulation/resume")
def resume_simulation(
    body: SimulationCommandRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Resumes temporal progression for the pet. Idempotent by command_id."""
    pet, user = pet_and_user
    try:
        res = command_handler.execute_command(
            session=session,
            user_id=user.id,
            pet_id=pet.id,
            command_id=body.command_id,
            command_type="resume",
            parameters={},
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

