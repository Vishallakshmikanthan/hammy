"""Stage 4: Evaluate autonomous habitat behaviours + petting/taming and render videos."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np

from ai.behaviour_manager import AutonomousBehaviourManager, InternalDrives
from simulation.habitat_objects import HABITAT_VERSION
from simulation.habitat_skill_controller import HabitatSkillController

OUT_DIR = Path("training/runs/stage4")
RENDERS_DIR = Path("renders/stage4")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RENDERS_DIR.mkdir(parents=True, exist_ok=True)

    ctrl = HabitatSkillController()

    # 1. Autonomous habitat benchmark (12 multi-skill episodes)
    auto_mgr = AutonomousBehaviourManager(
        InternalDrives(hunger=0.78, thirst=0.55, energy=0.70, comfort=0.60, stress=0.25, curiosity=0.72, familiarity=0.20)
    )
    ctrl.reset(start_xy=(0.0, 0.0), start_yaw=0.0)

    auto_frames: list[np.ndarray] = []
    auto_results = []
    for ep in range(6):
        dec = auto_mgr.select_autonomous_skill(
            food_available=ctrl.objects["prop_bowl_main"].resource_level,
            water_available=ctrl.objects["prop_bottle_main"].resource_level,
        )
        res = ctrl.execute_skill(
            skill_name=dec.skill_name,
            target_object_id=dec.target_object_id,
            max_approach_s=6.5,
            interact_s=1.0,
            manager=auto_mgr,
            record_frames=auto_frames if ep < 3 else None,
        )
        auto_mgr.apply_skill_outcome(dec.skill_name, res.success)
        auto_mgr.drives.step_time(1800.0)  # advance 30 min simulated time between bouts
        auto_results.append({**asdict(res), "selection_label": dec.selection_label, "drives_after": auto_mgr.drives.to_dict()})

    # 2. Petting & Taming progression (6 repeated parent interactions from shy -> tamed)
    pet_mgr = AutonomousBehaviourManager(
        InternalDrives(hunger=0.50, thirst=0.30, energy=0.80, comfort=0.60, stress=0.45, curiosity=0.50, familiarity=0.05)
    )
    pet_frames: list[np.ndarray] = []
    pet_results = []
    interaction_plan = [
        "gentle_pet",     # low trust -> avoid_and_retreat
        "offer_treat",    # builds familiarity
        "offer_treat",    # moderate trust -> cautious_sniff
        "gentle_pet",     # moderate/high trust
        "offer_treat",    # high trust -> accept_petting
        "gentle_pet",     # high trust -> accept_petting
    ]

    for idx, act_req in enumerate(interaction_plan):
        ctrl.reset(start_xy=(0.0, 0.0), start_yaw=0.0)
        outcome = pet_mgr.handle_parent_interaction(act_req)  # type: ignore[arg-type]
        margin = 0.06 if outcome.hamster_response == "cautious_sniff" else 0.0
        rec = pet_frames if idx in (0, 2, 5) else None
        res = ctrl.execute_skill(
            skill_name=outcome.hamster_response,
            target_object_id=outcome.target_object_id,
            max_approach_s=6.0,
            interact_s=1.0,
            cautious_stop_margin_m=margin,
            manager=pet_mgr,
            record_frames=rec,
            title_override=f"Petting #{idx+1} ({act_req} -> {outcome.hamster_response})",
        )
        pet_results.append({"interaction": asdict(outcome), "execution": asdict(res)})

    ctrl.close()

    # Save renders
    v_auto = RENDERS_DIR / "stage4_autonomous_habitat.mp4"
    v_pet = RENDERS_DIR / "stage4_petting_taming.mp4"
    imageio.mimsave(v_auto, auto_frames, fps=25, quality=8)
    imageio.mimsave(v_pet, pet_frames, fps=25, quality=8)

    snap_auto = auto_frames[len(auto_frames) // 2]
    snap_pet = pet_frames[len(pet_frames) - 10]
    preview = np.hstack([cv2.resize(snap_auto, (540, 300)), cv2.resize(snap_pet, (540, 300))])
    preview_p = RENDERS_DIR / "stage4_habitat_preview.png"
    imageio.imwrite(preview_p, preview)

    # Save grounded event log (JSONL)
    events_path = OUT_DIR / "events.jsonl"
    all_events = auto_mgr.event_log + pet_mgr.event_log
    events_path.write_text("\n".join(json.dumps(e) for e in all_events) + "\n", encoding="utf-8")

    # Summary metrics
    all_execs = auto_results + [p["execution"] for p in pet_results]
    n_total = len(all_execs)
    n_success = sum(1 for r in all_execs if r["success"])
    n_falls = sum(1 for r in all_execs if r["fell"])
    responses = [p["interaction"]["hamster_response"] for p in pet_results]

    report = {
        "habitat_version": HABITAT_VERSION,
        "onnx_policy_used": str(ctrl.onnx_path),
        "onnx_contract_meta": ctrl.onnx_meta,
        "summary": {
            "total_skill_executions": n_total,
            "success_rate_pct": round(100.0 * n_success / max(n_total, 1), 1),
            "fall_rate_pct": round(100.0 * n_falls / max(n_total, 1), 1),
            "taming_responses": responses,
            "familiarity_progression": [p["interaction"]["familiarity_after"] for p in pet_results],
            "stress_progression": [p["interaction"]["stress_after"] for p in pet_results],
            "events_logged": len(all_events),
        },
        "rendered_videos": [str(v_auto), str(v_pet), str(preview_p)],
        "autonomous_episodes": auto_results,
        "petting_taming_episodes": pet_results,
    }
    report_path = OUT_DIR / "stage4_eval_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
