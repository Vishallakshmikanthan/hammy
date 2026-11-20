"""
HAMMY — Step 6 Acceptance Test Suite (`tests/test_step6_shelf_commands.py`).
Tests all Step 6 & OVERRIDE requirements:
  1. Manifest validation (`assets/manifest.json` has 30 items across 5 categories; all foods are `hamster_safe=True`).
  2. Default clean cage policy (`reset_clean_cage` leaves ONLY bedding + 1 basic water source `prop_bottle_main`).
  3. `offer_food`: valid hamster-safe food succeeds, duplicate `command_id` is idempotent replay,
     invalid/non-food item is rejected, `consume_food` decreases server quantity and increases `cheek_pouch_fill`.
  4. `refill_water` & `consume_water`: refills water level up to 1.0, duplicate `command_id` is idempotent,
     `consume_water` decreases server water level.
  5. `equip_costume` & `unequip_costume`: equips to `head_slot`, `neck_slot`, `back_slot` (one item per slot),
     duplicate `command_id` is idempotent, unequip removes slot cleanly.
  6. `place_prop`, `move_prop`, `remove_prop`: validates cage bounds (rejects out-of-bounds placement),
     rejects overlapping placement, supports rotation/move/remove, logs world events for every action,
     and persists layout across reloads (`GET /api/v1/pets/{pet_id}/shelves/state`).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from infrastructure.database.connection import Base, setup_immutability_triggers
from infrastructure.database.models import WorldEvent
from infrastructure.database.seeds import seed_database
from services.api.auth import create_access_token, get_db
from services.api.main import app
from services.api.rate_limit import global_rate_limiter


@pytest.fixture
def client_and_session():
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
def headers():
    token = create_access_token(user_id="usr_hammy_default", email="owner@hammy.local")
    return {"Authorization": f"Bearer {token}"}


def test_manifest_endpoint_and_hamster_safety(client_and_session):
    client, _ = client_and_session
    res = client.get("/api/v1/assets/manifest")
    assert res.status_code == 200
    data = res.json()
    assert data["total_assets"] == 30
    items = data["items"]
    assert len(items) == 30

    categories = {it["category"] for it in items}
    assert categories == {"food", "water", "costume", "prop", "decor"}

    foods = [it for it in items if it["category"] == "food"]
    assert len(foods) == 7
    for f in foods:
        assert f["hamster_safe"] is True
        assert f["pivot"] == "pickup_pivot"

    costumes = [it for it in items if it["category"] == "costume"]
    assert len(costumes) == 7
    slots = {c["attachment_slot"] for c in costumes}
    assert slots == {"head_slot", "neck_slot", "back_slot"}


def test_clean_default_cage_and_persistence(client_and_session, headers):
    client, _ = client_and_session

    # Reset cage to clean minimal default state
    res = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/reset_clean_cage",
        headers=headers,
        json={"command_id": "cmd_reset_clean_001"},
    )
    assert res.status_code == 200
    layout = res.json()["layout"]

    # Verify nothing in the cage except the 1 basic water source
    assert layout["equipped_costumes"] == {}
    assert layout["offered_foods"] == []
    assert layout["placed_items"] == []
    assert len(layout["water_sources"]) == 1
    assert layout["water_sources"][0]["item_id"] == "water_bottle"


def test_offer_food_idempotency_and_server_authoritative_eat(client_and_session, headers):
    client, _ = client_and_session
    client.post(
        "/api/v1/pets/pet_hammy_01/shelves/reset_clean_cage",
        headers=headers,
        json={"command_id": "cmd_reset_food_test"},
    )

    # 1. Offer 2 carrot pieces
    cmd_id = "cmd_offer_carrot_001"
    r1 = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/offer_food",
        headers=headers,
        json={"command_id": cmd_id, "item_id": "food_carrot_piece", "quantity": 2},
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["idempotent_replay"] is False
    assert len(d1["layout"]["offered_foods"]) == 1
    assert d1["layout"]["offered_foods"][0]["quantity"] == 2
    food_obj_id = d1["result"]["object_id"]

    # 2. Duplicate delivery with same command_id must NOT add more food
    r2 = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/offer_food",
        headers=headers,
        json={"command_id": cmd_id, "item_id": "food_carrot_piece", "quantity": 2},
    )
    assert r2.status_code == 200
    assert r2.json()["idempotent_replay"] is True
    assert len(r2.json()["layout"]["offered_foods"]) == 1
    assert r2.json()["layout"]["offered_foods"][0]["quantity"] == 2

    # 3. Invalid food item rejected
    r_bad = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/offer_food",
        headers=headers,
        json={"command_id": "cmd_offer_bad_01", "item_id": "prop_wheel", "quantity": 1},
    )
    assert r_bad.status_code == 400

    # 4. Server-authoritative eating interaction decreases quantity (2 -> 1) and increases cheek_pouch_fill
    r_eat1 = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/consume_food",
        headers=headers,
        json={"command_id": "cmd_consume_carrot_01", "object_id": food_obj_id},
    )
    assert r_eat1.status_code == 200
    eat_data = r_eat1.json()
    assert eat_data["result"]["remaining_quantity"] == 1
    assert eat_data["layout"]["cheek_pouch_fill"] > 0.0
    assert eat_data["layout"]["offered_foods"][0]["quantity"] == 1

    # 5. Eating second piece removes offered_food item completely
    r_eat2 = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/consume_food",
        headers=headers,
        json={"command_id": "cmd_consume_carrot_02", "object_id": food_obj_id},
    )
    assert r_eat2.status_code == 200
    assert r_eat2.json()["layout"]["offered_foods"] == []


def test_refill_water_and_drink_idempotency(client_and_session, headers):
    client, _ = client_and_session
    client.post(
        "/api/v1/pets/pet_hammy_01/shelves/reset_clean_cage",
        headers=headers,
        json={"command_id": "cmd_reset_water_test"},
    )

    # 1. Hamster drinks water -> water level drops below 0.75
    r_drink = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/consume_water",
        headers=headers,
        json={"command_id": "cmd_drink_water_01"},
    )
    assert r_drink.status_code == 200
    lvl_after_drink = r_drink.json()["layout"]["water_level"]
    assert lvl_after_drink < 0.75

    # 2. User refills water -> water level rises to 1.0
    r_refill = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/refill_water",
        headers=headers,
        json={"command_id": "cmd_refill_water_01", "amount_ml": 100.0},
    )
    assert r_refill.status_code == 200
    assert r_refill.json()["idempotent_replay"] is False
    assert r_refill.json()["layout"]["water_level"] == 1.0

    # 3. Duplicate refill command_id is idempotent
    r_refill_dup = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/refill_water",
        headers=headers,
        json={"command_id": "cmd_refill_water_01", "amount_ml": 100.0},
    )
    assert r_refill_dup.status_code == 200
    assert r_refill_dup.json()["idempotent_replay"] is True


def test_equip_and_unequip_costume_slots(client_and_session, headers):
    client, _ = client_and_session
    client.post(
        "/api/v1/pets/pet_hammy_01/shelves/reset_clean_cage",
        headers=headers,
        json={"command_id": "cmd_reset_costume_test"},
    )

    # 1. Equip party hat to head_slot
    r1 = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/equip_costume",
        headers=headers,
        json={"command_id": "cmd_equip_hat_01", "item_id": "costume_party_hat"},
    )
    assert r1.status_code == 200
    assert r1.json()["layout"]["equipped_costumes"]["head_slot"]["item_id"] == "costume_party_hat"

    # 2. Duplicate delivery is idempotent
    r1_dup = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/equip_costume",
        headers=headers,
        json={"command_id": "cmd_equip_hat_01", "item_id": "costume_party_hat"},
    )
    assert r1_dup.status_code == 200
    assert r1_dup.json()["idempotent_replay"] is True

    # 3. Equipping top hat replaces party hat in head_slot (one item per slot)
    r2 = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/equip_costume",
        headers=headers,
        json={"command_id": "cmd_equip_tophat_02", "item_id": "costume_top_hat"},
    )
    assert r2.status_code == 200
    assert r2.json()["layout"]["equipped_costumes"]["head_slot"]["item_id"] == "costume_top_hat"

    # 4. Equip bow tie to neck_slot simultaneously
    r3 = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/equip_costume",
        headers=headers,
        json={"command_id": "cmd_equip_bowtie_03", "item_id": "costume_bow_tie"},
    )
    assert r3.status_code == 200
    eq = r3.json()["layout"]["equipped_costumes"]
    assert eq["head_slot"]["item_id"] == "costume_top_hat"
    assert eq["neck_slot"]["item_id"] == "costume_bow_tie"

    # 5. Unequip head_slot
    r_un = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/unequip_costume",
        headers=headers,
        json={"command_id": "cmd_unequip_head_04", "slot": "head_slot"},
    )
    assert r_un.status_code == 200
    assert "head_slot" not in r_un.json()["layout"]["equipped_costumes"]
    assert "neck_slot" in r_un.json()["layout"]["equipped_costumes"]


def test_place_move_remove_prop_bounds_overlap_and_events(client_and_session, headers):
    client, Session = client_and_session
    client.post(
        "/api/v1/pets/pet_hammy_01/shelves/reset_clean_cage",
        headers=headers,
        json={"command_id": "cmd_reset_prop_test"},
    )

    # 1. Place straight tunnel inside bounds (in open floor area clear of default wheel/logs/home/bowl)
    r_place = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/place_prop",
        headers=headers,
        json={
            "command_id": "cmd_place_tunnel_01",
            "item_id": "prop_tunnel_straight",
            "pose_xyz_m": [-0.22, -0.14, 0.165],
            "rotation_y_rad": 0.5,
        },
    )
    assert r_place.status_code == 200
    obj_id = r_place.json()["result"]["object_id"]
    assert len(r_place.json()["layout"]["placed_items"]) == 1

    # 2. Duplicate command_id does not place a second tunnel
    r_place_dup = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/place_prop",
        headers=headers,
        json={
            "command_id": "cmd_place_tunnel_01",
            "item_id": "prop_tunnel_straight",
            "pose_xyz_m": [-0.22, -0.14, 0.165],
            "rotation_y_rad": 0.5,
        },
    )
    assert r_place_dup.status_code == 200
    assert r_place_dup.json()["idempotent_replay"] is True
    assert len(r_place_dup.json()["layout"]["placed_items"]) == 1

    # 3. Out-of-bounds placement is rejected (400)
    r_oob = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/place_prop",
        headers=headers,
        json={
            "command_id": "cmd_place_oob_02",
            "item_id": "prop_hideout",
            "pose_xyz_m": [0.95, 0.0, 0.165],
            "rotation_y_rad": 0.0,
        },
    )
    assert r_oob.status_code == 400
    assert "outside cage bounds" in r_oob.json()["detail"]

    # 4. Overlapping placement at exact same spot is rejected (400)
    r_overlap = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/place_prop",
        headers=headers,
        json={
            "command_id": "cmd_place_overlap_03",
            "item_id": "prop_hideout",
            "pose_xyz_m": [-0.22, -0.14, 0.165],
            "rotation_y_rad": 0.0,
        },
    )
    assert r_overlap.status_code == 400
    assert "overlaps existing item" in r_overlap.json()["detail"]

    # 5. Move placed tunnel to a new valid position
    r_move = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/move_prop",
        headers=headers,
        json={
            "command_id": "cmd_move_tunnel_04",
            "object_id": obj_id,
            "pose_xyz_m": [-0.04, 0.14, 0.165],
            "rotation_y_rad": 1.2,
        },
    )
    assert r_move.status_code == 200
    assert r_move.json()["layout"]["placed_items"][0]["pose_xyz_m"] == [-0.04, 0.14, 0.165]

    # 6. Reload state (GET /shelves/state) -> persists layout
    r_state = client.get("/api/v1/pets/pet_hammy_01/shelves/state", headers=headers)
    assert r_state.status_code == 200
    assert len(r_state.json()["placed_items"]) == 1
    assert r_state.json()["placed_items"][0]["object_id"] == obj_id

    # 7. Remove placed tunnel back to shelf
    r_rem = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/remove_prop",
        headers=headers,
        json={"command_id": "cmd_remove_tunnel_05", "object_id": obj_id},
    )
    assert r_rem.status_code == 200
    assert r_rem.json()["layout"]["placed_items"] == []

    # 8. Verify world_events logged every action
    with Session() as session:
        evts = session.query(WorldEvent).filter_by(pet_id="pet_hammy_01").all()
        evt_types = {e.event_type for e in evts}
        assert "prop_placed" in evt_types
        assert "prop_moved" in evt_types
        assert "prop_removed" in evt_types


def test_functional_food_bowl_drop_depletion_and_refill(client_and_session, headers):
    client, _ = client_and_session
    r_reset = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/reset_clean_cage",
        headers=headers,
        json={"command_id": "cmd_reset_bowl_func_01"},
    )
    assert r_reset.status_code == 200
    assert r_reset.json()["layout"]["food_level"] == 1.0

    # 1. Autonomous bowl eating drops food_level even when no extra offered_food item exists
    r_eat_bowl = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/consume_food",
        headers=headers,
        json={"command_id": "cmd_consume_bowl_kibble_01"},
    )
    assert r_eat_bowl.status_code == 200
    lvl_after_eat = r_eat_bowl.json()["layout"]["food_level"]
    assert lvl_after_eat < 1.0

    # 2. Offering food lands directly inside the food bowl (~[0.28, -0.11]), never random cage corners
    r_offer = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/offer_food",
        headers=headers,
        json={"command_id": "cmd_offer_in_bowl_01", "item_id": "food_blueberry", "quantity": 1},
    )
    assert r_offer.status_code == 200
    offered_pose = r_offer.json()["result"]["pose_xyz_m"]
    assert abs(offered_pose[0] - 0.28) <= 0.02
    assert abs(offered_pose[1] - (-0.11)) <= 0.02

    # 3. Eating offered food also drops bowl food_level
    r_eat_offered = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/consume_food",
        headers=headers,
        json={"command_id": "cmd_consume_offered_01", "object_id": r_offer.json()["result"]["object_id"]},
    )
    assert r_eat_offered.status_code == 200
    assert r_eat_offered.json()["layout"]["food_level"] < 1.0

    # 4. Refill food bowl restores food_level to 1.0
    r_refill = client.post(
        "/api/v1/pets/pet_hammy_01/shelves/refill_food",
        headers=headers,
        json={"command_id": "cmd_refill_food_01", "amount_grams": 25.0},
    )
    assert r_refill.status_code == 200
    assert r_refill.json()["layout"]["food_level"] == 1.0
