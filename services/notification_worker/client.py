"""
HAMMY — Telegram HTTP API Client (`services/notification_worker/client.py`).
Token is loaded strictly from environment variable `TELEGRAM_BOT_TOKEN` (Rule 8).
Provides concrete TelegramClient (using httpx) and MockTelegramClient for deterministic testing.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("hammy.telegram.client")


class TelegramAPIError(Exception):
    """Raised when Telegram API rejects a request or network transport fails."""


class TelegramClient:
    """HTTP Client communicating with the Telegram Bot API."""

    def __init__(self, token: Optional[str] = None, timeout_sec: float = 10.0):
        # Rule 8: Token from environment variable only
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.timeout_sec = timeout_sec
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
    ) -> Dict[str, Any]:
        """Sends a text message to a specific Telegram chat_id."""
        if not self.is_configured:
            raise TelegramAPIError("TELEGRAM_BOT_TOKEN is not configured in environment.")

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": str(chat_id),
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }

        try:
            with httpx.Client(timeout=self.timeout_sec) as client:
                resp = client.post(url, json=payload)
                if resp.status_code != 200:
                    raise TelegramAPIError(
                        f"Telegram API HTTP {resp.status_code}: {resp.text}"
                    )
                data = resp.json()
                if not data.get("ok"):
                    raise TelegramAPIError(f"Telegram error: {data.get('description')}")
                return data
        except httpx.RequestError as e:
            raise TelegramAPIError(f"Transport error connecting to Telegram API: {str(e)}") from e


class MockTelegramClient:
    """Mock client recording messages in-memory with configurable failure injection."""

    def __init__(self, fail_first_n_attempts: int = 0, permanent_fail: bool = False):
        self.sent_messages: List[Dict[str, Any]] = []
        self.fail_countdown = fail_first_n_attempts
        self.permanent_fail = permanent_fail

    @property
    def is_configured(self) -> bool:
        return True

    def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
    ) -> Dict[str, Any]:
        if self.permanent_fail:
            raise TelegramAPIError("Simulated permanent Telegram API failure.")

        if self.fail_countdown > 0:
            self.fail_countdown -= 1
            raise TelegramAPIError(f"Simulated transient Telegram outage ({self.fail_countdown} remaining).")

        record = {
            "chat_id": str(chat_id),
            "text": text,
            "parse_mode": parse_mode,
            "message_id": len(self.sent_messages) + 1,
        }
        self.sent_messages.append(record)
        return {"ok": True, "result": record}

