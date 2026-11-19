"""Stage 5: FastAPI bridge exposing MuJoCo + ONNX policy status, petting interactions, and clips."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai.behaviour_manager import AutonomousBehaviourManager, InternalDrives
from contracts.locomotion_contracts import (
    ACTION_CONTRACT_VERSION,
    MODEL_VERSION,
    OBS_CONTRACT_VERSION,
)

router = APIRouter()

WEB_CLIPS_DIR = Path("web/public/assets/mujoco_clips")
ONNX_REPORT_PATH = Path("training/runs/stage3/ablation_report.json")

_behaviour_mgr = AutonomousBehaviourManager(
    InternalDrives(hunger=0.45, thirst=0.35, energy=0.80, comfort=0.65, stress=0.40, curiosity=0.55, familiarity=0.10)
)


class ParentInteractionRequest(BaseModel):
    action: Literal["offer_treat", "gentle_pet", "call_attention"] = "gentle_pet"


def _load_manifest() -> Dict[str, Any]:
    manifest_p = WEB_CLIPS_DIR / "manifest.json"
    if not manifest_p.exists():
        return {"clips": []}
    return json.loads(manifest_p.read_text(encoding="utf-8"))


@router.get("/mujoco/status")
def get_mujoco_bridge_status() -> Dict[str, Any]:
    manifest = _load_manifest()
    onnx_meta: Dict[str, Any] = {}
    if ONNX_REPORT_PATH.exists():
        rep = json.loads(ONNX_REPORT_PATH.read_text(encoding="utf-8"))
        onnx_meta = {
            "best_condition": rep.get("best_condition"),
            "honesty_label": rep.get("best_honesty_label"),
            "onnx_export": rep.get("onnx_export"),
        }
    return {
        "model_version": MODEL_VERSION,
        "obs_contract_version": OBS_CONTRACT_VERSION,
        "act_contract_version": ACTION_CONTRACT_VERSION,
        "drives": _behaviour_mgr.drives.to_dict(),
        "interaction_count": _behaviour_mgr.interaction_count,
        "policy": onnx_meta,
        "available_clips": manifest.get("clips", []),
    }


@router.post("/mujoco/interact")
def post_parent_interaction(req: ParentInteractionRequest) -> Dict[str, Any]:
    outcome = _behaviour_mgr.handle_parent_interaction(req.action)
    manifest = _load_manifest()
    matched_clip = None
    for entry in manifest.get("clips", []):
        if entry.get("skill_id") == outcome.hamster_response:
            matched_clip = entry
            break
    if matched_clip is None and outcome.hamster_response == "avoid_and_retreat":
        for entry in manifest.get("clips", []):
            if entry.get("skill_id") == "retreat_to_hideout":
                matched_clip = entry
                break
    return {
        "outcome": asdict(outcome),
        "drives": _behaviour_mgr.drives.to_dict(),
        "clip": matched_clip,
    }


@router.get("/mujoco/clips/{clip_id}")
def get_mujoco_clip(clip_id: str) -> Dict[str, Any]:
    clip_p = WEB_CLIPS_DIR / f"{clip_id}.json"
    if not clip_p.exists():
        raise HTTPException(status_code=404, detail=f"MuJoCo clip '{clip_id}' not found")
    return json.loads(clip_p.read_text(encoding="utf-8"))
