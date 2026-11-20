"""
HAMMY — Simulation Control Routes (`services/api/routes/simulation.py`).
Supports pause, resume, real-time multiplier toggles (`1x`, `10x`, `60x`, `300x`),
and manual live-brain stepping.
"""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from infrastructure.database.models import Pet, PetState, User
from services.api.auth import get_db, verify_pet_access
from services.api.rate_limit import rate_limit_dependency
from services.api.websocket import ws_manager
from services.commands.handler import CommandHandler, CommandValidationError
from services.runtime.live_brain_engine import live_brain_engine

router = APIRouter(dependencies=[Depends(rate_limit_dependency)])
command_handler = CommandHandler()


class SimulationCommandRequest(BaseModel):
    command_id: str = Field(..., min_length=4, description="Unique client idempotency key")


class TimeScaleCommandRequest(BaseModel):
    command_id: str = Field(..., min_length=4, description="Unique client idempotency key")
    real_time_scale: float = Field(..., ge=0.5, le=600.0, description="Simulation speed multiplier (1x, 10x, 60x, 300x)")


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


@router.post("/pets/{pet_id}/simulation/time_scale")
async def set_simulation_time_scale(
    body: TimeScaleCommandRequest,
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Sets simulation clock multiplier (1x real-time, 10x, 60x, 300x). Idempotent by command_id."""
    pet, user = pet_and_user
    try:
        res = command_handler.execute_command(
            session=session,
            user_id=user.id,
            pet_id=pet.id,
            command_id=body.command_id,
            command_type="set_time_scale",
            parameters={"real_time_scale": body.real_time_scale},
        )
        state = session.get(PetState, pet.id)
        if state:
            await ws_manager.broadcast_to_pet(
                pet.id,
                {
                    "type": "snapshot",
                    "pet_id": pet.id,
                    "version": state.version,
                    "sim_time_sec": state.sim_time_sec,
                    "simulated_age_days": state.simulated_age_days,
                    "real_time_scale": state.real_time_scale,
                    "drives": state.drives,
                    "position_xyz": state.position_xyz,
                    "active_skill": state.active_skill,
                    "is_paused": state.is_paused,
                    "policy_version": live_brain_engine.policy_version,
                    "motor_policy_version": live_brain_engine.motor_policy_version,
                    "brain_telemetry": live_brain_engine.get_brain_telemetry(session, pet.id),
                },
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


@router.post("/pets/{pet_id}/simulation/tick")
async def trigger_live_brain_tick(
    pet_and_user: tuple[Pet, User] = Depends(verify_pet_access),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Forces one immediate live brain decision + physiology step and broadcasts over WebSocket."""
    pet, _ = pet_and_user
    out = live_brain_engine.step_pet_live(session, pet.id, dt_wall_sec=2.0, force_decision=True)
    if out is None:
        return {"status": "paused_or_missing", "pet_id": pet.id}
    await ws_manager.broadcast_to_pet(pet.id, out["snapshot"])
    if out.get("event") is not None:
        await ws_manager.broadcast_to_pet(pet.id, {"type": "event", "event": out["event"]})
    return {"status": "ok", "snapshot": out["snapshot"], "event": out.get("event")}
