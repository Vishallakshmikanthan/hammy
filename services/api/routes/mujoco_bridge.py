"""Stage 5 + Phase D: FastAPI bridge exposing MuJoCo + ONNX motor & cognitive brain status,
unified learned parent taming interactions, and verified trajectory clips."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ai.behaviour_manager import AutonomousBehaviourManager, InternalDrives
from contracts.locomotion_contracts import (
    ACTION_CONTRACT_VERSION,
    MODEL_VERSION,
    OBS_CONTRACT_VERSION,
    OBS_V2_CONTRACT_VERSION,
)
from infrastructure.database.models import PetState
from services.api.auth import get_db
from services.api.websocket import ws_manager
from services.runtime.live_brain_engine import live_brain_engine

router = APIRouter()

WEB_CLIPS_DIR = Path("web/public/assets/mujoco_clips")
ONNX_V1_REPORT_PATH = Path("training/runs/stage3/ablation_report.json")
ONNX_V2_REPORT_PATH = Path("training/runs/motor_v2/motor_v2_report.json")
BRAIN_V2_REPORT_PATH = Path("training/runs/brain_v2/train_summary.json")

# Fallback only used if SQLite has no seeded pet row (e.g. isolated unit tests)
_fallback_mgr = AutonomousBehaviourManager(
    InternalDrives(hunger=0.35, thirst=0.25, energy=0.80, comfort=0.72, stress=0.25, curiosity=0.45, familiarity=0.15)
)


class ParentInteractionRequest(BaseModel):
    action: Literal["offer_treat", "gentle_pet", "call_attention"] = "gentle_pet"
    pet_id: str = "pet_hammy_01"


def _load_manifest() -> Dict[str, Any]:
    manifest_p = WEB_CLIPS_DIR / "manifest.json"
    if not manifest_p.exists():
        return {"clips": []}
    return json.loads(manifest_p.read_text(encoding="utf-8"))


@router.get("/mujoco/status")
def get_mujoco_bridge_status(
    pet_id: str = "pet_hammy_01",
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    manifest = _load_manifest()
    onnx_meta: Dict[str, Any] = {}
    if ONNX_V2_REPORT_PATH.exists():
        rep = json.loads(ONNX_V2_REPORT_PATH.read_text(encoding="utf-8"))
        onnx_meta = {
            "best_condition": "amp_ppo_v2",
            "honesty_label": "LEARNED (RTX 5070 GPU AMP-PPO v2 + REAL_VIDEO style prior)",
            "onnx_export": rep.get("onnx_export"),
            "eval_100ep": rep.get("eval_100ep"),
        }
    elif ONNX_V1_REPORT_PATH.exists():
        rep = json.loads(ONNX_V1_REPORT_PATH.read_text(encoding="utf-8"))
        onnx_meta = {
            "best_condition": rep.get("best_condition"),
            "honesty_label": rep.get("best_honesty_label"),
            "onnx_export": rep.get("onnx_export"),
        }

    brain_meta: Dict[str, Any] = {
        "policy_version": live_brain_engine.policy_version,
        "behaviour_mode": live_brain_engine.behaviour_mode,
        "motor_policy_version": live_brain_engine.motor_policy_version,
    }
    if BRAIN_V2_REPORT_PATH.exists():
        brep = json.loads(BRAIN_V2_REPORT_PATH.read_text(encoding="utf-8"))
        brain_meta["total_steps"] = brep.get("total_steps")
        brain_meta["eval"] = brep.get("eval")
        brain_meta["onnx_export"] = brep.get("onnx_export")

    pet_state = session.get(PetState, pet_id)
    if pet_state is not None:
        tel = live_brain_engine.get_brain_telemetry(session, pet_id)
        drives = {**(pet_state.drives or {}), "familiarity": tel["familiarity"]}
        interaction_count = live_brain_engine._get_mem(session, pet_id).interaction_count
    else:
        drives = _fallback_mgr.drives.to_dict()
        interaction_count = _fallback_mgr.interaction_count

    return {
        "model_version": MODEL_VERSION,
        "obs_contract_version": OBS_V2_CONTRACT_VERSION if ONNX_V2_REPORT_PATH.exists() else OBS_CONTRACT_VERSION,
        "act_contract_version": ACTION_CONTRACT_VERSION,
        "drives": drives,
        "interaction_count": interaction_count,
        "policy": onnx_meta,
        "cognitive_brain": brain_meta,
        "available_clips": manifest.get("clips", []),
    }


@router.post("/mujoco/interact")
async def post_parent_interaction(
    req: ParentInteractionRequest,
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    manifest = _load_manifest()
    pet_state = session.get(PetState, req.pet_id)

    if pet_state is not None:
        res = live_brain_engine.handle_parent_interaction(session, req.pet_id, req.action)
        outcome_dict = res["outcome"]
        drives_dict = res["drives"]
        await ws_manager.broadcast_to_pet(req.pet_id, res["snapshot"])
        await ws_manager.broadcast_to_pet(req.pet_id, {"type": "event", "event": res["event"]})
    else:
        outcome = _fallback_mgr.handle_parent_interaction(req.action)
        outcome_dict = asdict(outcome)
        drives_dict = _fallback_mgr.drives.to_dict()

    resp_skill = outcome_dict.get("hamster_response")
    matched_clip: Optional[Dict[str, Any]] = None
    for entry in manifest.get("clips", []):
        if entry.get("skill_id") == resp_skill:
            matched_clip = entry
            break
    if matched_clip is None and resp_skill == "avoid_and_retreat":
        for entry in manifest.get("clips", []):
            if entry.get("skill_id") == "retreat_to_hideout":
                matched_clip = entry
                break

    return {
        "outcome": outcome_dict,
        "drives": drives_dict,
        "clip": matched_clip,
        "policy_version": live_brain_engine.policy_version,
        "behaviour_mode": live_brain_engine.behaviour_mode,
    }


@router.get("/mujoco/clips/{clip_id}")
def get_mujoco_clip(clip_id: str) -> Dict[str, Any]:
    clip_p = WEB_CLIPS_DIR / f"{clip_id}.json"
    if not clip_p.exists():
        raise HTTPException(status_code=404, detail=f"MuJoCo clip '{clip_id}' not found")
    return json.loads(clip_p.read_text(encoding="utf-8"))
