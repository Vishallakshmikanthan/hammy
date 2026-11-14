"""
HAMMY — Notification Preferences & Chat Binding Routes (`services/api/routes/notifications.py`).
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from infrastructure.database.models import NotificationPreference, User
from services.api.auth import get_current_user, get_db
from services.api.rate_limit import rate_limit_dependency
from services.notification_worker.binding import TelegramBindingManager

router = APIRouter(dependencies=[Depends(rate_limit_dependency)])


class ConfirmBindingRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=32, description="Verification code from Telegram /start")


class NotificationPreferencesUpdate(BaseModel):
    daily_digest_enabled: Optional[bool] = None
    daily_digest_time_utc: Optional[str] = None
    urgent_alerts_enabled: Optional[bool] = None
    quiet_hours_start_utc: Optional[str] = None
    quiet_hours_end_utc: Optional[str] = None


@router.post("/notifications/telegram/confirm")
def confirm_telegram_binding(
    body: ConfirmBindingRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Confirms one-time pairing code from Telegram to link user account."""
    success, message, chat_id = TelegramBindingManager.confirm_binding(
        session=session,
        user_id=current_user.id,
        code=body.code,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return {
        "status": "success",
        "message": message,
        "chat_id": chat_id,
    }


@router.get("/notifications/preferences")
def get_preferences(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns current user's notification preferences."""
    pref = session.get(NotificationPreference, current_user.id)
    if not pref:
        return {
            "user_id": current_user.id,
            "telegram_chat_id": None,
            "daily_digest_enabled": True,
            "daily_digest_time_utc": "08:00",
            "urgent_alerts_enabled": True,
            "quiet_hours_start_utc": "22:00",
            "quiet_hours_end_utc": "07:00",
        }

    return {
        "user_id": pref.user_id,
        "telegram_chat_id": pref.telegram_chat_id,
        "daily_digest_enabled": pref.daily_digest_enabled,
        "daily_digest_time_utc": pref.daily_digest_time_utc,
        "urgent_alerts_enabled": pref.urgent_alerts_enabled,
        "quiet_hours_start_utc": pref.quiet_hours_start_utc,
        "quiet_hours_end_utc": pref.quiet_hours_end_utc,
    }


@router.put("/notifications/preferences")
def update_preferences(
    body: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Updates notification preferences and quiet hours."""
    pref = session.get(NotificationPreference, current_user.id)
    if not pref:
        pref = NotificationPreference(user_id=current_user.id)
        session.add(pref)

    if body.daily_digest_enabled is not None:
        pref.daily_digest_enabled = body.daily_digest_enabled
    if body.daily_digest_time_utc is not None:
        pref.daily_digest_time_utc = body.daily_digest_time_utc
    if body.urgent_alerts_enabled is not None:
        pref.urgent_alerts_enabled = body.urgent_alerts_enabled
    if body.quiet_hours_start_utc is not None:
        pref.quiet_hours_start_utc = body.quiet_hours_start_utc
    if body.quiet_hours_end_utc is not None:
        pref.quiet_hours_end_utc = body.quiet_hours_end_utc

    session.commit()
    return {"status": "updated", "preferences": get_preferences(current_user, session)}

