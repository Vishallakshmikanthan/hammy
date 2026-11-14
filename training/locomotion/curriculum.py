"""
Success-driven locomotion curriculum for P4.1:
  stand -> perturbation_recovery -> walk -> turn -> stop
Advances stage only when measured rolling success rate exceeds `advance_threshold`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import numpy as np

CurriculumStage = Literal["stand", "perturbation_recovery", "walk", "turn", "stop"]

STAGES: tuple[CurriculumStage, ...] = (
    "stand",
    "perturbation_recovery",
    "walk",
    "turn",
    "stop",
)


@dataclass
class CurriculumState:
    stage_idx: int = 0
    advance_threshold: float = 0.72
    last_success_rate: float = 0.0

    @property
    def stage(self) -> CurriculumStage:
        return STAGES[self.stage_idx]

    def update(self, measured_success_rate: float) -> bool:
        self.last_success_rate = float(measured_success_rate)
        if measured_success_rate >= self.advance_threshold and self.stage_idx < len(STAGES) - 1:
            self.stage_idx += 1
            return True
        return False

    def sample_commands(self, num_envs: int, rng: np.random.Generator) -> tuple[np.ndarray, float]:
        """
        Return (cmd_vel_xy_yaw [N, 3], perturbation_impulse_scale).
        """
        cmds = np.zeros((num_envs, 3), dtype=np.float32)
        stage = self.stage
        if stage == "stand":
            return cmds, 0.0
        if stage == "perturbation_recovery":
            return cmds, 1.0
        if stage == "walk":
            cmds[:, 0] = rng.uniform(0.12, 0.40, size=num_envs)
            return cmds, 0.35
        if stage == "turn":
            cmds[:, 0] = rng.uniform(0.10, 0.32, size=num_envs)
            cmds[:, 2] = rng.uniform(-1.0, 1.0, size=num_envs)
            return cmds, 0.35
        # stop: mix of moving and zero-velocity stop commands
        moving = rng.random(num_envs) > 0.35
        cmds[moving, 0] = rng.uniform(0.10, 0.38, size=int(np.sum(moving)))
        cmds[moving, 2] = rng.uniform(-0.8, 0.8, size=int(np.sum(moving)))
        return cmds, 0.45

