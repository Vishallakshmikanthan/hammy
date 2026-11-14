"""
HAMMY — Telegram Chat Binding & Verification Manager (`services/notification_worker/binding.py`).
Implements Criterion 2:
  /start returns a one-time code the parent confirms on the website; unbound chats are rejected.
"""

from __future__ import annotations

import datetime
import random
import string
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from infrastructure.database.models import NotificationPreference, TelegramBindingCode, User


def _ensure_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


class TelegramBindingManager:
    """Manages chat pairing codes and links verified Telegram chat IDs to Users."""

    @staticmethod
    def generate_binding_code(
        session: Session,
        chat_id: str,
        ttl_minutes: int = 15,
        now: Optional[datetime.datetime] = None,
    ) -> str:
        """
        Generates a 6-character verification code for an unbound Telegram chat.
        Deletes any prior pending codes for this chat.
        """
        curr_time = _ensure_utc(now or datetime.datetime.now(datetime.timezone.utc))
        expires_at = curr_time + datetime.timedelta(minutes=ttl_minutes)

        # Remove prior codes for this chat
        session.query(TelegramBindingCode).filter_by(chat_id=str(chat_id)).delete()

        # Generate unique code like HAMMY-7492
        digits = "".join(random.choices(string.digits, k=4))
        letters = "".join(random.choices(string.ascii_uppercase, k=2))
        code = f"HAMMY-{letters}{digits}"

        record = TelegramBindingCode(
            code=code,
            chat_id=str(chat_id),
            expires_at=expires_at,
            created_at=curr_time,
        )
        session.add(record)
        session.commit()
        return code

    @staticmethod
    def confirm_binding(
        session: Session,
        user_id: str,
        code: str,
        now: Optional[datetime.datetime] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Confirms a pairing code entered by a user on the website.
        Returns (success, message, chat_id).
        """
        curr_time = _ensure_utc(now or datetime.datetime.now(datetime.timezone.utc))
        norm_code = code.strip().upper()

        record = session.get(TelegramBindingCode, norm_code)
        if not record:
            return False, "Invalid verification code. Please check the code or send /start in Telegram for a new one.", None

        if _ensure_utc(record.expires_at) < curr_time:
            session.delete(record)
            session.commit()
            return False, "Verification code has expired. Please send /start in Telegram for a fresh code.", None

        chat_id = record.chat_id

        # Update or create NotificationPreference
        pref = session.get(NotificationPreference, user_id)
        if not pref:
            pref = NotificationPreference(
                user_id=user_id,
                telegram_chat_id=chat_id,
                daily_digest_enabled=True,
                urgent_alerts_enabled=True,
            )
            session.add(pref)
        else:
            pref.telegram_chat_id = chat_id
            pref.updated_at = curr_time

        session.delete(record)
        session.commit()
        return True, "Telegram account successfully linked to Hammy!", chat_id

    @staticmethod
    def get_bound_user_and_pet(session: Session, chat_id: str) -> Optional[Tuple[User, Any]]:
        """
        Resolves a Telegram chat_id to the owner User and their primary Pet.
        Returns None if the chat is not bound.
        """
        pref = session.query(NotificationPreference).filter_by(telegram_chat_id=str(chat_id)).first()
        if not pref:
            return None

        user = session.get(User, pref.user_id)
        if not user or not user.pets:
            return None

        primary_pet = user.pets[0]
        return user, primary_pet

