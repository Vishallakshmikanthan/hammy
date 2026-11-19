"""Stage 5 acceptance tests: MuJoCo + ONNX TrajectoryClipV1 web bundle & FastAPI bridge."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from contracts.locomotion_contracts import MODEL_VERSION
from contracts.schemas import BehaviourType, EventOrigin, TrajectoryClipV1
from services.api.routes.mujoco_bridge import (
    ParentInteractionRequest,
    get_mujoco_bridge_status,
    get_mujoco_clip,
    post_parent_interaction,
)

WEB_CLIPS_DIR = Path("web/public/assets/mujoco_clips")


def test_mujoco_web_clips_manifest_and_schema():
    manifest_p = WEB_CLIPS_DIR / "manifest.json"
    assert manifest_p.exists(), f"Missing {manifest_p}"
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    clips = manifest["clips"]
    assert len(clips) >= 6

    expected_skills = {
        "forage_bowl",
        "drink_water",
        "enter_tunnel",
        "retreat_to_hideout",
        "cautious_sniff",
        "accept_petting",
    }
    found_skills = {c["skill_id"] for c in clips}
    assert expected_skills.issubset(found_skills)

    for entry in clips:
        clip_p = WEB_CLIPS_DIR / f"{entry['clip_id']}.json"
        assert clip_p.exists()
        clip = TrajectoryClipV1.model_validate_json(clip_p.read_text(encoding="utf-8"))
        assert clip.origin == EventOrigin.OBSERVED_PHYSICS
        assert clip.behaviour_type == BehaviourType.LEARNED
        assert clip.morphology_version == MODEL_VERSION
        assert len(clip.keyframes) >= 20
        assert entry["displacement_m"] > 0.05, f"Clip {entry['skill_id']} had tiny displacement {entry['displacement_m']}"

        for kf in clip.keyframes:
            assert len(kf.joint_angles) == 16
            assert len(kf.foot_contacts) == 4
            assert np.all(np.isfinite(kf.root_pos))
            assert np.all(np.isfinite(kf.root_quat))
            assert np.all(np.isfinite(kf.joint_angles))


def test_mujoco_bridge_api_handlers():
    status = get_mujoco_bridge_status()
    assert status["model_version"] == MODEL_VERSION
    assert len(status["available_clips"]) >= 6

    # Non-forced petting interaction -> returns grounded outcome + matching MuJoCo clip
    resp1 = post_parent_interaction(ParentInteractionRequest(action="gentle_pet"))
    assert resp1["outcome"]["hamster_response"] in ("avoid_and_retreat", "cautious_sniff", "accept_petting")
    assert resp1["clip"] is not None

    # Fetch clip payload via bridge handler
    clip_data = get_mujoco_clip(resp1["clip"]["clip_id"])
    assert clip_data["morphology_version"] == MODEL_VERSION
    assert len(clip_data["keyframes"]) >= 20
