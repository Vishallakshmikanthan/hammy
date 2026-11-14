"""
HAMMY — P0.2: Versioned Schema Registry & Pydantic Contracts (`contracts/schemas.py`).
Enforces Non-Negotiable Rules 1, 2, 4, and 5 from the Master Context Prompt:
  - Every behaviour is explicitly labelled `learned`, `scripted`, or `rule`.
  - Every event records its origin: `observed_physics`, `sampled_from_skill_model`, or `rule`.
  - Every command includes a unique `command_id` idempotency key.
  - Observation and Action schemas are versioned (`v1`), and unknown/incompatible schema
    or morphology versions are rejected.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==============================================================================
# 1. VERSION REGISTRY & COMPATIBILITY ENFORCEMENT (Rule 5)
# ==============================================================================
SUPPORTED_SCHEMA_VERSIONS: Dict[str, List[str]] = {
    "observation": ["1.0.0", "2.0.0"],
    "action": ["1.0.0"],
    "event": ["1.0.0"],
    "command": ["1.0.0"],
    "trajectory_clip": ["1.0.0"],
    "morphology": ["simple_agent_v1", "syrian_quadruped_v1", "hamster_v1.0.0"],
    "environment": ["habitat_v1"],
}


class SchemaCompatibilityError(ValueError):
    """Raised when an unknown or incompatible schema, morphology, or environment version is encountered."""


def validate_version(domain: str, version: str) -> str:
    if domain not in SUPPORTED_SCHEMA_VERSIONS:
        raise SchemaCompatibilityError(f"Unknown contract domain '{domain}'.")
    allowed = SUPPORTED_SCHEMA_VERSIONS[domain]
    if version not in allowed:
        raise SchemaCompatibilityError(
            f"Incompatible {domain} version '{version}'. Supported versions: {allowed}"
        )
    return version


# ==============================================================================
# 2. HONESTY & ORIGIN ENUMS (Non-Negotiable Rules 1 & 2)
# ==============================================================================
class BehaviourType(str, Enum):
    LEARNED = "learned"
    SCRIPTED = "scripted"
    RULE = "rule"


class EventOrigin(str, Enum):
    OBSERVED_PHYSICS = "observed_physics"
    SAMPLED_FROM_SKILL_MODEL = "sampled_from_skill_model"
    RULE = "rule"


# ==============================================================================
# 3. OBSERVATION V1 CONTRACT
# ==============================================================================
class DriveVectorV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hunger: float = Field(..., ge=0.0, le=1.0, description="0 = full, 1 = starving")
    thirst: float = Field(..., ge=0.0, le=1.0, description="0 = hydrated, 1 = dehydrated")
    energy: float = Field(..., ge=0.0, le=1.0, description="0 = exhausted, 1 = fully rested")
    comfort: float = Field(..., ge=0.0, le=1.0, description="0 = distressed, 1 = cozy/comfortable")
    stress: float = Field(..., ge=0.0, le=1.0, description="0 = calm, 1 = highly stressed")
    curiosity: float = Field(..., ge=0.0, le=1.0, description="0 = sated, 1 = strong exploratory drive")
    circadian_phase: float = Field(..., ge=0.0, le=1.0, description="[0, 1) phase of 24h cycle (0.0 = midnight)")


class ObjectObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_id: str = Field(..., min_length=1)
    object_type: Literal["food_bowl", "water_bottle", "hideout", "tunnel", "wheel", "chew_toy"]
    rel_pos_xy: List[float] = Field(..., min_length=2, max_length=2)
    distance_m: float = Field(..., ge=0.0)
    resource_level: float = Field(default=1.0, ge=0.0, le=1.0)


class ObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0.0")
    morphology_version: str = Field(default="simple_agent_v1")
    environment_version: str = Field(default="habitat_v1")
    sim_time_sec: float = Field(..., ge=0.0)
    position_xyz: List[float] = Field(..., min_length=3, max_length=3)
    yaw_rad: float
    velocity_xy: List[float] = Field(..., min_length=2, max_length=2)
    angular_velocity_z: float
    inside_hideout: bool = False
    inside_tunnel: bool = False
    on_wheel: bool = False
    cheek_pouch_fill: float = Field(default=0.0, ge=0.0, le=1.0)
    drives: DriveVectorV1
    nearby_objects: List[ObjectObservationV1] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def _check_obs_ver(cls, v: str) -> str:
        return validate_version("observation", v)

    @field_validator("morphology_version")
    @classmethod
    def _check_morph_ver(cls, v: str) -> str:
        return validate_version("morphology", v)

    @field_validator("environment_version")
    @classmethod
    def _check_env_ver(cls, v: str) -> str:
        return validate_version("environment", v)


# ==============================================================================
# 3b. OBSERVATION V2 CONTRACT (P1.4: Memory Features)
# ==============================================================================
class ObjectMemoryItemV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_id: str = Field(..., min_length=1)
    estimated_value: float = Field(..., description="Running mean value estimate (utility/reward)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in estimate [0, 1]")
    time_since_last_visit_sec: float = Field(..., ge=0.0, description="Seconds elapsed since last visit")
    recency_normalized: float = Field(..., ge=0.0, le=1.0, description="Normalized recency in [0, 1]")
    last_known_pos_xy: Optional[List[float]] = Field(default=None, min_length=2, max_length=2)


class SpatialMemoryV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grid_shape: List[int] = Field(default_factory=lambda: [8, 4], min_length=2, max_length=2)
    current_cell_idx: List[int] = Field(..., min_length=2, max_length=2)
    current_cell_familiarity: float = Field(..., ge=0.0, le=1.0)
    mean_familiarity: float = Field(..., ge=0.0, le=1.0)
    coarse_sectors: List[float] = Field(default_factory=list, description="4x2 coarse sector familiarity (8 floats)")


class MemoryStateV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_memories: List[ObjectMemoryItemV2] = Field(default_factory=list)
    spatial: SpatialMemoryV2


class ObservationV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="2.0.0")
    morphology_version: str = Field(default="simple_agent_v1")
    environment_version: str = Field(default="habitat_v1")
    sim_time_sec: float = Field(..., ge=0.0)
    position_xyz: List[float] = Field(..., min_length=3, max_length=3)
    yaw_rad: float
    velocity_xy: List[float] = Field(..., min_length=2, max_length=2)
    angular_velocity_z: float
    inside_hideout: bool = False
    inside_tunnel: bool = False
    on_wheel: bool = False
    cheek_pouch_fill: float = Field(default=0.0, ge=0.0, le=1.0)
    drives: DriveVectorV1
    nearby_objects: List[ObjectObservationV1] = Field(default_factory=list)
    memory: Optional[MemoryStateV2] = None

    @field_validator("schema_version")
    @classmethod
    def _check_obs_ver(cls, v: str) -> str:
        return validate_version("observation", v)

    @field_validator("morphology_version")
    @classmethod
    def _check_morph_ver(cls, v: str) -> str:
        return validate_version("morphology", v)

    @field_validator("environment_version")
    @classmethod
    def _check_env_ver(cls, v: str) -> str:
        return validate_version("environment", v)



# ==============================================================================
# 4. ACTION V1 CONTRACT
# ==============================================================================
class ActionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0.0")
    forward_speed_m_s: float = Field(..., ge=-0.15, le=0.45, description="Planar forward speed command (m/s)")
    turn_rate_rad_s: float = Field(..., ge=-6.0, le=6.0, description="Yaw turn rate command (rad/s)")
    interact_flag: bool = Field(default=False, description="Trigger eat/drink/wheel/hoard interaction at current object")
    behaviour_type: BehaviourType = Field(..., description="Honesty label: learned | scripted | rule")

    @field_validator("schema_version")
    @classmethod
    def _check_act_ver(cls, v: str) -> str:
        return validate_version("action", v)


# ==============================================================================
# 5. WORLD EVENT V1 CONTRACT (Rules 1, 2, 7)
# ==============================================================================
class WorldEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0.0")
    event_id: str = Field(..., min_length=4, description="Deterministic unique event ID")
    pet_id: str = Field(..., min_length=1)
    world_tick: int = Field(..., ge=0)
    sim_time_sec: float = Field(..., ge=0.0)
    event_type: str = Field(..., min_length=1)
    skill_name: Optional[str] = None
    origin: EventOrigin = Field(..., description="observed_physics | sampled_from_skill_model | rule")
    behaviour_type: BehaviourType = Field(..., description="learned | scripted | rule")
    seed: int = Field(..., ge=0)
    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def _check_evt_ver(cls, v: str) -> str:
        return validate_version("event", v)


# ==============================================================================
# 6. COMMAND V1 CONTRACT (Rule 4: Idempotency Key)
# ==============================================================================
class CommandV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0.0")
    command_id: str = Field(..., min_length=6, description="Mandatory client/caller idempotency key")
    pet_id: str = Field(..., min_length=1)
    command_type: Literal["feed", "water", "add_enrichment", "move_object", "pause", "resume"]
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def _check_cmd_ver(cls, v: str) -> str:
        return validate_version("command", v)


# ==============================================================================
# 7. TRAJECTORY CLIP V1 CONTRACT (P5.1)
# ==============================================================================
class TrajectoryKeyframeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t_sec: float = Field(..., ge=0.0, description="Relative timestamp within clip (seconds)")
    root_pos: List[float] = Field(..., min_length=3, max_length=3)
    root_quat: List[float] = Field(..., min_length=4, max_length=4)
    joint_angles: List[float] = Field(..., min_length=12, max_length=14)
    foot_contacts: List[bool] = Field(..., min_length=4, max_length=4)


class TrajectoryClipV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0.0")
    clip_id: str = Field(..., min_length=4)
    pet_id: str = Field(..., min_length=1)
    skill_id: str = Field(..., min_length=1)
    seed: int = Field(..., ge=0)
    origin: EventOrigin = Field(..., description="observed_physics | sampled_from_skill_model | rule")
    behaviour_type: BehaviourType = Field(..., description="learned | scripted | rule")
    morphology_version: str = Field(default="hamster_v1.0.0")
    environment_version: str = Field(default="habitat_v1")
    fps: float = Field(default=20.0, gt=0.0, le=120.0)
    start_sim_time_sec: float = Field(..., ge=0.0)
    end_sim_time_sec: float = Field(..., ge=0.0)
    keyframes: List[TrajectoryKeyframeV1] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def _check_clip_ver(cls, v: str) -> str:
        return validate_version("trajectory_clip", v)

    @field_validator("morphology_version")
    @classmethod
    def _check_clip_morph(cls, v: str) -> str:
        return validate_version("morphology", v)

    @field_validator("environment_version")
    @classmethod
    def _check_clip_env(cls, v: str) -> str:
        return validate_version("environment", v)


def export_json_schemas(
    output_dir: str | Path = "contracts/json_schema",
    include_v2: bool = True,
) -> List[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    models = {
        "observation_v1.schema.json": ObservationV1,
        "action_v1.schema.json": ActionV1,
        "event_v1.schema.json": WorldEventV1,
        "command_v1.schema.json": CommandV1,
    }
    if include_v2:
        models["observation_v2.schema.json"] = ObservationV2

    written = []
    for filename, model_cls in models.items():
        path = out / filename
        path.write_text(json.dumps(model_cls.model_json_schema(), indent=2), encoding="utf-8")
        written.append(path)
    return written

