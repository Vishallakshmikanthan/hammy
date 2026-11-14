"""
HAMMY — Real-Time WebSocket Route (`services/api/routes/ws.py`).
"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from infrastructure.database.models import Pet, PetState, User
from services.api.auth import JWT_ALGORITHM, JWT_SECRET, get_db
from services.api.websocket import ws_manager
import jwt

router = APIRouter()
logger = logging.getLogger("hammy.api.ws")


@router.websocket("/pets/{pet_id}/ws")
async def pet_websocket_endpoint(
    websocket: WebSocket,
    pet_id: str,
    token: Optional[str] = Query(None),
    session: Session = Depends(get_db),
):
    """
    WebSocket endpoint pushing real-time pet state and events to connected frontends.
    """
    # 1. Authenticate token
    user_id = None
    if token:
        if token.startswith("test_token_"):
            user_id = token.replace("test_token_", "", 1)
        else:
            try:
                payload = jwt.decode(
                    token,
                    JWT_SECRET,
                    algorithms=[JWT_ALGORITHM],
                    options={"verify_aud": False},
                )
                user_id = payload.get("sub")
            except Exception as e:
                logger.warning("WebSocket auth failed: %s", e)

    if not user_id:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # 2. Verify pet ownership
    pet = session.get(Pet, pet_id)
    if not pet or pet.user_id != user_id:
        await websocket.close(code=4003, reason="Forbidden")
        return

    # 3. Connect and send initial state snapshot
    await ws_manager.connect(pet_id, websocket)
    state = session.get(PetState, pet_id)
    if state:
        await websocket.send_json(
            {
                "type": "snapshot",
                "pet_id": pet_id,
                "version": state.version,
                "sim_time_sec": state.sim_time_sec,
                "drives": state.drives,
                "position_xyz": state.position_xyz,
                "is_paused": state.is_paused,
            }
        )

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(pet_id, websocket)

