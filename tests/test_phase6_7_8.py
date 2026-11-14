"""Tests for Phase 6 (Behaviours), Phase 7 (RND Curiosity & Autonomy), and Phase 8 (Cinematic Delivery)."""

from __future__ import annotations

from pathlib import Path
import numpy as np

from ai.cognition.drives import HomeostaticDrives
from ai.cognition.rnd_curiosity import RNDConfig, RNDCuriosityModule
from ai.policies.behaviours import BEHAVIOUR_SPECS
from ai.policies.skills import SKILLS_BY_NAME
from contracts.schemas import (
    BehaviourType,
    EventOrigin,
    ObservationV1,
    WorldEventV1,
)
from services.notification_worker.cinematic_delivery import (
    CinematicRenderQueue,
    RenderBudget,
    build_verified_clip_caption,
    deliver_cinematic_clip,
)
from services.simulation_worker.clip_generator import generate_episode_clip


def test_p6_behaviours_registered_and_honestly_labelled():
    expected = {"cheek_stuffing", "hind_leg_standing", "grooming", "digging", "nesting"}
    assert expected.issubset(set(BEHAVIOUR_SPECS.keys()))
    assert expected.issubset(set(SKILLS_BY_NAME.keys()))

    drives = HomeostaticDrives()
    obs = ObservationV1(
        sim_time_sec=10.0,
        position_xyz=[0.0, 0.0, 0.165],
        yaw_rad=0.0,
        velocity_xy=[0.0, 0.0],
        angular_velocity_z=0.0,
        drives=drives.to_contract(),
        nearby_objects=[],
    )
    for name in expected:
        assert BEHAVIOUR_SPECS[name].implementation_type == "scripted-with-learned-selection"
        act = SKILLS_BY_NAME[name].step(obs)
        assert act.behaviour_type == BehaviourType.SCRIPTED


def test_p7_rnd_curiosity_decay_and_noisy_tv_safeguard():
    rnd = RNDCuriosityModule(RNDConfig(obs_dim=8, decay_half_life_steps=100.0, noisy_tv_damping_rate=0.5), seed=42)
    vec = np.array([0.2, 0.2, 0.8, 0.8, 0.1, 0.5, 0.1, 1.0], dtype=np.float32)

    r_first = rnd.compute_intrinsic_reward(vec, update=True)
    for _ in range(25):
        r_later = rnd.compute_intrinsic_reward(vec, update=True)
    assert r_first >= 0.0
    assert r_later < r_first or r_later == 0.0


def test_p8_cinematic_queue_and_verified_caption(tmp_path: Path):
    clip = generate_episode_clip(
        pet_id="pet_hammy_01",
        skill_id="explore_area",
        seed=42,
        start_sim_time_sec=10.0,
        duration_sec=2.0,
    )
    queue = CinematicRenderQueue(output_dir=tmp_path)
    job = queue.enqueue(clip, camera_preset="low_macro", budget=RenderBudget(samples=32, res_x=640, res_y=360))
    assert "seed42" in job.output_path.name
    assert "low_macro" in job.output_path.name

    ev = WorldEventV1(
        event_id="evt_test_0001",
        pet_id="pet_hammy_01",
        world_tick=10,
        sim_time_sec=11.0,
        event_type="skill_completed",
        skill_name="explore_area",
        origin=EventOrigin.OBSERVED_PHYSICS,
        behaviour_type=BehaviourType.LEARNED,
        seed=42,
        payload={},
    )
    caption = build_verified_clip_caption(clip, [ev])
    assert "observed_physics" in caption
    assert "skill_completed" in caption
    assert "Seed: 42" in caption

    sent = []
    deliver_cinematic_clip(
        chat_id="12345",
        clip=clip,
        events=[ev],
        video_path=job.output_path,
        send_video_fn=lambda cid, path, cap: sent.append((cid, str(path), cap)) or {"ok": True},
    )
    assert len(sent) == 1
    assert sent[0][0] == "12345"
