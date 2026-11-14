"""P5.1 Trajectory Clips & Determinism Tests."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest
from pydantic import ValidationError

from contracts.schemas import (
    BehaviourType,
    EventOrigin,
    SchemaCompatibilityError,
    TrajectoryClipV1,
)
from services.simulation_worker.clip_generator import generate_episode_clip
from services.simulation_worker.storage import LocalObjectStorage


def test_trajectory_clip_schema_validation():
    clip = generate_episode_clip(
        pet_id="pet_hammy_01",
        skill_id="explore_area",
        seed=42,
        start_sim_time_sec=0.0,
        duration_sec=1.0,
        fps=20.0,
    )
    assert clip.schema_version == "1.0.0"
    assert clip.origin == EventOrigin.OBSERVED_PHYSICS
    assert clip.behaviour_type in {BehaviourType.LEARNED, BehaviourType.SCRIPTED}
    assert len(clip.keyframes) == 20

    with pytest.raises((SchemaCompatibilityError, ValidationError), match="Incompatible trajectory_clip version"):
        TrajectoryClipV1(
            **{**clip.model_dump(), "schema_version": "9.9.9"},
        )


def test_clip_generation_is_deterministic_given_seed():
    c1 = generate_episode_clip(
        pet_id="pet_hammy_01",
        skill_id="explore_area",
        seed=777,
        start_sim_time_sec=12.0,
        duration_sec=2.0,
        fps=20.0,
    )
    c2 = generate_episode_clip(
        pet_id="pet_hammy_01",
        skill_id="explore_area",
        seed=777,
        start_sim_time_sec=12.0,
        duration_sec=2.0,
        fps=20.0,
    )
    assert c1.clip_id == c2.clip_id
    assert len(c1.keyframes) == len(c2.keyframes)
    for k1, k2 in zip(c1.keyframes, c2.keyframes):
        np.testing.assert_allclose(k1.root_pos, k2.root_pos, atol=1e-6)
        np.testing.assert_allclose(k1.root_quat, k2.root_quat, atol=1e-6)
        np.testing.assert_allclose(k1.joint_angles, k2.joint_angles, atol=1e-6)
        assert k1.foot_contacts == k2.foot_contacts


def test_object_storage_upload_list_and_chaining(tmp_path: Path):
    storage = LocalObjectStorage(root=tmp_path)
    c1 = generate_episode_clip(
        pet_id="pet_hammy_01",
        skill_id="explore_area",
        seed=42,
        start_sim_time_sec=0.0,
        duration_sec=2.0,
        fps=20.0,
    )
    last_pos = c1.keyframes[-1].root_pos
    c2 = generate_episode_clip(
        pet_id="pet_hammy_01",
        skill_id="approach_food",
        seed=43,
        start_sim_time_sec=c1.end_sim_time_sec,
        duration_sec=2.0,
        fps=20.0,
        initial_pos=(last_pos[0], -last_pos[2], last_pos[1]),
    )

    storage.upload_clip(c1)
    storage.upload_clip(c2)

    manifest = storage.list_clips("pet_hammy_01")
    assert len(manifest) == 2
    assert manifest[0]["clip_id"] == c1.clip_id
    assert manifest[1]["clip_id"] == c2.clip_id
    assert manifest[0]["end_sim_time_sec"] == manifest[1]["start_sim_time_sec"]
    assert manifest[0]["origin"] == "observed_physics"

    loaded = storage.get_clip("pet_hammy_01", c1.clip_id)
    assert loaded is not None
    assert loaded.clip_id == c1.clip_id
    np.testing.assert_allclose(loaded.keyframes[0].root_pos, c1.keyframes[0].root_pos, atol=1e-6)
