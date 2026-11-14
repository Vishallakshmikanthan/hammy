"""
HAMMY — P2.5 Acceptance Test Suite (`tests/test_p2_5.py`).
Tests all P2.5 Minimal Brain Observatory backend requirements:
  1. Authoritative REST API hydration:
     - Pet record with morphology_version.
     - PetState with schema_version (2.0.0), environment_version, drives, sim_time, real_time_scale, is_paused.
     - WorldEvents feed returning last 50 events with required origin & behaviour_type badges.
  2. WebSocket real-time snapshot emission & reconnection restoration:
     - Initial connect sends snapshot.
     - Disconnect & reconnect restores the latest updated state snapshot.
  3. Authoritative server control:
     - Pause & resume simulation endpoints update database state.
     - Zero client-side invented state: every field links directly to stored DB records.
"""

from __future__ import annotations

import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from infrastructure.database.connection import Base, setup_immutability_triggers
from infrastructure.database.models import Pet, PetState, User, WorldEvent
from infrastructure.database.seeds import seed_database
from services.api.auth import create_access_token, get_db
from services.api.main import app
from services.api.rate_limit import global_rate_limiter


@pytest.fixture
def observatory_client():
    """Provides isolated FastAPI TestClient with seeded DB for Observatory testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    setup_immutability_triggers(engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as session:
        seed_database(session)

        # Seed additional varied events to test the 50-limit events feed and origin/behaviour tags
        for i in range(1, 55):
            origin = "observed_physics" if i % 3 == 0 else ("sampled_from_skill_model" if i % 3 == 1 else "rule")
            behaviour = "learned" if i % 3 == 0 else ("scripted" if i % 3 == 1 else "rule")
            ev = WorldEvent(
                event_id=f"evt_obs_{i:03d}",
                pet_id="pet_hammy_01",
                world_tick=100 + i,
                sim_time_sec=1000.0 + i * 5.0,
                event_type="test_step" if i % 2 == 0 else "forage_decision",
                skill_name="forage" if i % 2 == 1 else None,
                origin=origin,
                behaviour_type=behaviour,
                seed=42 + i,
                payload={"step": i, "value": i * 0.1},
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(ev)
        session.commit()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    global_rate_limiter.reset()

    with TestClient(app) as client:
        yield client, TestingSessionLocal

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def auth_headers():
    token = create_access_token(user_id="usr_hammy_default", email="owner@hammy.local")
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. REST HYDRATION CONTRACTS FOR OBSERVATORY
# ==============================================================================
def test_observatory_rest_hydration_contracts(observatory_client, auth_headers):
    client, _ = observatory_client

    # 1. Pet metadata
    res_pet = client.get("/api/v1/pets/pet_hammy_01", headers=auth_headers)
    assert res_pet.status_code == 200
    pet_data = res_pet.json()
    assert pet_data["id"] == "pet_hammy_01"
    assert pet_data["morphology_version"] == "simple_agent_v1"

    # 2. State metadata (active skill, policy context, drives, banner data)
    res_state = client.get("/api/v1/pets/pet_hammy_01/state", headers=auth_headers)
    assert res_state.status_code == 200
    state_data = res_state.json()
    assert state_data["schema_version"] == "2.0.0"
    assert state_data["environment_version"] in {"habitat_v1", "cage_v1"}
    assert state_data["real_time_scale"] == 1.0
    assert "is_paused" in state_data
    assert "sim_time_sec" in state_data
    assert "simulated_age_days" in state_data

    # Verify homeostatic drives
    drives = state_data["drives"]
    for drive in ["hunger", "thirst", "energy", "comfort", "stress", "curiosity", "circadian_phase"]:
        assert drive in drives
        assert isinstance(drives[drive], (int, float))

    # 3. Events feed with limit 50 and origin & behaviour badges
    res_events = client.get("/api/v1/pets/pet_hammy_01/events?limit=50", headers=auth_headers)
    assert res_events.status_code == 200
    events = res_events.json()
    assert len(events) == 50  # Cap to last 50 events

    for ev in events:
        assert ev["origin"] in {"observed_physics", "sampled_from_skill_model", "rule"}
        assert ev["behaviour_type"] in {"learned", "scripted", "rule"}
        assert ev["pet_id"] == "pet_hammy_01"
        assert "event_id" in ev


# ==============================================================================
# 2. SIMULATION PAUSE & RESUME CONTROLS (BANNER)
# ==============================================================================
def test_simulation_pause_resume_reflects_in_observatory(observatory_client, auth_headers):
    client, _ = observatory_client

    # Pause simulation
    pause_res = client.post(
        "/api/v1/pets/pet_hammy_01/simulation/pause",
        headers=auth_headers,
        json={"command_id": "cmd_obs_pause_1"},
    )
    assert pause_res.status_code == 200
    assert pause_res.json()["result"]["is_paused"] is True

    # Verify state reflects pause
    state_res = client.get("/api/v1/pets/pet_hammy_01/state", headers=auth_headers)
    assert state_res.json()["is_paused"] is True

    # Resume simulation
    resume_res = client.post(
        "/api/v1/pets/pet_hammy_01/simulation/resume",
        headers=auth_headers,
        json={"command_id": "cmd_obs_resume_1"},
    )
    assert resume_res.status_code == 200
    assert resume_res.json()["result"]["is_paused"] is False

    state_res2 = client.get("/api/v1/pets/pet_hammy_01/state", headers=auth_headers)
    assert state_res2.json()["is_paused"] is False


# ==============================================================================
# 3. WEBSOCKET RECONNECTION & STATE RESTORATION
# ==============================================================================
def test_websocket_reconnection_restores_latest_state(observatory_client):
    client, session_factory = observatory_client
    token = create_access_token("usr_hammy_default")

    # 1. Initial Connection
    with client.websocket_connect(f"/api/v1/pets/pet_hammy_01/ws?token={token}") as ws1:
        snapshot1 = ws1.receive_json()
        assert snapshot1["type"] == "snapshot"
        assert snapshot1["pet_id"] == "pet_hammy_01"
        assert snapshot1["is_paused"] is False

    # 2. Disconnect & mutate authoritative state on server
    with session_factory() as session:
        pet_state = session.query(PetState).filter_by(pet_id="pet_hammy_01").one()
        pet_state.version += 10
        pet_state.sim_time_sec += 500.0
        pet_state.is_paused = True
        pet_state.drives = {
            **pet_state.drives,
            "hunger": 0.88,
            "stress": 0.65,
        }
        session.commit()

    # 3. Reconnect WebSocket: must immediately receive updated state snapshot
    with client.websocket_connect(f"/api/v1/pets/pet_hammy_01/ws?token={token}") as ws2:
        snapshot2 = ws2.receive_json()
        assert snapshot2["type"] == "snapshot"
        assert snapshot2["pet_id"] == "pet_hammy_01"
        assert snapshot2["version"] == snapshot1["version"] + 10
        assert snapshot2["sim_time_sec"] == snapshot1["sim_time_sec"] + 500.0
        assert snapshot2["is_paused"] is True
        assert snapshot2["drives"]["hunger"] == 0.88
        assert snapshot2["drives"]["stress"] == 0.65
