"""
HAMMY — P2.3 Acceptance Test Suite (`tests/test_p2_3.py`).
Tests all P2.3 criteria:
  1. Acceptance Criterion: Feeding twice with the same command_id adds food once.
  2. Authentication and per-pet authorisation (401 on missing token, 403 on other user's pet).
  3. All blueprint endpoints (pet, state, events, memories, habitat, care, simulation, health).
  4. Command parameter validation (bounds, invalid types).
  5. WebSocket state streaming.
  6. Rate limiting enforcement.
  7. OpenAPI documentation generation.
"""

from __future__ import annotations

import datetime
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from infrastructure.database.connection import Base, setup_immutability_triggers
from infrastructure.database.models import Habitat, HabitatObject, Pet, PetState, User
from infrastructure.database.seeds import seed_database
from services.api.auth import create_access_token, get_db
from services.api.main import app
from services.api.rate_limit import RateLimiter, global_rate_limiter, rate_limit_dependency


@pytest.fixture
def client_with_db():
    """Provides FastAPI TestClient wired to an isolated in-memory test database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    setup_immutability_triggers(engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed initial user, pet, and habitat
    with TestingSessionLocal() as session:
        seed_database(session)

        # Seed a second user and pet to test multi-tenant authorization
        user_intruder = User(
            id="usr_intruder_02",
            email="intruder@hammy.local",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        pet_intruder = Pet(
            id="pet_other_99",
            user_id="usr_intruder_02",
            name="Shadow",
            species="roborovski_hamster",
            birth_date=datetime.datetime.now(datetime.timezone.utc),
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        session.add(user_intruder)
        session.add(pet_intruder)
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
def owner_headers():
    token = create_access_token(user_id="usr_hammy_default", email="owner@hammy.local")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def intruder_headers():
    token = create_access_token(user_id="usr_intruder_02", email="intruder@hammy.local")
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. CORE ACCEPTANCE CRITERIA: IDEMPOTENT FEEDING
# ==============================================================================
def test_feeding_twice_with_same_command_id_adds_food_once(client_with_db, owner_headers):
    """
    CRITICAL ACCEPTANCE CRITERION:
    Feeding twice with the same command_id adds food once.
    """
    client, Session = client_with_db

    # 1. Inspect initial bowl food level
    with Session() as session:
        bowl = session.get(HabitatObject, "prop_bowl_main")
        # Ensure bowl starts at 10% capacity
        bowl.resource_state = {"food_level": 0.10, "capacity_grams": 25.0}
        session.commit()
        init_level = bowl.resource_state["food_level"]

    # 2. First feed request
    command_id = "cmd_feed_idempotent_test_001"
    res1 = client.post(
        "/api/v1/pets/pet_hammy_01/care/feed",
        headers=owner_headers,
        json={"command_id": command_id, "amount_grams": 5.0},
    )
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1["idempotent_replay"] is False
    level_after_first = data1["result"]["new_food_level"]
    assert level_after_first > init_level  # (2.5g + 5.0g) / 25.0g = 0.30

    with Session() as session:
        bowl_after_1 = session.get(HabitatObject, "prop_bowl_main")
        assert bowl_after_1.resource_state["food_level"] == level_after_first

    # 3. Second feed request with the EXACT SAME command_id
    res2 = client.post(
        "/api/v1/pets/pet_hammy_01/care/feed",
        headers=owner_headers,
        json={"command_id": command_id, "amount_grams": 5.0},
    )
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert data2["idempotent_replay"] is True

    # 4. CRITICAL VERIFICATION: Food level is identical; food was NOT added a second time!
    with Session() as session:
        bowl_after_2 = session.get(HabitatObject, "prop_bowl_main")
        assert bowl_after_2.resource_state["food_level"] == level_after_first


# ==============================================================================
# 2. AUTHENTICATION & PER-PET AUTHORISATION
# ==============================================================================
def test_unauthorised_access_without_token(client_with_db):
    client, _ = client_with_db
    res = client.get("/api/v1/pets/pet_hammy_01")
    assert res.status_code == 401
    assert "Authorization" in res.json()["detail"]


def test_unauthorised_access_other_users_pet(client_with_db, intruder_headers):
    client, _ = client_with_db
    # Intruder tries to access pet_hammy_01 (owned by usr_hammy_default)
    res = client.get("/api/v1/pets/pet_hammy_01", headers=intruder_headers)
    assert res.status_code == 403
    assert "Access forbidden" in res.json()["detail"]


def test_access_nonexistent_pet_returns_404(client_with_db, owner_headers):
    client, _ = client_with_db
    res = client.get("/api/v1/pets/pet_does_not_exist_999", headers=owner_headers)
    assert res.status_code == 404


# ==============================================================================
# 3. BLUEPRINT ENDPOINTS
# ==============================================================================
def test_get_pet_details_and_state(client_with_db, owner_headers):
    client, _ = client_with_db

    # Pet details
    res_pet = client.get("/api/v1/pets/pet_hammy_01", headers=owner_headers)
    assert res_pet.status_code == 200
    assert res_pet.json()["name"] == "Hammy"
    assert res_pet.json()["species"] == "syrian_hamster"

    # State snapshot
    res_state = client.get("/api/v1/pets/pet_hammy_01/state", headers=owner_headers)
    assert res_state.status_code == 200
    state = res_state.json()
    assert "drives" in state
    assert "hunger" in state["drives"]
    assert "position_xyz" in state
    assert state["is_paused"] is False


def test_get_events_and_memories(client_with_db, owner_headers):
    client, _ = client_with_db

    res_events = client.get("/api/v1/pets/pet_hammy_01/events", headers=owner_headers)
    assert res_events.status_code == 200
    assert isinstance(res_events.json(), list)

    res_mem = client.get("/api/v1/pets/pet_hammy_01/memories", headers=owner_headers)
    assert res_mem.status_code == 200
    assert isinstance(res_mem.json(), list)


def test_get_habitat_and_props(client_with_db, owner_headers):
    client, _ = client_with_db

    res_hab = client.get("/api/v1/pets/pet_hammy_01/habitat", headers=owner_headers)
    assert res_hab.status_code == 200
    assert "dimensions_xyz" in res_hab.json()
    assert "floor_bounds" in res_hab.json()

    res_objs = client.get("/api/v1/pets/pet_hammy_01/habitat/objects", headers=owner_headers)
    assert res_objs.status_code == 200
    objects = res_objs.json()
    assert len(objects) == 6
    types = {o["object_type"] for o in objects}
    assert "food_bowl" in types
    assert "water_bottle" in types


def test_move_habitat_object_and_bounds_validation(client_with_db, owner_headers):
    client, _ = client_with_db

    # Valid move
    res_move = client.post(
        "/api/v1/pets/pet_hammy_01/habitat/objects",
        headers=owner_headers,
        json={
            "command_id": "cmd_move_bowl_001",
            "object_id": "prop_bowl_main",
            "new_pose_xyz_m": [0.20, -0.10, 0.165],
        },
    )
    assert res_move.status_code == 200
    assert res_move.json()["result"]["new_pose_xyz_m"] == [0.20, -0.10, 0.165]

    # Out of bounds move (x = 2.0m outside 1.0m cage bounds [-0.5, 0.5])
    res_oob = client.post(
        "/api/v1/pets/pet_hammy_01/habitat/objects",
        headers=owner_headers,
        json={
            "command_id": "cmd_move_bowl_oob",
            "object_id": "prop_bowl_main",
            "new_pose_xyz_m": [2.0, 0.0, 0.165],
        },
    )
    assert res_oob.status_code == 400
    assert "outside habitat bounds" in res_oob.json()["detail"]


def test_water_and_enrichment_care_actions(client_with_db, owner_headers):
    client, _ = client_with_db

    # Water
    res_water = client.post(
        "/api/v1/pets/pet_hammy_01/care/water",
        headers=owner_headers,
        json={"command_id": "cmd_water_001", "amount_ml": 25.0},
    )
    assert res_water.status_code == 200
    assert "Refilled" in res_water.json()["message"]

    # Valid Enrichment
    res_enrich = client.post(
        "/api/v1/pets/pet_hammy_01/enrichment",
        headers=owner_headers,
        json={
            "command_id": "cmd_enrich_001",
            "enrichment_type": "cardboard_tube",
            "parameters": {"color": "brown"},
        },
    )
    assert res_enrich.status_code == 200
    assert "cardboard_tube" in res_enrich.json()["message"]

    # Invalid Enrichment type
    res_invalid_enrich = client.post(
        "/api/v1/pets/pet_hammy_01/enrichment",
        headers=owner_headers,
        json={"command_id": "cmd_enrich_bad", "enrichment_type": "laser_pointer"},
    )
    assert res_invalid_enrich.status_code == 400
    assert "Invalid enrichment_type" in res_invalid_enrich.json()["detail"]


def test_simulation_pause_and_resume(client_with_db, owner_headers):
    client, _ = client_with_db

    # Pause
    res_pause = client.post(
        "/api/v1/pets/pet_hammy_01/simulation/pause",
        headers=owner_headers,
        json={"command_id": "cmd_pause_001"},
    )
    assert res_pause.status_code == 200
    assert res_pause.json()["result"]["is_paused"] is True

    # Verify state reflects pause
    res_state = client.get("/api/v1/pets/pet_hammy_01/state", headers=owner_headers)
    assert res_state.json()["is_paused"] is True

    # Resume
    res_resume = client.post(
        "/api/v1/pets/pet_hammy_01/simulation/resume",
        headers=owner_headers,
        json={"command_id": "cmd_resume_001"},
    )
    assert res_resume.status_code == 200
    assert res_resume.json()["result"]["is_paused"] is False

    res_state2 = client.get("/api/v1/pets/pet_hammy_01/state", headers=owner_headers)
    assert res_state2.json()["is_paused"] is False


def test_system_health(client_with_db):
    client, _ = client_with_db
    res = client.get("/api/v1/system/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


# ==============================================================================
# 4. WEBSOCKET REAL-TIME STREAMING
# ==============================================================================
def test_websocket_streaming_initial_snapshot(client_with_db):
    client, _ = client_with_db
    token = create_access_token("usr_hammy_default")

    # Connect to WebSocket with token query param
    with client.websocket_connect(f"/api/v1/pets/pet_hammy_01/ws?token={token}") as ws:
        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot"
        assert snapshot["pet_id"] == "pet_hammy_01"
        assert "drives" in snapshot

        # Ping-pong test
        ws.send_text("ping")
        reply = ws.receive_text()
        assert reply == "pong"


def test_websocket_rejects_unauthenticated(client_with_db):
    client, _ = client_with_db
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/pets/pet_hammy_01/ws"):
            pass


# ==============================================================================
# 5. RATE LIMITING & OPENAPI SCHEMA
# ==============================================================================
def test_rate_limiting_enforcement(client_with_db, owner_headers):
    client, _ = client_with_db
    # Create strict rate limiter: 3 requests per minute
    test_limiter = RateLimiter(requests_per_minute=3)

    def override_rate_limit(request: Request):
        test_limiter.check(request)

    app.dependency_overrides[rate_limit_dependency] = override_rate_limit

    try:
        # First 3 requests succeed
        for _ in range(3):
            r = client.get("/api/v1/pets/pet_hammy_01/state", headers=owner_headers)
            assert r.status_code == 200

        # 4th request triggers 429
        r4 = client.get("/api/v1/pets/pet_hammy_01/state", headers=owner_headers)
        assert r4.status_code == 429
        assert "Rate limit exceeded" in r4.json()["detail"]
        assert "Retry-After" in r4.headers
    finally:
        app.dependency_overrides.pop(rate_limit_dependency, None)


def test_openapi_documentation(client_with_db):
    client, _ = client_with_db
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    assert "paths" in schema
    assert "/api/v1/pets/{pet_id}" in schema["paths"]
    assert "/api/v1/pets/{pet_id}/care/feed" in schema["paths"]
    assert "/api/v1/pets/{pet_id}/care/water" in schema["paths"]
    assert "/api/v1/pets/{pet_id}/simulation/pause" in schema["paths"]
    assert "/api/v1/system/health" in schema["paths"]
