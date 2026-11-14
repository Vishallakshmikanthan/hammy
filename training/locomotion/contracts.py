"""
Versioned observation/action contracts and checkpoint metadata for Phase 4 locomotion.
Per Master Context Rule 5, every checkpoint records schema_version, morphology_version,
and environment_version and rejects incompatible policies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict

LOCOMOTION_OBS_SCHEMA_VERSION = "locomotion_obs_v1.0.0"
LOCOMOTION_ACT_SCHEMA_VERSION = "locomotion_act_v1.0.0"
QUADRUPED_MORPHOLOGY_VERSION = "quadruped_standin_v1.0.0"
QUADRUPED_ENV_VERSION = "quadruped_env_v1.0.0"
HAMSTER_MORPHOLOGY_VERSION = "hamster_v1.0.0"
HAMSTER_ENV_VERSION = "hamster_locomotion_env_v1.0.0"


@dataclass(frozen=True)
class LocomotionContractSpec:
    obs_dim: int
    action_dim: int
    num_joints: int
    obs_schema_version: str = LOCOMOTION_OBS_SCHEMA_VERSION
    act_schema_version: str = LOCOMOTION_ACT_SCHEMA_VERSION
    morphology_version: str = QUADRUPED_MORPHOLOGY_VERSION
    environment_version: str = QUADRUPED_ENV_VERSION

    def to_metadata(self) -> Dict[str, str]:
        return {
            "obs_schema_version": self.obs_schema_version,
            "act_schema_version": self.act_schema_version,
            "morphology_version": self.morphology_version,
            "environment_version": self.environment_version,
            "obs_dim": str(self.obs_dim),
            "action_dim": str(self.action_dim),
            "num_joints": str(self.num_joints),
        }


def validate_checkpoint_compatibility(
    checkpoint_meta: Dict[str, str],
    expected: LocomotionContractSpec,
) -> None:
    """Reject checkpoints trained against incompatible schemas, morphologies, or envs."""
    checks = [
        ("obs_schema_version", expected.obs_schema_version),
        ("act_schema_version", expected.act_schema_version),
        ("morphology_version", expected.morphology_version),
        ("environment_version", expected.environment_version),
    ]
    for key, exp_val in checks:
        got = checkpoint_meta.get(key)
        if got != exp_val:
            raise ValueError(
                f"Incompatible checkpoint {key}: expected '{exp_val}', got '{got}'"
            )


def spec_for_quadruped() -> LocomotionContractSpec:
    # 12 joint pos + 12 joint vel + 3 body orientation (roll, pitch, yaw_sin/cos or rpy)
    # + 3 angular vel + 12 prev action + 3 command (vx, vy, yaw_rate) = 45 dims
    return LocomotionContractSpec(
        obs_dim=45,
        action_dim=12,
        num_joints=12,
        morphology_version=QUADRUPED_MORPHOLOGY_VERSION,
        environment_version=QUADRUPED_ENV_VERSION,
    )


def spec_for_hamster() -> LocomotionContractSpec:
    # 14 joints (2 spine + 12 legs): 14 pos + 14 vel + 3 orient + 3 angvel + 14 prev_act + 3 cmd = 51 dims
    return LocomotionContractSpec(
        obs_dim=51,
        action_dim=14,
        num_joints=14,
        morphology_version=HAMSTER_MORPHOLOGY_VERSION,
        environment_version=HAMSTER_ENV_VERSION,
    )

