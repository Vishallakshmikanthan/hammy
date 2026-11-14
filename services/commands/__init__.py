"""
HAMMY — Shared Command Handler Architecture (`services/commands`).
Used by both the FastAPI backend and the Telegram bot to enforce:
  - Strict parameter validation (bounds, allowed types).
  - Client-side idempotency keys via `commands.command_id` (Rule 4).
  - Care action and world event auditing.
"""

from services.commands.handler import CommandHandler, CommandResult, CommandValidationError

__all__ = ["CommandHandler", "CommandResult", "CommandValidationError"]

