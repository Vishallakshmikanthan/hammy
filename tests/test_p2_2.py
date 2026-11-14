"""
HAMMY — P2.2 Acceptance Test Suite (`tests/test_p2_2.py`).
Tests all P2.2 acceptance criteria:
  1. Crash mid-update leaves state consistent (transaction rollback).
  2. Double-run produces no duplicate events (deterministic event IDs).
  3. A 7-day gap completes in bounded work (capping catch-up chunks).
  4. Pause/resume stops advancement.
  5. Distributed lease mutual exclusion and timeout takeover.
"""

from __future__ import annotations

import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.database.connection import Base, setup_immutability_triggers
from infrastructure.database.models import Pet, PetState, WorkerLease, WorldEvent
from infrastructure.database.seeds import seed_database
from services.world_worker.worker import WorldWorker


def _ensure_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


@pytest.fixture
def isolated_db():
    """Provides an isolated in-memory SQLite database with schema, triggers, and seed data."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    setup_immutability_triggers(engine)

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with Session() as session:
        seed_database(session)

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_crash_mid_update_leaves_state_consistent(isolated_db):
    """AC-1: Mid-update crash causes complete transaction rollback with zero leaked events."""
    engine = isolated_db
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with Session() as session:
        state_init = session.get(PetState, "pet_hammy_01")
        init_version = state_init.version
        init_sim_time = state_init.sim_time_sec
        init_last_sim = state_init.last_simulated_at
        init_events_count = session.query(WorldEvent).count()

    if init_last_sim.tzinfo is None:
        init_last_sim = init_last_sim.replace(tzinfo=datetime.timezone.utc)
    future_time = init_last_sim + datetime.timedelta(hours=2)

    def fail_hook():
        raise RuntimeError("SIMULATED_CRASH_MID_TRANSACTION")

    worker = WorldWorker(worker_id="crash_worker_01", engine=engine)

    with pytest.raises(RuntimeError, match="SIMULATED_CRASH_MID_TRANSACTION"):
        worker.step_pet("pet_hammy_01", now=future_time, fail_hook=fail_hook)

    # Verify state after crash
    with Session() as session:
        state_after = session.get(PetState, "pet_hammy_01")
        events_after = session.query(WorldEvent).count()

        assert state_after.version == init_version
        assert state_after.sim_time_sec == init_sim_time
        assert _ensure_utc(state_after.last_simulated_at) == init_last_sim
        assert events_after == init_events_count


def test_double_run_produces_no_duplicate_events(isolated_db):
    """AC-2: Re-running worker on identical interval produces no duplicate event IDs."""
    engine = isolated_db
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with Session() as session:
        state = session.get(PetState, "pet_hammy_01")
        t0 = state.last_simulated_at
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=datetime.timezone.utc)

    target_time = t0 + datetime.timedelta(minutes=30)
    worker = WorldWorker(worker_id="worker_dedup", engine=engine)

    # First run
    res1 = worker.step_pet("pet_hammy_01", now=target_time)
    assert res1["status"] == "success"

    with Session() as session:
        events_1 = session.query(WorldEvent).filter_by(pet_id="pet_hammy_01").all()
        event_ids_1 = [e.event_id for e in events_1]
        assert len(event_ids_1) == len(set(event_ids_1)), "Duplicate event_ids in first run!"

    # Second run immediately without new time elapsed
    res2 = worker.step_pet("pet_hammy_01", now=target_time)
    assert res2["status"] == "success"
    assert res2["steps_executed"] == 0

    with Session() as session:
        events_2 = session.query(WorldEvent).filter_by(pet_id="pet_hammy_01").all()
        event_ids_2 = [e.event_id for e in events_2]
        # Total event count must not increase
        assert len(event_ids_2) == len(event_ids_1)
        assert len(event_ids_2) == len(set(event_ids_2))


def test_seven_day_gap_completes_in_bounded_work(isolated_db):
    """AC-3: A 7-day offline gap completes in bounded chunks and logs in-progress summary."""
    engine = isolated_db
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with Session() as session:
        state = session.get(PetState, "pet_hammy_01")
        t0 = state.last_simulated_at
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=datetime.timezone.utc)

    # 7-day offline gap = 604,800 seconds
    seven_days_later = t0 + datetime.timedelta(days=7)

    # Configure worker with strict cap: 1800 sim seconds and max 20 steps
    worker = WorldWorker(
        worker_id="bounded_worker",
        engine=engine,
        max_sim_sec_per_run=1800.0,
        max_steps_per_run=20,
    )

    res = worker.step_pet("pet_hammy_01", now=seven_days_later)
    assert res["status"] == "success"

    # Must be bounded!
    assert res["steps_executed"] <= 20
    assert res["simulated_sec"] <= 2400.0  # 1800s budget + at most one finishing skill duration
    assert res["remaining_sim_sec"] > 500000.0  # Substantial time remaining for subsequent ticks

    # Check that catch_up_in_progress event was recorded
    with Session() as session:
        summary_event = (
            session.query(WorldEvent)
            .filter_by(pet_id="pet_hammy_01", event_type="catch_up_in_progress")
            .first()
        )
        assert summary_event is not None
        assert summary_event.origin == "rule"
        assert summary_event.behaviour_type == "rule"
        assert summary_event.payload["remaining_sim_sec"] > 500000.0


def test_pause_stops_advancement(isolated_db):
    """AC-4: When is_paused is True, simulation time and drives do not advance."""
    engine = isolated_db
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with Session() as session:
        state = session.get(PetState, "pet_hammy_01")
        state.is_paused = True
        session.commit()

        t0 = state.last_simulated_at
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=datetime.timezone.utc)
        init_sim_time = state.sim_time_sec
        init_drives = dict(state.drives)

    # 1 full day passes in wall-clock time
    one_day_later = t0 + datetime.timedelta(days=1)
    worker = WorldWorker(worker_id="pause_worker", engine=engine)

    res = worker.step_pet("pet_hammy_01", now=one_day_later)
    assert res["status"] == "success"
    assert res["steps_executed"] == 0
    assert res["simulated_sec"] == 0.0
    assert res["is_paused"] is True

    # Check database state
    with Session() as session:
        state_after = session.get(PetState, "pet_hammy_01")
        assert state_after.sim_time_sec == init_sim_time
        assert state_after.drives == init_drives
        # last_simulated_at should be updated to current time so no backlog is created
        assert _ensure_utc(state_after.last_simulated_at) >= one_day_later


def test_lease_mutual_exclusion_and_expiration_takeover(isolated_db):
    """AC-5: Leases block concurrent workers and allow takeover upon expiration."""
    engine = isolated_db
    worker1 = WorldWorker(worker_id="worker_alpha", engine=engine, lease_ttl_sec=5.0)
    worker2 = WorldWorker(worker_id="worker_beta", engine=engine, lease_ttl_sec=5.0)

    now = datetime.datetime.now(datetime.timezone.utc)

    # Worker 1 acquires lease
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with Session() as session:
        acq1 = worker1.lease_manager.acquire_lease(session, "pet_hammy_01", worker1.worker_id, ttl_sec=5.0, now=now)
        session.commit()
        assert acq1 is True

    # Worker 2 attempts while lease active (now + 2s)
    with Session() as session:
        acq2 = worker2.lease_manager.acquire_lease(session, "pet_hammy_01", worker2.worker_id, ttl_sec=5.0, now=now + datetime.timedelta(seconds=2))
        session.commit()
        assert acq2 is False

    # After TTL expires (now + 6s), Worker 2 successfully takes over lease
    with Session() as session:
        acq2_expired = worker2.lease_manager.acquire_lease(session, "pet_hammy_01", worker2.worker_id, ttl_sec=5.0, now=now + datetime.timedelta(seconds=6))
        session.commit()
        assert acq2_expired is True
        lease = session.get(WorkerLease, "pet_hammy_01")
        assert lease.worker_id == "worker_beta"


def test_worker_run_once_entrypoint(isolated_db):
    """AC-6: WorldWorker.run_once() processes registered pets and returns summary."""
    engine = isolated_db
    worker = WorldWorker(worker_id="runner_worker", engine=engine)

    results = worker.run_once()
    assert len(results) == 1
    assert results[0]["pet_id"] == "pet_hammy_01"
    assert results[0]["status"] == "success"


def test_worker_run_loop_terminates_cleanly_on_stop_event(isolated_db):
    """AC-6: WorldWorker.run_loop() runs iteratively and stops cleanly on stop_event."""
    import threading
    import time

    engine = isolated_db
    worker = WorldWorker(worker_id="loop_worker", engine=engine)
    stop_event = threading.Event()

    # Pre-set stop_event so loop exits immediately after 1 cycle
    stop_event.set()
    worker.run_loop(interval_sec=0.01, stop_event=stop_event)
    # Reaching here without blocking or error confirms clean exit

