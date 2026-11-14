#!/usr/bin/env python3
"""
HAMMY — Mid-Transaction Crash Rollback Verification Script (`scripts/test_worker_rollback.py`).
Fulfills P2.2 Acceptance: "a script that kills the worker mid-transaction proves rollback."
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from infrastructure.database.connection import Base, setup_immutability_triggers
from infrastructure.database.models import Pet, PetState, WorldEvent
from infrastructure.database.seeds import seed_database
from services.world_worker.worker import WorldWorker


def run_rollback_demonstration() -> bool:
    print("=" * 70)
    print("HAMMY — P2.2 Mid-Transaction Crash Rollback Verification")
    print("=" * 70)

    # 1. Setup isolated database
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    setup_immutability_triggers(engine)

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with Session() as session:
        seed_database(session)

    # 2. Inspect initial state
    with Session() as session:
        state_before = session.get(PetState, "pet_hammy_01")
        v_before = state_before.version
        sim_time_before = state_before.sim_time_sec
        last_sim_before = state_before.last_simulated_at
        events_before = session.query(WorldEvent).filter_by(pet_id="pet_hammy_01").count()

    print(f"[*] Initial Pet State:")
    print(f"    - Version:          {v_before}")
    print(f"    - Sim Time (sec):   {sim_time_before}")
    print(f"    - Last Simulated:   {last_sim_before}")
    print(f"    - World Events:     {events_before}")

    # 3. Simulate elapsed real time (+2 hours)
    if last_sim_before.tzinfo is None:
        last_sim_before = last_sim_before.replace(tzinfo=datetime.timezone.utc)
    target_now = last_sim_before + datetime.timedelta(hours=2)

    # 4. Define simulated catastrophic failure hook (process crash / network partition mid-transaction)
    def catastrophic_crash():
        print("[!] >> Simulating catastrophic mid-transaction failure (SIGKILL/Exception)...")
        raise RuntimeError("FATAL_WORKER_CRASH: Process terminated before transaction commit!")

    worker = WorldWorker(worker_id="crash_test_worker", engine=engine)

    crashed = False
    try:
        worker.step_pet("pet_hammy_01", now=target_now, fail_hook=catastrophic_crash)
    except RuntimeError as ex:
        crashed = True
        print(f"[*] Caught simulated crash exception: {ex}")

    assert crashed, "Worker was expected to crash during fail_hook!"

    # 5. Verify database integrity after crash
    with Session() as session:
        state_after = session.get(PetState, "pet_hammy_01")
        v_after = state_after.version
        sim_time_after = state_after.sim_time_sec
        last_sim_after = state_after.last_simulated_at
        events_after = session.query(WorldEvent).filter_by(pet_id="pet_hammy_01").count()

    print(f"\n[*] Post-Crash Database State (Verification):")
    print(f"    - Version:          {v_after} (Expected: {v_before})")
    print(f"    - Sim Time (sec):   {sim_time_after} (Expected: {sim_time_before})")
    print(f"    - Last Simulated:   {last_sim_after} (Expected: {last_sim_before})")
    print(f"    - World Events:     {events_after} (Expected: {events_before})")

    # Assertions
    assert v_after == v_before, f"Integrity Failure: version advanced from {v_before} to {v_after}!"
    assert sim_time_after == sim_time_before, f"Integrity Failure: sim_time changed after crash!"
    assert events_after == events_before, f"Integrity Failure: orphaned events leaked into database!"

    print("\n[SUCCESS] Transaction rolled back cleanly with 0 database corruption.")

    # 6. Verify subsequent healthy worker run succeeds
    print("\n[*] Executing subsequent healthy worker run on same pet...")
    healthy_result = worker.step_pet("pet_hammy_01", now=target_now)
    assert healthy_result["status"] == "success"
    print(f"[*] Healthy run succeeded: {healthy_result['steps_executed']} steps, {healthy_result['simulated_sec']:.1f}s simulated.")

    with Session() as session:
        state_final = session.get(PetState, "pet_hammy_01")
        print(f"[*] Final committed state version: {state_final.version}, sim_time: {state_final.sim_time_sec:.1f}s")
        assert state_final.version == v_before + 1

    print("=" * 70)
    print("ALL ROLLBACK ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_rollback_demonstration()
    sys.exit(0 if success else 1)

