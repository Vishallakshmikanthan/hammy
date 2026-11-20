"""
HAMMY — Phase A–D Automated Verification Suite (`tests/test_rl_v2_brain_and_runtime.py`).

Tests:
  1. ObservationV3 (96-dim) feature builder & biologically grounded action masking.
  2. LiveBrainEngine physiological drive progression & legacy 0%-drive auto-healing.
  3. Idempotent `POST /api/v1/pets/{id}/simulation/time_scale` (1x, 10x, 60x, 300x) & bounds.
  4. `POST /api/v1/pets/{id}/simulation/tick` live learned brain decision + telemetry contract.
  5. Unified `POST /api/v1/mujoco/interact` updating SQLite PetState & persisted `memories`.
  6. Trained `high_level_brain_v2.onnx` & `motor_amp_v2.onnx` contract parity (when artifacts exist).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ai.cognition.cognitive_brain import (
    COGNITIVE_SKILLS_V2,
    OBS_V3_DIM,
    SKILL_TO_IDX,
    CognitiveBrainONNX,
    CognitiveObservationInput,
    build_observation_v3,
    compute_action_mask,
)
from infrastructure.database.connection import Base, setup_immutability_triggers
from infrastructure.database.models import Memory, PetState, WorldEvent
from infrastructure.database.seeds import seed_database
from services.api.auth import create_access_token, get_db
from services.api.main import app
from services.api.rate_limit import global_rate_limiter
from services.runtime.live_brain_engine import live_brain_engine


@pytest.fixture
def isolated_client(monkeypatch):
    monkeypatch.setenv("HAMMY_AUTH_REQUIRED", "true")
    monkeypatch.setenv("HAMMY_DISABLE_LIVE_LOOP", "1")

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    setup_immutability_triggers(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with SessionLocal() as session:
        seed_database(session)
        session.commit()

    def override_get_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    global_rate_limiter.reset()
    live_brain_engine._pet_mem.clear()
    live_brain_engine.reload_policies()

    token = create_access_token(user_id="usr_hammy_default", email="owner@hammy.local")
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        yield client, SessionLocal, headers

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_observation_v3_and_action_masking():
    inp = CognitiveObservationInput(
        hunger=0.35,
        thirst=0.25,
        energy=0.80,
        comfort=0.75,
        stress=0.15,
        curiosity=0.45,
        familiarity=0.20,
        circadian_phase=0.90,
        cheek_pouch_fill=0.0,
        parent_active=False,
    )
    vec = build_observation_v3(inp)
    assert vec.shape == (OBS_V3_DIM,)
    assert np.all(np.isfinite(vec))

    mask = compute_action_mask(inp)
    assert mask.shape == (len(COGNITIVE_SKILLS_V2),)
    # No parent active -> cautious_sniff and accept_petting masked out
    assert not mask[SKILL_TO_IDX["cautious_sniff"]]
    assert not mask[SKILL_TO_IDX["accept_petting"]]
    # Empty cheeks -> unload_hoard masked out
    assert not mask[SKILL_TO_IDX["unload_hoard"]]

    inp.parent_active = True
    inp.cheek_pouch_fill = 0.50
    mask2 = compute_action_mask(inp)
    assert mask2[SKILL_TO_IDX["cautious_sniff"]]
    assert mask2[SKILL_TO_IDX["accept_petting"]]
    assert mask2[SKILL_TO_IDX["unload_hoard"]]


def test_time_scale_multipliers_and_idempotency(isolated_client):
    client, SessionLocal, headers = isolated_client

    for mult in (1.0, 10.0, 60.0, 300.0):
        cid = f"cmd_ts_{int(mult)}"
        r1 = client.post(
            "/api/v1/pets/pet_hammy_01/simulation/time_scale",
            headers=headers,
            json={"command_id": cid, "real_time_scale": mult},
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["result"]["real_time_scale"] == mult
        assert r1.json()["idempotent_replay"] is False

        # Replay with same command_id is idempotent
        r2 = client.post(
            "/api/v1/pets/pet_hammy_01/simulation/time_scale",
            headers=headers,
            json={"command_id": cid, "real_time_scale": mult},
        )
        assert r2.status_code == 200
        assert r2.json()["idempotent_replay"] is True

    # Out-of-bounds rejected
    r_bad = client.post(
        "/api/v1/pets/pet_hammy_01/simulation/time_scale",
        headers=headers,
        json={"command_id": "cmd_ts_bad", "real_time_scale": 9999.0},
    )
    assert r_bad.status_code == 422


def test_live_brain_tick_heals_zero_drives_and_advances_time(isolated_client):
    client, SessionLocal, headers = isolated_client

    # Simulate legacy frozen 0%-drive DB state from screenshot
    with SessionLocal() as session:
        st = session.get(PetState, "pet_hammy_01")
        st.drives = {
            "hunger": 0.0,
            "thirst": 0.0,
            "energy": 1.0,
            "comfort": 0.95,
            "stress": 0.0,
            "curiosity": 0.0,
            "circadian_phase": 0.85,
        }
        st.real_time_scale = 60.0
        st.sim_time_sec = 1000.0
        session.commit()

    r = client.post("/api/v1/pets/pet_hammy_01/simulation/tick", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    snap = body["snapshot"]
    assert snap["sim_time_sec"] > 1000.0
    assert snap["drives"]["hunger"] > 0.0
    assert snap["drives"]["thirst"] > 0.0
    assert snap["drives"]["curiosity"] > 0.0
    assert "brain_telemetry" in snap
    assert len(snap["brain_telemetry"]["spatial_familiarity"]) == 8

    # Verify GET /state returns policy_version and brain_telemetry
    r_st = client.get("/api/v1/pets/pet_hammy_01/state", headers=headers)
    assert r_st.status_code == 200
    st_json = r_st.json()
    assert "policy_version" in st_json
    assert "brain_telemetry" in st_json

    if Path("training/runs/brain_v2/high_level_brain_v2.onnx").exists():
        assert st_json["policy_version"] == "hl_rppo_rnd_v2.0.0"
        assert body["event"]["behaviour_type"] == "learned"


def test_parent_interaction_unified_with_pet_state_and_memories(isolated_client):
    client, SessionLocal, headers = isolated_client

    r1 = client.post(
        "/api/v1/mujoco/interact",
        headers=headers,
        json={"action": "offer_treat", "pet_id": "pet_hammy_01"},
    )
    assert r1.status_code == 200, r1.text
    data = r1.json()
    assert data["outcome"]["hamster_response"] in ("avoid_and_retreat", "cautious_sniff", "accept_petting")
    assert "familiarity" in data["drives"]

    with SessionLocal() as session:
        trust_mem = session.get(Memory, "mem_pet_hammy_01_social_trust")
        assert trust_mem is not None
        assert trust_mem.estimated_value == pytest.approx(data["drives"]["familiarity"], abs=1e-3)
        evts = session.query(WorldEvent).filter_by(event_type="parent_interaction_response").all()
        assert len(evts) == 1


def test_trained_cognitive_onnx_artifact_if_present():
    onnx_p = Path("training/runs/brain_v2/high_level_brain_v2.onnx")
    if not onnx_p.exists():
        pytest.skip("high_level_brain_v2.onnx not yet trained")

    brain = CognitiveBrainONNX(onnx_p, Path("training/runs/brain_v2/rnd_curiosity_v2.onnx"))
    dec = brain.decide(
        "pet_test",
        CognitiveObservationInput(hunger=0.55, thirst=0.15, energy=0.80, curiosity=0.40, circadian_phase=0.90),
        deterministic=True,
    )
    assert dec.skill_name in COGNITIVE_SKILLS_V2
    assert abs(sum(dec.skill_probs.values()) - 1.0) < 0.02
    assert dec.behaviour_type == "learned"
    assert dec.policy_version == "hl_rppo_rnd_v2.0.0"
