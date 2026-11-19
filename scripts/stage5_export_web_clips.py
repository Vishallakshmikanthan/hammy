"""Stage 5: Export real MuJoCo + ONNX TrajectoryClipV1 bundles for object storage and Three.js web replay."""

from __future__ import annotations

import json
from pathlib import Path

from contracts.locomotion_contracts import MODEL_VERSION
from services.simulation_worker.mujoco_clip_generator import generate_mujoco_onnx_clip
from services.simulation_worker.storage import LocalObjectStorage
from simulation.habitat_objects import HABITAT_VERSION

WEB_CLIPS_DIR = Path("web/public/assets/mujoco_clips")
PET_ID = "pet_hammy_01"


def main() -> None:
    WEB_CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    storage = LocalObjectStorage()

    skills = [
        ("forage_bowl", 42),
        ("drink_water", 43),
        ("enter_tunnel", 44),
        ("retreat_to_hideout", 45),
        ("cautious_sniff", 46),
        ("accept_petting", 47),
    ]

    manifest_entries = []
    t_cursor = 0.0
    for skill_id, seed in skills:
        clip = generate_mujoco_onnx_clip(
            pet_id=PET_ID,
            skill_id=skill_id,
            seed=seed,
            start_sim_time_sec=t_cursor,
            max_approach_s=5.0,
            interact_s=1.0,
            fps=20.0,
        )
        t_cursor = clip.end_sim_time_sec

        # 1. Upload to backend LocalObjectStorage (.clip.json.gz)
        storage.upload_clip(clip)

        # 2. Export uncompressed JSON to web/public/assets/mujoco_clips/ for browser Three.js ClipPlayer
        clip_json_path = WEB_CLIPS_DIR / f"{clip.clip_id}.json"
        clip_json_path.write_text(clip.model_dump_json(indent=2), encoding="utf-8")

        p0 = clip.keyframes[0].root_pos
        p1 = clip.keyframes[-1].root_pos
        disp_m = float(((p1[0] - p0[0]) ** 2 + (p1[2] - p0[2]) ** 2) ** 0.5)

        manifest_entries.append(
            {
                "clip_id": clip.clip_id,
                "skill_id": clip.skill_id,
                "origin": clip.origin.value,
                "behaviour_type": clip.behaviour_type.value,
                "morphology_version": clip.morphology_version,
                "environment_version": clip.environment_version,
                "fps": clip.fps,
                "num_keyframes": len(clip.keyframes),
                "duration_s": round(clip.end_sim_time_sec - clip.start_sim_time_sec, 3),
                "displacement_m": round(disp_m, 3),
                "asset_url": f"/assets/mujoco_clips/{clip.clip_id}.json",
            }
        )

    manifest = {
        "pet_id": PET_ID,
        "model_version": MODEL_VERSION,
        "habitat_version": HABITAT_VERSION,
        "clips": manifest_entries,
    }
    manifest_p = WEB_CLIPS_DIR / "manifest.json"
    manifest_p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
