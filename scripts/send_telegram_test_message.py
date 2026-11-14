#!/usr/bin/env python3
"""
HAMMY — Manual Telegram Bot Test Script (`scripts/send_telegram_test_message.py`).
Fulfills P2.4 Acceptance: "a manual test script sends one verified message to my bot."
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.notification_worker.client import MockTelegramClient, TelegramClient


def main():
    print("=" * 70)
    print("HAMMY — P2.4 Telegram Bot Integration Test Script")
    print("=" * 70)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    test_message = (
        "🐹 <b>HAMMY Notification Test</b>\n"
        "Verification check successful! Your virtual Syrian hamster simulation is active."
    )

    if token and chat_id:
        print(f"[*] Detected TELEGRAM_BOT_TOKEN ({token[:8]}...) and TELEGRAM_CHAT_ID ({chat_id}).")
        print("[*] Dispatching real HTTP request to Telegram Bot API...")
        client = TelegramClient(token=token)
        try:
            resp = client.send_message(chat_id=chat_id, text=test_message)
            print("[SUCCESS] Verified message sent to live Telegram chat!")
            print(f"[*] Response: {resp}")
        except Exception as e:
            print(f"[ERROR] Failed to send to live Telegram API: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("[NOTE] Live credentials not set in environment:")
        if not token:
            print("       - TELEGRAM_BOT_TOKEN is not set.")
        if not chat_id:
            print("       - TELEGRAM_CHAT_ID is not set.")
        print("\n[*] Executing verified Mock transmission test...")
        mock_client = MockTelegramClient()
        resp = mock_client.send_message(chat_id=chat_id or "123456789", text=test_message)
        assert len(mock_client.sent_messages) == 1
        assert mock_client.sent_messages[0]["text"] == test_message
        print(f"[SUCCESS] Mock verified send completed: message_id={resp['result']['message_id']}")
        print("\nTo test with your live Telegram bot:")
        print("  $env:TELEGRAM_BOT_TOKEN=\"<your_bot_token>\"")
        print("  $env:TELEGRAM_CHAT_ID=\"<your_telegram_chat_id>\"")
        print("  python scripts/send_telegram_test_message.py")

    print("=" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()

