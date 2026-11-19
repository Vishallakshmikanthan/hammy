"""Stage 4 acceptance tests: MuJoCo habitat + ONNX skill execution + drives + petting/taming."""

from __future__ import annotations

import json
from pathlib import Path

from ai.behaviour_manager import AutonomousBehaviourManager, InternalDrives
from simulation.habitat_objects import build_habitat_model, default_habitat_objects
from simulation.habitat_skill_controller import HabitatSkillController


def test_habitat_mjcf_builds_and_contains_props():
    objs = default_habitat_objects()
    assert len(objs) == 6
    model = build_habitat_model(objects=objs)
    assert model.nu == 16


def test_petting_non_forced_and_taming_progression():
    mgr = AutonomousBehaviourManager(InternalDrives(stress=0.50, familiarity=0.05))

    # First gentle pet when stressed & unfamiliar must NOT force acceptance
    out1 = mgr.handle_parent_interaction("gentle_pet")
    assert out1.hamster_response == "avoid_and_retreat"
    assert out1.target_object_id == "prop_hideout_main"

    # Repeated gentle treats gradually build familiarity & reduce stress -> accept_petting
    responses = [out1.hamster_response]
    for _ in range(5):
        out = mgr.handle_parent_interaction("offer_treat")
        responses.append(out.hamster_response)

    assert "accept_petting" in responses
    assert mgr.drives.familiarity > out1.familiarity_before
    # Drives stay strictly bounded in [0, 1]
    for val in mgr.drives.to_dict().values():
        assert 0.0 <= val <= 1.0


def test_onnx_habitat_skill_execution_without_falling():
    ctrl = HabitatSkillController()
    ctrl.reset(start_xy=(0.0, 0.0), start_yaw=0.0)
    res = ctrl.execute_skill("forage_bowl", "prop_bowl_main", max_approach_s=3.5, interact_s=0.6)
    ctrl.close()
    assert res.fell is False
    assert "LEARNED" in res.locomotion_label
    assert res.interaction_label == "RULE-BASED"
    assert res.final_dist_m < res.start_dist_m


def test_stage4_report_events_and_renders_exist():
    report_p = Path("training/runs/stage4/stage4_eval_report.json")
    events_p = Path("training/runs/stage4/events.jsonl")
    assert report_p.exists() and events_p.exists()

    report = json.loads(report_p.read_text(encoding="utf-8"))
    summary = report["summary"]
    assert summary["fall_rate_pct"] == 0.0
    assert summary["success_rate_pct"] >= 80.0
    assert "avoid_and_retreat" in summary["taming_responses"]
    assert "accept_petting" in summary["taming_responses"]

    for v in (
        "renders/stage4/stage4_autonomous_habitat.mp4",
        "renders/stage4/stage4_petting_taming.mp4",
        "renders/stage4/stage4_habitat_preview.png",
    ):
        vp = Path(v)
        assert vp.exists() and vp.stat().st_size > 10_000, f"Missing render: {vp}"
