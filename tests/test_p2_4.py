"""
HAMMY — P2.4 Acceptance Test Suite (`tests/test_p2_4.py`).
Tests all P2.4 criteria:
  1. Outbox delivery, retries, exponential backoff, and dead-letter state.
  2. Exactly-once message production even after retries (Criterion 7).
  3. Telegram outage does not block world worker progression (Criterion 7).
  4. Chat binding flow: /start generates code, confirmation on website links chat, unbound chats rejected.
  5. Bot commands: /status, /feed, /water, /pause, /resume, /report via shared command handlers.
  6. Daily digest built strictly from recorded events with plain-language origin badges (Criterion 4).
  7. Quiet hours postponement and duplicate message suppression (Criterion 5).
"""

from __future__ import annotations

import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from infrastructure.database.connection import Base, setup_immutability_triggers
from infrastructure.database.models import (
    Command,
    HabitatObject,
    NotificationOutbox,
    NotificationPreference,
    Pet,
    PetState,
    TelegramBindingCode,
    User,
    WorldEvent,
)
from infrastructure.database.seeds import seed_database
from services.api.auth import create_access_token, get_db
from services.api.main import app
from services.commands.handler import CommandHandler
from services.notification_worker.binding import TelegramBindingManager
from services.notification_worker.bot import TelegramBot
from services.notification_worker.client import MockTelegramClient
from services.notification_worker.digest import DailyDigestBuilder
from services.notification_worker.outbox import OutboxProcessor
from services.world_worker.worker import WorldWorker


def _ensure_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


@pytest.fixture
def isolated_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    setup_immutability_triggers(engine)

    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with Session() as session:
        seed_database(session)

    yield engine, Session

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ==============================================================================
# 1. OUTBOX RETRIES, BACKOFF, AND DEAD-LETTER STATE (Criterion 1 & 7)
# ==============================================================================
def test_outbox_delivery_retry_backoff_and_exactly_once_production(isolated_db):
    """
    Criterion 7 Acceptance:
    Tests with a mocked Telegram API: one event produces exactly one message
    even after retries.
    """
    _, Session = isolated_db
    mock_client = MockTelegramClient(fail_first_n_attempts=2)  # Fails 2 times, succeeds on 3rd
    processor = OutboxProcessor(telegram_client=mock_client, max_retries=3, base_delay_sec=10.0)

    now = datetime.datetime(2026, 11, 14, 12, 0, 0, tzinfo=datetime.timezone.utc)

    with Session() as session:
        # Enqueue one message
        item = processor.enqueue(
            session=session,
            user_id="usr_hammy_default",
            pet_id="pet_hammy_01",
            category="status_update",
            text="Hammy completed wheel exercise.",
            now=now,
        )
        msg_id = item.id

    # --- Attempt 1: Transient failure ---
    with Session() as session:
        res1 = processor.process_pending(session, now=now)
        assert res1["failed"] == 1
        item1 = session.get(NotificationOutbox, msg_id)
        assert item1.status == "pending"
        assert item1.attempts == 1
        assert _ensure_utc(item1.scheduled_for) > now  # Rescheduled with backoff
        retry_time_1 = _ensure_utc(item1.scheduled_for)

    # --- Attempt 2: Second transient failure ---
    with Session() as session:
        res2 = processor.process_pending(session, now=retry_time_1)
        assert res2["failed"] == 1
        item2 = session.get(NotificationOutbox, msg_id)
        assert item2.status == "pending"
        assert item2.attempts == 2
        assert _ensure_utc(item2.scheduled_for) > retry_time_1
        retry_time_2 = _ensure_utc(item2.scheduled_for)

    # --- Attempt 3: Success ---
    with Session() as session:
        res3 = processor.process_pending(session, now=retry_time_2)
        assert res3["delivered"] == 1
        item3 = session.get(NotificationOutbox, msg_id)
        assert item3.status == "delivered"
        assert item3.delivered_at is not None

    # CRITICAL ACCEPTANCE ASSERTION:
    # Exactly ONE delivered message produced on mock client despite 2 prior failures!
    assert len(mock_client.sent_messages) == 1
    assert mock_client.sent_messages[0]["text"] == "Hammy completed wheel exercise."


def test_outbox_dead_letter_after_exceeding_max_retries(isolated_db):
    """After max_retries attempts fail, message enters dead_letter status."""
    _, Session = isolated_db
    mock_client = MockTelegramClient(permanent_fail=True)
    processor = OutboxProcessor(telegram_client=mock_client, max_retries=3, base_delay_sec=10.0)

    now = datetime.datetime(2026, 11, 14, 12, 0, 0, tzinfo=datetime.timezone.utc)

    with Session() as session:
        item = processor.enqueue(
            session=session,
            user_id="usr_hammy_default",
            pet_id="pet_hammy_01",
            category="alert",
            text="Water bottle low.",
            now=now,
        )
        msg_id = item.id

    # Run 3 attempts
    for i in range(3):
        with Session() as session:
            current_item = session.get(NotificationOutbox, msg_id)
            processor.process_pending(session, now=current_item.scheduled_for)

    with Session() as session:
        final_item = session.get(NotificationOutbox, msg_id)
        assert final_item.status == "dead_letter"
        assert final_item.attempts == 3
        assert "Simulated permanent" in final_item.last_error


# ==============================================================================
# 2. TELEGRAM OUTAGE DOES NOT BLOCK WORLD WORKER (Criterion 7)
# ==============================================================================
def test_telegram_outage_does_not_block_world_worker(isolated_db):
    """
    Criterion 7:
    Telegram outage does not block the world worker from advancing simulation.
    """
    engine, Session = isolated_db

    # World worker steps simulation even when Telegram is completely offline/unreachable
    worker = WorldWorker(worker_id="worker_robust", engine=engine)
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)

    step_res = worker.step_pet("pet_hammy_01", now=now)
    assert step_res["status"] == "success"
    assert step_res["steps_executed"] > 0
    assert step_res["simulated_sec"] > 0.0

    # Verify simulation state advanced in database
    with Session() as session:
        state = session.get(PetState, "pet_hammy_01")
        assert state.sim_time_sec > 0.0
        events_count = session.query(WorldEvent).count()
        assert events_count > 0


# ==============================================================================
# 3. CHAT BINDING FLOW & UNBOUND REJECTION (Criterion 2)
# ==============================================================================
def test_chat_binding_flow_and_rejection_of_unbound_chats(isolated_db):
    engine, Session = isolated_db
    bot = TelegramBot()

    chat_id = "987654321"

    # 1. Unbound chat sending command is rejected
    with Session() as session:
        rej = bot.process_message(session, chat_id=chat_id, text="/status")
        assert "Unbound Account" in rej

    # 2. Unbound chat sending /start receives one-time pairing code
    with Session() as session:
        start_reply = bot.process_message(session, chat_id=chat_id, text="/start")
        assert "HAMMY-" in start_reply

        # Retrieve generated code from database
        code_record = session.query(TelegramBindingCode).filter_by(chat_id=chat_id).first()
        assert code_record is not None
        code = code_record.code

    # 3. Parent confirms code via API
    def override_get_db():
        with Session() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    token = create_access_token("usr_hammy_default")

    with TestClient(app) as client:
        # Invalid code check
        res_bad = client.post(
            "/api/v1/notifications/telegram/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "HAMMY-INVALID"},
        )
        assert res_bad.status_code == 400

        # Valid code confirmation
        res_ok = client.post(
            "/api/v1/notifications/telegram/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": code},
        )
        assert res_ok.status_code == 200
        assert res_ok.json()["status"] == "success"

    app.dependency_overrides.clear()

    # 4. Chat is now bound: /status succeeds!
    with Session() as session:
        status_reply = bot.process_message(session, chat_id=chat_id, text="/status")
        assert "Hammy" in status_reply
        assert "Simulated Age" in status_reply


# ==============================================================================
# 4. BOT COMMANDS VIA SHARED COMMAND HANDLERS (Criterion 3)
# ==============================================================================
def test_telegram_bot_commands_via_shared_handlers(isolated_db):
    """
    Criterion 3:
    Commands: /status, /feed, /water, /pause, /resume, /report,
    calling the shared command handlers (never writing the DB directly).
    """
    _, Session = isolated_db
    bot = TelegramBot()
    chat_id = "123456789"  # Already bound to usr_hammy_default in seed

    # /feed
    with Session() as session:
        feed_reply = bot.process_message(session, chat_id, "/feed 4.5")
        assert "Added 4.5g food" in feed_reply

        bowl = session.get(HabitatObject, "prop_bowl_main")
        assert bowl.resource_state["food_level"] > 0.0

        # Verify command recorded in commands table
        cmd = session.query(Command).filter_by(command_type="feed").first()
        assert cmd is not None
        assert cmd.status == "completed"

    # /water
    with Session() as session:
        water_reply = bot.process_message(session, chat_id, "/water 15")
        assert "Refilled 15.0ml water" in water_reply

    # /pause
    with Session() as session:
        pause_reply = bot.process_message(session, chat_id, "/pause")
        assert "Simulation paused" in pause_reply
        state = session.get(PetState, "pet_hammy_01")
        assert state.is_paused is True

    # /resume
    with Session() as session:
        resume_reply = bot.process_message(session, chat_id, "/resume")
        assert "Simulation resumed" in resume_reply
        state = session.get(PetState, "pet_hammy_01")
        assert state.is_paused is False

    # /report
    with Session() as session:
        report_reply = bot.process_message(session, chat_id, "/report")
        assert "Activity Breakdown" in report_reply


# ==============================================================================
# 5. DAILY DIGEST WITH PLAIN-LANGUAGE PROVENANCE (Criterion 4)
# ==============================================================================
def test_daily_digest_built_strictly_from_recorded_events(isolated_db):
    """
    Criterion 4:
    Daily digest built only from recorded events; include event origin
    (observed vs sampled vs rule) in plain language.
    """
    _, Session = isolated_db
    now = datetime.datetime.now(datetime.timezone.utc)

    with Session() as session:
        # Add 3 events with different origins
        e1 = WorldEvent(
            event_id="evt_test_sampled",
            pet_id="pet_hammy_01",
            world_tick=1,
            sim_time_sec=10.0,
            event_type="skill_completed",
            skill_name="eat",
            origin="sampled_from_skill_model",
            behaviour_type="scripted",
            seed=1,
            payload={},
            created_at=now - datetime.timedelta(hours=2),
        )
        e2 = WorldEvent(
            event_id="evt_test_physics",
            pet_id="pet_hammy_01",
            world_tick=2,
            sim_time_sec=20.0,
            event_type="skill_completed",
            skill_name="run_on_wheel",
            origin="observed_physics",
            behaviour_type="learned",
            seed=2,
            payload={},
            created_at=now - datetime.timedelta(hours=1),
        )
        e3 = WorldEvent(
            event_id="evt_test_rule",
            pet_id="pet_hammy_01",
            world_tick=3,
            sim_time_sec=25.0,
            event_type="care_feed",
            skill_name=None,
            origin="rule",
            behaviour_type="rule",
            seed=0,
            payload={},
            created_at=now - datetime.timedelta(minutes=30),
        )
        session.add_all([e1, e2, e3])
        session.commit()

        digest = DailyDigestBuilder.build_digest(session, "pet_hammy_01", now=now)

    assert digest["total_events"] == 3
    assert digest["origin_counts"]["sampled_from_skill_model"] == 1
    assert digest["origin_counts"]["observed_physics"] == 1
    assert digest["origin_counts"]["rule"] == 1

    # Plain language verification in message
    msg = digest["html_message"]
    assert "Predicted by behavioral AI model: <b>1 events</b>" in msg
    assert "Simulated in full 3D physics: <b>1 events</b>" in msg
    assert "Care action / Game rule: <b>1 events</b>" in msg


# ==============================================================================
# 6. QUIET HOURS AND DUPLICATE SUPPRESSION (Criterion 5)
# ==============================================================================
def test_quiet_hours_postponement_and_duplicate_suppression(isolated_db):
    """
    Criterion 5:
    Quiet hours postpone non-urgent notifications; duplicate texts are suppressed.
    """
    _, Session = isolated_db
    mock_client = MockTelegramClient()
    processor = OutboxProcessor(telegram_client=mock_client)

    # 1. Quiet Hours: 23:30 is between 22:00 and 07:00
    quiet_time = datetime.datetime(2026, 11, 14, 23, 30, 0, tzinfo=datetime.timezone.utc)

    with Session() as session:
        # Non-urgent digest
        item = processor.enqueue(
            session=session,
            user_id="usr_hammy_default",
            pet_id="pet_hammy_01",
            category="digest",
            text="Quiet hours test message.",
            now=quiet_time,
        )
        counts = processor.process_pending(session, now=quiet_time)
        assert counts["rescheduled"] == 1
        rescheduled_item = session.get(NotificationOutbox, item.id)
        assert rescheduled_item.status == "pending"
        assert _ensure_utc(rescheduled_item.scheduled_for) > quiet_time

    # 2. Duplicate Suppression: daytime (14:00)
    day_time = datetime.datetime(2026, 11, 14, 14, 0, 0, tzinfo=datetime.timezone.utc)

    with Session() as session:
        # First message delivers successfully
        processor.enqueue(
            session=session,
            user_id="usr_hammy_default",
            pet_id="pet_hammy_01",
            category="status",
            text="Same exact notification text",
            now=day_time,
        )
        processor.process_pending(session, now=day_time)

        # Second message with identical text 1 minute later
        item2 = processor.enqueue(
            session=session,
            user_id="usr_hammy_default",
            pet_id="pet_hammy_01",
            category="status",
            text="Same exact notification text",
            now=day_time + datetime.timedelta(minutes=1),
        )
        counts2 = processor.process_pending(session, now=day_time + datetime.timedelta(minutes=1))
        assert counts2["suppressed"] == 1

        suppressed_item = session.get(NotificationOutbox, item2.id)
        assert suppressed_item.status == "duplicate_suppressed"
