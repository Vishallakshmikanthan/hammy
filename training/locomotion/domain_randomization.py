"""
Domain randomisation configuration and sampling for P4.1 / P4.2 locomotion:
friction, mass, actuator strength, action latency, and sensor noise.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class DomainRandomizationRanges:
    friction_range: tuple[float, float] = (0.55, 1.25)
    mass_scale_range: tuple[float, float] = (0.85, 1.20)
    actuator_strength_range: tuple[float, float] = (0.85, 1.15)
    latency_steps_choices: tuple[int, ...] = (0, 1, 2)
    pos_noise_std: float = 0.015
    vel_noise_std: float = 0.05
    imu_noise_std: float = 0.02


@dataclass
class RandomizedEnvParams:
    friction: np.ndarray          # [N]
    mass_scale: np.ndarray        # [N]
    actuator_strength: np.ndarray # [N]
    latency_steps: np.ndarray     # [N] int


def sample_domain_randomization(
    num_envs: int,
    rng: np.random.Generator,
    ranges: DomainRandomizationRanges = DomainRandomizationRanges(),
    enabled: bool = True,
) -> RandomizedEnvParams:
    if not enabled:
        return RandomizedEnvParams(
            friction=np.ones(num_envs, dtype=np.float32),
            mass_scale=np.ones(num_envs, dtype=np.float32),
            actuator_strength=np.ones(num_envs, dtype=np.float32),
            latency_steps=np.zeros(num_envs, dtype=np.int32),
        )
    return RandomizedEnvParams(
        friction=rng.uniform(*ranges.friction_range, size=num_envs).astype(np.float32),
        mass_scale=rng.uniform(*ranges.mass_scale_range, size=num_envs).astype(np.float32),
        actuator_strength=rng.uniform(*ranges.actuator_strength_range, size=num_envs).astype(np.float32),
        latency_steps=rng.choice(ranges.latency_steps_choices, size=num_envs).astype(np.int32),
    )

