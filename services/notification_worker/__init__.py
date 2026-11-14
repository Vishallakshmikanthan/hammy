"""
HAMMY — Telegram Integration and Notification Worker Package (`services/notification_worker`).
Implements:
  - Reliable outbox delivery with exponential backoff and dead-letter handling.
  - One-time verification code binding flow.
  - Shared command handler bot routing (/status, /feed, /water, /pause, /resume, /report).
  - Recorded-events-only daily digest with plain-language origin badges.
  - Quiet hours and duplicate suppression.
"""

from services.notification_worker.binding import TelegramBindingManager
from services.notification_worker.client import TelegramClient
from services.notification_worker.digest import DailyDigestBuilder
from services.notification_worker.outbox import OutboxProcessor

__all__ = [
    "TelegramBindingManager",
    "TelegramClient",
    "DailyDigestBuilder",
    "OutboxProcessor",
]

