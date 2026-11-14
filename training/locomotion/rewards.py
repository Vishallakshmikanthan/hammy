"""
Separate, auditable reward terms for P4.1 / P4.2 legged locomotion:
  - velocity_tracking
  - orientation
  - torque_energy
  - action_rate
  - foot_slip
  - falls
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import numpy as np


@dataclass(frozen=True)
class RewardWeights:
    velocity_tracking: float = 2.2
    orientation: float = -1.2
    torque_energy: float = -0.015
    action_rate: float = -0.06
    foot_slip: float = -0.35
    falls: float = -5.0


def compute_locomotion_rewards(
    lin_vel_xy: np.ndarray,
    yaw_rate: float | np.ndarray,
    cmd_vel_xy_yaw: np.ndarray,
    roll_pitch: np.ndarray,
    torques: np.ndarray,
    action: np.ndarray,
    prev_action: np.ndarray,
    foot_contacts: np.ndarray,
    foot_xy_speeds: np.ndarray,
    fallen: np.ndarray,
    weights: RewardWeights = RewardWeights(),
) -> tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    Vectorized reward computation over batch dimension N.
    Returns (total_reward [N], reward_terms_dict).
    """
    vx_err = np.sum((lin_vel_xy - cmd_vel_xy_yaw[:, :2]) ** 2, axis=-1)
    yaw_err = (np.asarray(yaw_rate) - cmd_vel_xy_yaw[:, 2]) ** 2
    r_vel = weights.velocity_tracking * np.exp(-3.5 * (vx_err + 0.5 * yaw_err))

    tilt = np.sum(roll_pitch ** 2, axis=-1)
    r_orient = weights.orientation * tilt

    r_torque = weights.torque_energy * np.mean(torques ** 2, axis=-1)
    r_act_rate = weights.action_rate * np.mean((action - prev_action) ** 2, axis=-1)

    slip = np.sum(foot_contacts * (foot_xy_speeds ** 2), axis=-1)
    r_slip = weights.foot_slip * slip

    r_falls = weights.falls * fallen.astype(np.float32)

    terms = {
        "velocity_tracking": r_vel,
        "orientation": r_orient,
        "torque_energy": r_torque,
        "action_rate": r_act_rate,
        "foot_slip": r_slip,
        "falls": r_falls,
    }
    total = r_vel + r_orient + r_torque + r_act_rate + r_slip + r_falls
    return total.astype(np.float32), terms

