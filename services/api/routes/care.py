"""
HAMMY — Care and Enrichment Routes (`services/api/routes/care.py`).
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from infrastructure.database.models import Pet, User
from services.api.auth import get_db, verify_pet_access
from services.api.rate_limit import rate_limit_dependency
from services.commands.handler import CommandHandler, CommandValidationError

router = APIRouter(dependencies=[Depends(rate_limit_dependency)])
command_handler = CommandHandler()


class FeedRequest(BaseModel):
    command_id: str = Field(..., min_length=4, description="Unique client idempotency key")
    amount_grams: float = Field(default=5.0, ge=0.1, le=25.0)


class WaterRequest(BaseModel):
    command_id: str = Field(..., min_length=4, description="Unique client idempotency key")
    amount_ml: float = Field(default=20.0, ge=1.0, le=150.0)


class EnrichmentRequest(BaseModel):
    command_id: str = Field(..., min_length=4, description="Unique client idempotency key")
    enrichment_type: str = Field(..., min_length=2)
    parameters: Dict[str, Any] = Field(default_factory=dict)


@router.post("/pets/{pet_id}/care/feed")
def feed_pet(
    body: FeedRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Adds food to the habitat bowl. Idempotent by command_id."""
    pet, user = pet_and_user
    try:
        res = command_handler.execute_command(
            session=session,
            user_id=user.id,
            pet_id=pet.id,
            command_id=body.command_id,
            command_type="feed",
            parameters={"amount_grams": body.amount_grams},
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


@router.post("/pets/{pet_id}/care/water")
def water_pet(
    body: WaterRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Refills the habitat water bottle. Idempotent by command_id."""
    pet, user = pet_and_user
    try:
        res = command_handler.execute_command(
            session=session,
            user_id=user.id,
            pet_id=pet.id,
            command_id=body.command_id,
            command_type="water",
            parameters={"amount_ml": body.amount_ml},
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


@router.post("/pets/{pet_id}/enrichment")
def add_enrichment(
    body: EnrichmentRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Adds habitat enrichment (chew toy, tube, foraging scatter). Idempotent by command_id."""
    pet, user = pet_and_user
    try:
        res = command_handler.execute_command(
            session=session,
            user_id=user.id,
            pet_id=pet.id,
            command_id=body.command_id,
            command_type="add_enrichment",
            parameters={"enrichment_type": body.enrichment_type, **body.parameters},
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

