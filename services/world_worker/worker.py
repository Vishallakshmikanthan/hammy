"""
HAMMY — Persistent World Worker (`services/world_worker/worker.py`).
Implements:
  1. Distributed lease acquisition per pet.
  2. Bounded catch-up simulation using empirical skill models and homeostatic policy.
  3. Single atomic transaction for state mutation and deterministic event insertion.
  4. Automatic rollback on mid-transaction crash / exception.
  5. CLI and script entrypoints for scheduled (one-shot) or continuous looping modes.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import signal
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from infrastructure.database.connection import engine as default_engine, get_db_session
from infrastructure.database.models import Pet, PetState, WorldEvent
from services.world_worker.catchup import CatchUpSimulator
from services.world_worker.lease import LeaseManager

logger = logging.getLogger("hammy.world_worker")


class WorldWorker:
    """
    Persistent World Worker that acquires per-pet leases, evaluates elapsed time,
    advances simulation via bounded skill-outcome catchup, writes events and state
    in one atomic transaction, and safely releases leases.
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        engine=None,
        lease_ttl_sec: float = 30.0,
        max_sim_sec_per_run: float = 3600.0,
        max_steps_per_run: int = 50,
    ):
        self.worker_id = worker_id or f"worker_{os.getpid()}_{uuid.uuid4().hex[:6]}"
        self.engine = engine or default_engine
        self.lease_ttl_sec = lease_ttl_sec
        self.lease_manager = LeaseManager(default_ttl_sec=lease_ttl_sec)
        self.simulator = CatchUpSimulator(
            max_sim_sec_per_run=max_sim_sec_per_run,
            max_steps_per_run=max_steps_per_run,
        )

    def step_pet(
        self,
        pet_id: str,
        now: Optional[datetime.datetime] = None,
        fail_hook: Optional[Callable[[], None]] = None,
    ) -> Dict[str, Any]:
        """
        Executes one atomic catch-up cycle for a single pet:
          1. Acquires distributed per-pet lease.
          2. Runs simulation steps.
          3. Writes events and updated state in one atomic transaction.
          4. Releases lease.
        """
        # 1. Acquire Lease
        with get_db_session(self.engine) as session:
            acquired = self.lease_manager.acquire_lease(
                session, pet_id, self.worker_id, ttl_sec=self.lease_ttl_sec, now=now
            )
            if not acquired:
                logger.info("Pet %s is currently locked by another worker.", pet_id)
                return {"status": "lease_unavailable", "pet_id": pet_id}

        try:
            # 2 & 3. Atomic Simulation & Mutation Transaction
            with get_db_session(self.engine) as session:
                pet = session.get(Pet, pet_id)
                pet_state = session.get(PetState, pet_id)
                if not pet or not pet_state:
                    return {"status": "not_found", "pet_id": pet_id}

                # Find latest world tick for this pet
                max_tick = (
                    session.query(func.max(WorldEvent.world_tick))
                    .filter(WorldEvent.pet_id == pet_id)
                    .scalar()
                )
                current_tick = (max_tick or 0) + 1

                # Simulate catch-up
                sim_res = self.simulator.simulate_catchup(
                    pet_state=pet_state,
                    pet=pet,
                    current_tick=current_tick,
                    now=now,
                )

                # Insert events idempotently (deterministic event_id primary key)
                for evt in sim_res["events"]:
                    existing = session.get(WorldEvent, evt.event_id)
                    if existing is None:
                        session.add(evt)

                # Mutate pet_state with optimistic concurrency version increment
                pet_state.version += 1
                pet_state.sim_time_sec = sim_res["new_sim_time_sec"]
                pet_state.simulated_age_days = sim_res["new_simulated_age_days"]
                pet_state.last_simulated_at = sim_res["new_last_simulated_at"]
                pet_state.drives = sim_res["new_drives"]
                pet_state.position_xyz = sim_res["new_position_xyz"]

                flags = sim_res["new_flags"]
                pet_state.inside_hideout = flags["inside_hideout"]
                pet_state.inside_tunnel = flags["inside_tunnel"]
                pet_state.on_wheel = flags["on_wheel"]
                pet_state.cheek_pouch_fill = flags["cheek_pouch_fill"]

                # Simulated crash / fail hook to prove atomic rollback
                if fail_hook is not None:
                    fail_hook()

                session.flush()

            return {
                "status": "success",
                "pet_id": pet_id,
                "steps_executed": sim_res["steps_executed"],
                "simulated_sec": sim_res["simulated_sec"],
                "remaining_sim_sec": sim_res["remaining_sim_sec"],
                "events_count": len(sim_res["events"]),
                "new_sim_time_sec": sim_res["new_sim_time_sec"],
                "is_paused": sim_res.get("status") == "paused",
            }

        finally:
            # 4. Release Lease
            try:
                with get_db_session(self.engine) as session:
                    self.lease_manager.release_lease(session, pet_id, self.worker_id, now=now)
            except Exception as e:
                logger.warning("Error releasing lease for pet %s: %s", pet_id, e)

    def run_once(
        self,
        pet_ids: Optional[List[str]] = None,
        now: Optional[datetime.datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Executes a single tick over specified or all registered pets."""
        target_ids = pet_ids
        if target_ids is None:
            with get_db_session(self.engine) as session:
                pets = session.query(Pet.id).all()
                target_ids = [p[0] for p in pets]

        results = []
        for pid in target_ids:
            res = self.step_pet(pid, now=now)
            results.append(res)
        return results

    def run_loop(
        self,
        interval_sec: float = 5.0,
        pet_ids: Optional[List[str]] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        """Runs the world worker continuously in a loop until stopped."""
        stopper = stop_event or threading.Event()

        def _handle_signal(signum, frame):
            logger.info("Received termination signal %s. Stopping worker gracefully...", signum)
            stopper.set()

        try:
            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)
        except (ValueError, AttributeError):
            # Not in main thread or unsupported platform signal
            pass

        logger.info(
            "WorldWorker %s starting loop (interval=%.1fs, pets=%s)...",
            self.worker_id,
            interval_sec,
            pet_ids or "ALL",
        )

        while not stopper.is_set():
            t0 = time.time()
            try:
                summaries = self.run_once(pet_ids=pet_ids)
                logger.debug("Worker loop cycle finished: %s", summaries)
            except Exception as e:
                logger.error("Exception during worker loop cycle: %s", e, exc_info=True)

            elapsed = time.time() - t0
            sleep_time = max(0.1, interval_sec - elapsed)
            stopper.wait(timeout=sleep_time)

        logger.info("WorldWorker %s stopped cleanly.", self.worker_id)


def main():
    parser = argparse.ArgumentParser(description="HAMMY Persistent World Worker")
    parser.add_argument("--once", action="store_true", help="Run once and exit (scheduled job mode)")
    parser.add_argument("--loop", action="store_true", help="Run continuously in a loop")
    parser.add_argument("--interval", type=float, default=5.0, help="Loop interval in seconds (default: 5.0)")
    parser.add_argument("--pet-id", type=str, default=None, help="Target specific pet ID")
    parser.add_argument("--max-sim-sec", type=float, default=3600.0, help="Max simulated seconds per tick")
    parser.add_argument("--max-steps", type=int, default=50, help="Max skill steps per tick")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    worker = WorldWorker(
        max_sim_sec_per_run=args.max_sim_sec,
        max_steps_per_run=args.max_steps,
    )

    pets = [args.pet_id] if args.pet_id else None

    if args.loop:
        worker.run_loop(interval_sec=args.interval, pet_ids=pets)
    else:
        results = worker.run_once(pet_ids=pets)
        print(f"World worker run completed: {results}")


if __name__ == "__main__":
    main()

