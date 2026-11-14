"""
HAMMY — System & Health Route (`services/api/routes/system.py`).
"""

from __future__ import annotations

import datetime
from typing import Any, Dict
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.api.auth import get_db

router = APIRouter()


@router.get("/system/health")
def health_check(session: Session = Depends(get_db)) -> Dict[str, Any]:
    """Health check validating application runtime and database connectivity."""
    db_status = "connected"
    try:
        session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "database": db_status,
        "version": "1.0.0",
    }

