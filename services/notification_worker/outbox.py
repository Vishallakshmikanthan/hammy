"""
HAMMY — Notification Outbox Processor (`services/notification_worker/outbox.py`).
Implements Criterion 1 & 5:
  - Outbox pattern with exponential backoff, dead-letter state, and delivery status.
  - Quiet hours postponement, category preferences, and duplicate suppression.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from infrastructure.database.models import NotificationOutbox, NotificationPreference
from services.notification_worker.client import TelegramAPIError, TelegramClient


def _ensure_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def is_in_quiet_hours(
    t: datetime.time,
    start_str: str = "22:00",
    end_str: str = "07:00",
) -> bool:
    """Checks if the given time falls within configured quiet hours."""
    try:
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        start = datetime.time(sh, sm)
        end = datetime.time(eh, em)
    except Exception:
        start = datetime.time(22, 0)
        end = datetime.time(7, 0)

    if start > end:
        # Crosses midnight (e.g. 22:00 to 07:00)
        return t >= start or t < end
    else:
        return start <= t < end


class OutboxProcessor:
    """
    Pulls pending notifications from `notification_outbox`, validates quiet hours
    and user preferences, attempts transmission, and handles backoff / dead-letter.
    """

    def __init__(
        self,
        telegram_client: Any,
        max_retries: int = 3,
        base_delay_sec: float = 30.0,
        suppression_window_sec: float = 300.0,
    ):
        self.client = telegram_client
        self.max_retries = max_retries
        self.base_delay_sec = base_delay_sec
        self.suppression_window_sec = suppression_window_sec

    def enqueue(
        self,
        session: Session,
        user_id: str,
        pet_id: str,
        category: str,
        text: str,
        outbox_id: Optional[str] = None,
        scheduled_for: Optional[datetime.datetime] = None,
        now: Optional[datetime.datetime] = None,
    ) -> NotificationOutbox:
        """Helper to enqueue a message into the outbox."""
        import uuid

        curr_time = _ensure_utc(now or datetime.datetime.now(datetime.timezone.utc))
        sched_time = _ensure_utc(scheduled_for or curr_time)

        item = NotificationOutbox(
            id=outbox_id or f"ntf_{uuid.uuid4().hex[:14]}",
            user_id=user_id,
            pet_id=pet_id,
            channel="telegram",
            category=category,
            message_payload={"text": text},
            status="pending",
            attempts=0,
            scheduled_for=sched_time,
            created_at=curr_time,
        )
        session.add(item)
        session.commit()
        return item

    def process_pending(
        self,
        session: Session,
        now: Optional[datetime.datetime] = None,
        limit: int = 50,
    ) -> Dict[str, int]:
        """
        Processes pending outbox items ready for transmission.
        Returns execution counts.
        """
        curr_time = _ensure_utc(now or datetime.datetime.now(datetime.timezone.utc))
        items = (
            session.query(NotificationOutbox)
            .filter(
                NotificationOutbox.status == "pending",
                NotificationOutbox.scheduled_for <= curr_time,
            )
            .order_by(NotificationOutbox.scheduled_for.asc())
            .limit(limit)
            .all()
        )

        counts = {
            "delivered": 0,
            "failed": 0,
            "dead_letter": 0,
            "ignored": 0,
            "rescheduled": 0,
            "suppressed": 0,
        }

        for item in items:
            # 1. Fetch user preferences
            pref = session.get(NotificationPreference, item.user_id)
            if not pref or not pref.telegram_chat_id:
                item.status = "failed"
                item.last_error = "User has no linked Telegram chat ID."
                counts["failed"] += 1
                continue

            # 2. Category Preferences Check
            if item.category == "digest" and not pref.daily_digest_enabled:
                item.status = "ignored"
                item.last_error = "Daily digest disabled in user preferences."
                counts["ignored"] += 1
                continue

            if item.category == "urgent_alert" and not pref.urgent_alerts_enabled:
                item.status = "ignored"
                item.last_error = "Urgent alerts disabled in user preferences."
                counts["ignored"] += 1
                continue

            # 3. Quiet Hours Check
            if item.category != "urgent_alert":
                start_h = pref.quiet_hours_start_utc or "22:00"
                end_h = pref.quiet_hours_end_utc or "07:00"
                if is_in_quiet_hours(curr_time.time(), start_h, end_h):
                    # Postpone delivery past quiet hours
                    item.scheduled_for = curr_time + datetime.timedelta(hours=1)
                    counts["rescheduled"] += 1
                    continue

            # 4. Duplicate Suppression Check
            text_to_send = item.message_payload.get("text", "")
            suppression_threshold = curr_time - datetime.timedelta(seconds=self.suppression_window_sec)
            recent_same = (
                session.query(NotificationOutbox)
                .filter(
                    NotificationOutbox.user_id == item.user_id,
                    NotificationOutbox.status == "delivered",
                    NotificationOutbox.delivered_at >= suppression_threshold,
                    NotificationOutbox.id != item.id,
                )
                .all()
            )
            is_dup = any(
                r.message_payload.get("text") == text_to_send
                for r in recent_same
            )
            if is_dup:
                item.status = "duplicate_suppressed"
                item.delivered_at = curr_time
                counts["suppressed"] += 1
                continue

            # 5. Delivery Attempt
            try:
                self.client.send_message(
                    chat_id=pref.telegram_chat_id,
                    text=text_to_send,
                )
                item.status = "delivered"
                item.delivered_at = curr_time
                item.last_error = None
                counts["delivered"] += 1
            except Exception as e:
                item.attempts += 1
                item.last_error = str(e)

                if item.attempts >= self.max_retries:
                    item.status = "dead_letter"
                    counts["dead_letter"] += 1
                else:
                    backoff = self.base_delay_sec * (2 ** (item.attempts - 1))
                    item.scheduled_for = curr_time + datetime.timedelta(seconds=backoff)
                    item.status = "pending"
                    counts["failed"] += 1

        session.commit()
        return counts

