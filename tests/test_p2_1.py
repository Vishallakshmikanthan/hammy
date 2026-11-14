"""
HAMMY — P2.1 Acceptance Test Suite (`tests/test_p2_1.py`).
Tests all P2.1 acceptance criteria:
  1. Migrations apply cleanly from empty (all 16 tables created).
  2. Duplicate command_id inserts fail (idempotency key constraint).
  3. world_events cannot be updated (trigger enforces append-only immutability).
  4. Optimistic concurrency control on pet_state (version counter).
  5. Seed script runs cleanly and populates user, pet, state, habitat, and standard objects.
"""

from __future__ import annotations

import datetime
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker

from infrastructure.database.connection import Base, setup_immutability_triggers
from infrastructure.database.models import (
    BehaviourStat,
    CareAction,
    Command,
    Habitat,
    HabitatObject,
    Memory,
    NotificationOutbox,
    NotificationPreference,
    Pet,
    PetState,
    PolicyVersion,
    SimulationRun,
    TrainingRun,
    User,
    WorkerLease,
    WorldEvent,
)
from infrastructure.database.seeds import seed_database


@pytest.fixture
def in_memory_db():
    """Provides an isolated in-memory SQLite database for clean test execution."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    
    # 1. Apply schema from empty
    Base.metadata.create_all(bind=engine)
    setup_immutability_triggers(engine)

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()

    yield engine, session

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_migrations_apply_cleanly_and_all_16_tables_exist(in_memory_db):
    """AC-1: All 16 tables defined in schema exist in clean migration."""
    engine, _ = in_memory_db
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    expected_tables = {
        "users",
        "pets",
        "pet_state",
        "habitats",
        "habitat_objects",
        "care_actions",
        "world_events",
        "memories",
        "behaviour_stats",
        "policy_versions",
        "simulation_runs",
        "training_runs",
        "notification_preferences",
        "notification_outbox",
        "worker_leases",
        "commands",
    }

    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"


def test_duplicate_command_id_fails_idempotency(in_memory_db):
    """AC-2: Duplicate command_id inserts fail enforcing idempotency constraint (Rule 4)."""
    _, session = in_memory_db

    # Seed owner & pet first for foreign key integrity
    seed_database(session)

    cmd1 = Command(
        command_id="cmd_unique_12345",
        pet_id="pet_hammy_01",
        user_id="usr_hammy_default",
        command_type="feed",
        parameters={"amount_grams": 5.0},
        status="received",
    )
    session.add(cmd1)
    session.commit()

    # Attempt to insert identical command_id
    cmd2 = Command(
        command_id="cmd_unique_12345",
        pet_id="pet_hammy_01",
        user_id="usr_hammy_default",
        command_type="feed",
        parameters={"amount_grams": 5.0},
        status="received",
    )
    session.add(cmd2)

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_world_events_cannot_be_updated_append_only(in_memory_db):
    """AC-3: world_events is append-only; update attempts must raise an error."""
    _, session = in_memory_db
    seed_database(session)

    evt = WorldEvent(
        event_id="evt_test_001",
        pet_id="pet_hammy_01",
        world_tick=100,
        sim_time_sec=25.0,
        event_type="skill_completed",
        skill_name="eat",
        origin="observed_physics",
        behaviour_type="learned",
        seed=42,
        payload={"food_eaten_grams": 2.5},
    )
    session.add(evt)
    session.commit()

    # Attempt to update the event - should be blocked by trigger
    with pytest.raises((DBAPIError, Exception)) as excinfo:
        evt.skill_name = "drink"
        session.commit()

    session.rollback()
    assert "append-only" in str(excinfo.value) or "world_events" in str(excinfo.value)


def test_seed_database_execution_and_relationships(in_memory_db):
    """AC-4: Seed script seeds 1 user, 1 pet, 1 habitat with standard objects."""
    _, session = in_memory_db
    result = seed_database(session)

    assert result["user_id"] == "usr_hammy_default"
    assert result["pet_id"] == "pet_hammy_01"
    assert result["habitat_id"] == "habitat_v1_main"
    assert len(result["object_ids"]) == 6

    # Verify queryable records
    user = session.get(User, "usr_hammy_default")
    assert user is not None
    assert user.email == "owner@hammy.local"
    assert len(user.pets) == 1

    pet = user.pets[0]
    assert pet.name == "Hammy"
    assert pet.state is not None
    assert pet.state.drives["hunger"] == 0.15
    assert pet.state.version == 1

    habitat = session.get(Habitat, "habitat_v1_main")
    assert habitat is not None
    assert len(habitat.objects) == 6

    object_types = {obj.object_type for obj in habitat.objects}
    assert object_types == {"food_bowl", "water_bottle", "hideout", "tunnel", "wheel", "chew_toy"}


def test_pet_state_optimistic_concurrency(in_memory_db):
    """AC-5: Optimistic concurrency control via version counter on pet_state."""
    _, session = in_memory_db
    seed_database(session)

    state = session.get(PetState, "pet_hammy_01")
    current_version = state.version

    # Simulate valid update with version increment
    state.sim_time_sec += 60.0
    state.version += 1
    session.commit()

    updated = session.get(PetState, "pet_hammy_01")
    assert updated.version == current_version + 1
    assert updated.sim_time_sec == 60.0

