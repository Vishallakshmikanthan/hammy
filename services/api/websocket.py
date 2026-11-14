"""
HAMMY — WebSocket Connection Manager (`services/api/websocket.py`).
Maintains active real-time connections per pet and broadcasts state snapshots and events.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Set
from fastapi import WebSocket

logger = logging.getLogger("hammy.websocket")


class ConnectionManager:
    """Manages active WebSocket connections grouped by pet_id."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, pet_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if pet_id not in self.active_connections:
            self.active_connections[pet_id] = set()
        self.active_connections[pet_id].add(websocket)
        logger.debug("WebSocket connected for pet %s. Total: %d", pet_id, len(self.active_connections[pet_id]))

    def disconnect(self, pet_id: str, websocket: WebSocket) -> None:
        if pet_id in self.active_connections:
            self.active_connections[pet_id].discard(websocket)
            if not self.active_connections[pet_id]:
                del self.active_connections[pet_id]
        logger.debug("WebSocket disconnected for pet %s.", pet_id)

    async def broadcast_to_pet(self, pet_id: str, message: Dict[str, Any]) -> None:
        if pet_id in self.active_connections:
            dead_sockets = set()
            for ws in list(self.active_connections[pet_id]):
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.debug("Error sending to websocket: %s", e)
                    dead_sockets.add(ws)

            for dead in dead_sockets:
                self.disconnect(pet_id, dead)


ws_manager = ConnectionManager()

