"""
HAMMY — Notification Worker Daemon (`services/notification_worker/worker.py`).
Executes outbox processing loop, handles exponential backoff, and enqueues daily digests.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from infrastructure.database.connection import engine as default_engine, get_db_session
from infrastructure.database.models import NotificationPreference, Pet
from services.notification_worker.client import TelegramClient
from services.notification_worker.digest import DailyDigestBuilder
from services.notification_worker.outbox import OutboxProcessor

logger = logging.getLogger("hammy.notification_worker")


class NotificationWorker:
    """Daemon processing the notification outbox and scheduling digests."""

    def __init__(
        self,
        telegram_client: Optional[Any] = None,
        engine=None,
        max_retries: int = 3,
        base_delay_sec: float = 30.0,
    ):
        self.engine = engine or default_engine
        self.client = telegram_client or TelegramClient()
        self.processor = OutboxProcessor(
            telegram_client=self.client,
            max_retries=max_retries,
            base_delay_sec=base_delay_sec,
        )

    def run_once(self, now: Optional[datetime.datetime] = None) -> Dict[str, int]:
        """Runs one processing pass over the outbox."""
        with get_db_session(self.engine) as session:
            return self.processor.process_pending(session, now=now)

    def enqueue_daily_digests_if_due(self, now: Optional[datetime.datetime] = None) -> int:
        """Enqueues daily digests for users whose scheduled digest time matches current hour/minute."""
        curr_time = now or datetime.datetime.now(datetime.timezone.utc)
        curr_hm = curr_time.strftime("%H:%M")

        enqueued_count = 0
        with get_db_session(self.engine) as session:
            prefs = (
                session.query(NotificationPreference)
                .filter(
                    NotificationPreference.daily_digest_enabled == True,
                    NotificationPreference.telegram_chat_id != None,
                    NotificationPreference.daily_digest_time_utc == curr_hm,
                )
                .all()
            )

            for pref in prefs:
                pets = session.query(Pet).filter_by(user_id=pref.user_id).all()
                for pet in pets:
                    digest = DailyDigestBuilder.build_digest(session, pet.id, now=curr_time)
                    self.processor.enqueue(
                        session=session,
                        user_id=pref.user_id,
                        pet_id=pet.id,
                        category="digest",
                        text=digest["html_message"],
                        now=curr_time,
                    )
                    enqueued_count += 1

        return enqueued_count

    def run_loop(
        self,
        interval_sec: float = 5.0,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        """Continuous polling loop."""
        stopper = stop_event or threading.Event()

        def _handle_signal(signum, frame):
            logger.info("Signal %s received. Stopping notification worker...", signum)
            stopper.set()

        try:
            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)
        except (ValueError, AttributeError):
            pass

        logger.info("NotificationWorker started (interval=%.1fs)...", interval_sec)

        while not stopper.is_set():
            t0 = time.time()
            try:
                self.enqueue_daily_digests_if_due()
                counts = self.run_once()
                if sum(counts.values()) > 0:
                    logger.info("Outbox cycle processed: %s", counts)
            except Exception as e:
                logger.error("Error in notification worker cycle: %s", e, exc_info=True)

            elapsed = time.time() - t0
            stopper.wait(timeout=max(0.1, interval_sec - elapsed))

        logger.info("NotificationWorker stopped cleanly.")


def main():
    parser = argparse.ArgumentParser(description="HAMMY Notification Outbox Worker")
    parser.add_argument("--once", action="store_true", help="Process once and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuous processing loop")
    parser.add_argument("--interval", type=float, default=5.0, help="Loop interval seconds")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    worker = NotificationWorker()

    if args.loop:
        worker.run_loop(interval_sec=args.interval)
    else:
        counts = worker.run_once()
        print(f"Notification worker outbox run: {counts}")


if __name__ == "__main__":
    main()

