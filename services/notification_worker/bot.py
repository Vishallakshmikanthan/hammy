"""
HAMMY — Telegram Bot Command Router (`services/notification_worker/bot.py`).
Implements Criterion 3:
  Commands: /status, /feed, /water, /pause, /resume, /report,
  calling the shared command handlers (never writing the DB directly).
"""

from __future__ import annotations

import datetime
import time
import uuid
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from infrastructure.database.models import PetState
from services.commands.handler import CommandHandler, CommandValidationError
from services.notification_worker.binding import TelegramBindingManager
from services.notification_worker.digest import DailyDigestBuilder


class TelegramBot:
    """Dispatches Telegram commands to shared business logic."""

    def __init__(self, command_handler: Optional[CommandHandler] = None):
        self.command_handler = command_handler or CommandHandler()

    def process_message(
        self,
        session: Session,
        chat_id: str,
        text: str,
        now: Optional[datetime.datetime] = None,
    ) -> str:
        """Processes an incoming message text from chat_id and returns the reply string."""
        curr_time = now or datetime.datetime.now(datetime.timezone.utc)
        clean_text = text.strip()
        parts = clean_text.split()
        if not parts:
            return "Please provide a valid command (e.g. /status, /feed, /water, /pause, /resume, /report)."

        cmd = parts[0].lower()

        # 1. /start command — always accessible to trigger binding flow
        if cmd == "/start":
            bound = TelegramBindingManager.get_bound_user_and_pet(session, chat_id)
            if bound:
                _, pet = bound
                return f"👋 Welcome back! You are linked to <b>{pet.name}</b>.\nUse /status, /feed, /water, /pause, /resume, or /report."

            code = TelegramBindingManager.generate_binding_code(session, chat_id, now=curr_time)
            return (
                "👋 <b>Welcome to HAMMY!</b>\n"
                "Your Telegram account is not yet connected to your virtual pet.\n\n"
                "Your 1-time verification code is:\n"
                f"<b><code>{code}</code></b>\n\n"
                "Please enter this code on the Hammy website under <i>Settings > Notifications</i> to confirm connection.\n"
                "<i>Code expires in 15 minutes.</i>"
            )

        # 2. Check chat binding (Criterion 2: unbound chats are rejected)
        bound = TelegramBindingManager.get_bound_user_and_pet(session, chat_id)
        if not bound:
            return "⚠️ <b>Unbound Account</b>: You are not yet connected to a virtual pet. Please send /start to receive a pairing code."

        user, pet = bound

        # 3. Handle commands via shared command handler
        try:
            if cmd == "/status":
                return self._handle_status(session, pet)
            elif cmd == "/feed":
                amount = float(parts[1]) if len(parts) > 1 else 5.0
                cmd_id = f"cmd_tg_feed_{chat_id}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:4]}"
                res = self.command_handler.execute_command(
                    session=session,
                    user_id=user.id,
                    pet_id=pet.id,
                    command_id=cmd_id,
                    command_type="feed",
                    parameters={"amount_grams": amount},
                    now=curr_time,
                )
                return f"✅ {res.message}"
            elif cmd == "/water":
                amount = float(parts[1]) if len(parts) > 1 else 20.0
                cmd_id = f"cmd_tg_water_{chat_id}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:4]}"
                res = self.command_handler.execute_command(
                    session=session,
                    user_id=user.id,
                    pet_id=pet.id,
                    command_id=cmd_id,
                    command_type="water",
                    parameters={"amount_ml": amount},
                    now=curr_time,
                )
                return f"💧 {res.message}"
            elif cmd == "/pause":
                cmd_id = f"cmd_tg_pause_{chat_id}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:4]}"
                res = self.command_handler.execute_command(
                    session=session,
                    user_id=user.id,
                    pet_id=pet.id,
                    command_id=cmd_id,
                    command_type="pause",
                    parameters={},
                    now=curr_time,
                )
                return "⏸️ Simulation paused."
            elif cmd == "/resume":
                cmd_id = f"cmd_tg_resume_{chat_id}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:4]}"
                res = self.command_handler.execute_command(
                    session=session,
                    user_id=user.id,
                    pet_id=pet.id,
                    command_id=cmd_id,
                    command_type="resume",
                    parameters={},
                    now=curr_time,
                )
                return "▶️ Simulation resumed."
            elif cmd == "/report":
                digest = DailyDigestBuilder.build_digest(session, pet.id, now=curr_time)
                return digest["html_message"]
            else:
                return f"❓ Unknown command '{cmd}'. Available: /status, /feed, /water, /pause, /resume, /report."
        except CommandValidationError as e:
            return f"❌ Command error: {str(e)}"

    def _handle_status(self, session: Session, pet: Any) -> str:
        state = session.get(PetState, pet.id)
        if not state:
            return f"Pet {pet.name} has no simulation state."

        drives = state.drives or {}
        return (
            f"🐹 <b>{pet.name} — Syrian Hamster Status</b>\n"
            f"• Simulated Age: <b>{state.simulated_age_days:.1f} days</b>\n"
            f"• Temporal State: <b>{'Paused ⏸️' if state.is_paused else 'Active ▶️'}</b>\n"
            f"• Hunger: <b>{int(drives.get('hunger', 0) * 100)}%</b>\n"
            f"• Thirst: <b>{int(drives.get('thirst', 0) * 100)}%</b>\n"
            f"• Energy: <b>{int(drives.get('energy', 0) * 100)}%</b>\n"
            f"• Comfort: <b>{int(drives.get('comfort', 0) * 100)}%</b>\n"
            f"• Stress: <b>{int(drives.get('stress', 0) * 100)}%</b>\n"
            f"• Curiosity: <b>{int(drives.get('curiosity', 0) * 100)}%</b>\n"
            f"• Circadian Phase: <b>{drives.get('circadian_phase', 0.0):.2f}</b>"
        )

