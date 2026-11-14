"""
Object storage abstraction for P5.1 trajectory clips.
`LocalObjectStorage` persists compressed `.clip.json.gz` files and a per-pet
`manifest.json` index under `infrastructure/object_storage/clips/`.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Dict, List, Optional

from contracts.schemas import TrajectoryClipV1

DEFAULT_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "infrastructure" / "object_storage" / "clips"


class LocalObjectStorage:
    def __init__(self, root: Path = DEFAULT_STORAGE_ROOT) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _pet_dir(self, pet_id: str) -> Path:
        d = self.root / pet_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _manifest_path(self, pet_id: str) -> Path:
        return self._pet_dir(pet_id) / "manifest.json"

    def _read_manifest(self, pet_id: str) -> List[Dict]:
        mp = self._manifest_path(pet_id)
        if not mp.exists():
            return []
        return json.loads(mp.read_text(encoding="utf-8"))

    def upload_clip(self, clip: TrajectoryClipV1) -> str:
        pet_dir = self._pet_dir(clip.pet_id)
        object_key = f"{clip.pet_id}/{clip.clip_id}.clip.json.gz"
        file_path = pet_dir / f"{clip.clip_id}.clip.json.gz"

        raw = clip.model_dump_json().encode("utf-8")
        file_path.write_bytes(gzip.compress(raw))

        manifest = self._read_manifest(clip.pet_id)
        manifest = [m for m in manifest if m["clip_id"] != clip.clip_id]
        manifest.append(
            {
                "clip_id": clip.clip_id,
                "object_key": object_key,
                "skill_id": clip.skill_id,
                "seed": clip.seed,
                "origin": clip.origin.value,
                "behaviour_type": clip.behaviour_type.value,
                "fps": clip.fps,
                "start_sim_time_sec": clip.start_sim_time_sec,
                "end_sim_time_sec": clip.end_sim_time_sec,
                "keyframe_count": len(clip.keyframes),
            }
        )
        manifest.sort(key=lambda m: m["start_sim_time_sec"])
        self._manifest_path(clip.pet_id).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return object_key

    def list_clips(self, pet_id: str) -> List[Dict]:
        return self._read_manifest(pet_id)

    def get_clip(self, pet_id: str, clip_id: str) -> Optional[TrajectoryClipV1]:
        file_path = self._pet_dir(pet_id) / f"{clip_id}.clip.json.gz"
        if not file_path.exists():
            return None
        raw = gzip.decompress(file_path.read_bytes()).decode("utf-8")
        return TrajectoryClipV1.model_validate_json(raw)

