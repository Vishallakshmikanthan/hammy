"""
HAMMY — P1.2: Homeostatic Drives & Reward System (`ai/cognition/drives.py`).
Models a crepuscular/nocturnal Syrian hamster's 6 internal drives normalized to [0, 1]
plus a 24-hour circadian phase variable:
  - hunger, thirst, energy, comfort, stress, curiosity
Computes the homeostatic reward as the reduction in summed squared deviation from
per-drive set points (`reward = D(s_t) - D(s_{t+1})`), exposing each drive's term
separately in `info` for transparent logging.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
from contracts.schemas import DriveVectorV1

DEFAULT_CONFIG_PATH = Path(__file__).parent / "drives_config.json"
with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _CACHED_DRIVES_CFG = json.load(_f)


@dataclass
class HomeostaticDrives:
    hunger: float = 0.18
    thirst: float = 0.16
    energy: float = 0.82
    comfort: float = 0.78
    stress: float = 0.10
    curiosity: float = 0.25
    circadian_phase: float = 0.80  # 0.80 = 19:12 evening (active dusk period for nocturnal hamster)

    def __post_init__(self):
        self.cfg = _CACHED_DRIVES_CFG
        self._clamp_all()

    def _clamp_all(self):
        self.hunger = float(np.clip(self.hunger, 0.0, 1.0))
        self.thirst = float(np.clip(self.thirst, 0.0, 1.0))
        self.energy = float(np.clip(self.energy, 0.0, 1.0))
        self.comfort = float(np.clip(self.comfort, 0.0, 1.0))
        self.stress = float(np.clip(self.stress, 0.0, 1.0))
        self.curiosity = float(np.clip(self.curiosity, 0.0, 1.0))
        self.circadian_phase = float(self.circadian_phase % 1.0)

    def is_daylight(self) -> bool:
        c = self.cfg["circadian"]
        return bool(c["daylight_start_phase"] <= self.circadian_phase <= c["daylight_end_phase"])

    def to_contract(self) -> DriveVectorV1:
        return DriveVectorV1(
            hunger=self.hunger,
            thirst=self.thirst,
            energy=self.energy,
            comfort=self.comfort,
            stress=self.stress,
            curiosity=self.curiosity,
            circadian_phase=self.circadian_phase,
        )

    def per_drive_squared_deviations(self) -> Dict[str, float]:
        sp = self.cfg["set_points"]
        return {
            "hunger": (self.hunger - sp["hunger"]) ** 2,
            "thirst": (self.thirst - sp["thirst"]) ** 2,
            "energy": (self.energy - sp["energy"]) ** 2,
            "comfort": (self.comfort - sp["comfort"]) ** 2,
            "stress": (self.stress - sp["stress"]) ** 2,
            "curiosity": (self.curiosity - sp["curiosity"]) ** 2,
        }

    def total_drive_deviation(self) -> float:
        return float(sum(self.per_drive_squared_deviations().values()))

    def in_healthy_range_flags(self) -> Dict[str, bool]:
        hr = self.cfg["healthy_ranges"]
        vals = {
            "hunger": self.hunger,
            "thirst": self.thirst,
            "energy": self.energy,
            "comfort": self.comfort,
            "stress": self.stress,
            "curiosity": self.curiosity,
        }
        return {k: bool(hr[k][0] <= v <= hr[k][1]) for k, v in vals.items()}

    def step(
        self,
        dt_sec: float,
        *,
        is_eating: bool = False,
        is_drinking: bool = False,
        is_sleeping: bool = False,
        is_sheltered: bool = False,
        is_running_wheel: bool = False,
        is_exploring: bool = False,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Advances the homeostatic drives by `dt_sec` seconds and returns:
          `(total_homeostatic_reward, per_drive_reward_terms)`
        where `reward_k = (dev_before_k - dev_after_k)`.
        """
        dev_before = self.per_drive_squared_deviations()

        dt_hours = dt_sec / 3600.0
        rates = self.cfg["passive_rates_per_hour"]
        acts = self.cfg["action_effects_per_second"]
        daylight = self.is_daylight()

        # 1. Circadian phase progression (86,400 s per 24h cycle)
        self.circadian_phase = float(
            (self.circadian_phase + dt_sec / self.cfg["circadian"]["seconds_per_day"]) % 1.0
        )

        # 2. Hunger & Thirst passive rise + active eating/drinking reduction
        h_rate = rates["hunger_rise_asleep"] if is_sleeping else rates["hunger_rise_awake"]
        t_rate = rates["thirst_rise_asleep"] if is_sleeping else rates["thirst_rise_awake"]
        self.hunger += h_rate * dt_hours
        self.thirst += t_rate * dt_hours

        if is_eating:
            self.hunger -= acts["eat_hunger_reduction"] * dt_sec
        if is_drinking:
            self.thirst -= acts["drink_thirst_reduction"] * dt_sec

        # 3. Energy dynamics (crepuscular/nocturnal: daytime awake drains 1.25x faster)
        if is_sleeping:
            sleep_boost = 1.25 if daylight else 1.0
            self.energy += rates["energy_recovery_asleep"] * sleep_boost * dt_hours
        else:
            day_penalty = 1.25 if daylight else 1.0
            self.energy -= rates["energy_decay_awake"] * day_penalty * dt_hours
            if is_running_wheel:
                self.energy -= acts["wheel_energy_cost"] * dt_sec

        # 4. Comfort & Stress dynamics (sheltered inside hideout/tunnel vs exposed)
        if is_sheltered or is_sleeping:
            self.comfort += rates["comfort_recovery_sheltered"] * dt_hours
            self.stress -= rates["stress_decay_sheltered"] * dt_hours
        else:
            self.comfort -= rates["comfort_decay_exposed"] * dt_hours
            if daylight:
                self.stress += rates["stress_rise_exposed_daylight"] * dt_hours
            else:
                self.stress -= 0.25 * rates["stress_decay_sheltered"] * dt_hours

        # High hunger or thirst elevates stress
        if self.hunger > 0.65 or self.thirst > 0.60:
            self.stress += 0.08 * dt_hours

        # 5. Curiosity dynamics
        if is_sleeping:
            self.curiosity -= rates["curiosity_decay_asleep"] * dt_hours
        else:
            self.curiosity += rates["curiosity_rise_awake"] * dt_hours
            if is_running_wheel:
                self.curiosity -= acts["wheel_curiosity_reduction"] * dt_sec
                self.stress -= acts["wheel_stress_reduction"] * dt_sec
            elif is_exploring:
                self.curiosity -= acts["explore_curiosity_reduction"] * dt_sec

        self._clamp_all()

        dev_after = self.per_drive_squared_deviations()
        per_drive_rewards = {k: float(dev_before[k] - dev_after[k]) for k in dev_before}
        total_reward = float(sum(per_drive_rewards.values()))
        return total_reward, per_drive_rewards
