"""
HAMMY — P1.4: Per-Object Value Estimates, Confidence, Decay & Recency (`ai/memory/object_memory.py`).
Implements:
  - Running mean value estimates of interaction utility / rewards with exponential weighting.
  - Confidence scoring in [0, 1] that increases with direct interaction and decays over time.
  - Recency tracking: continuous seconds since last visit, plus normalized recency in [0, 1].
  - Value decay: unvisited object value estimates regress towards neutral prior over time.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from contracts.schemas import ObjectMemoryItemV2


class ObjectMemory:
    """
    Cognitive memory for a single habitat object or landmark.
    Tracks:
      - `estimated_value`: running mean utility observed at this object.
      - `confidence`: confidence in the estimate in [0, 1].
      - `time_since_last_visit_sec`: continuous elapsed seconds since last physical proximity/interaction.
      - `last_known_pos_xy`: last confirmed 2D position.
    """

    def __init__(
        self,
        object_id: str,
        initial_value: float = 0.0,
        initial_confidence: float = 0.1,
        value_decay_rate: float = 0.0005,      # Half-life ~1386 s (~23 min)
        confidence_decay_rate: float = 0.001,   # Half-life ~693 s (~11 min)
        recency_tau_sec: float = 300.0,         # Recency scale (5 minutes)
        update_alpha: float = 0.25,             # Exponential moving average learning rate
    ):
        self.object_id = str(object_id)
        self.estimated_value = float(initial_value)
        self.confidence = float(np.clip(initial_confidence, 0.0, 1.0))
        self.time_since_last_visit_sec = 0.0
        self.last_known_pos_xy: Optional[List[float]] = None

        self.value_decay_rate = float(value_decay_rate)
        self.confidence_decay_rate = float(confidence_decay_rate)
        self.recency_tau_sec = float(recency_tau_sec)
        self.update_alpha = float(update_alpha)

    def record_visit(
        self,
        pos_xy: Tuple[float, float] | List[float] | np.ndarray,
        observed_value: float,
        dt_sec: float = 1.0,
    ) -> None:
        """
        Called when the agent is physically present at the object.
        Updates running mean value, boosts confidence, resets recency, and records 2D position.
        """
        self.time_since_last_visit_sec = 0.0
        self.last_known_pos_xy = [round(float(pos_xy[0]), 4), round(float(pos_xy[1]), 4)]

        # Exponential moving average update
        self.estimated_value = (
            (1.0 - self.update_alpha) * self.estimated_value
            + self.update_alpha * float(observed_value)
        )

        # Boost confidence per visit (saturating at 1.0)
        self.confidence = min(1.0, self.confidence + 0.30)

    def step_decay(self, dt_sec: float) -> None:
        """
        Called on every simulation step when the agent is NOT at this object.
        Increments elapsed time and applies exponential temporal decay to confidence and value.
        """
        dt = float(max(0.0, dt_sec))
        self.time_since_last_visit_sec += dt

        # Confidence decay
        self.confidence = max(
            0.0,
            float(self.confidence * math.exp(-self.confidence_decay_rate * dt))
        )

        # Value estimate decay towards 0.0 neutral prior
        self.estimated_value = float(
            self.estimated_value * math.exp(-self.value_decay_rate * dt)
        )

    @property
    def recency_normalized(self) -> float:
        """
        Normalized recency in [0, 1].
        0.0 = visited right now; 1.0 = visited infinitely long ago (or never).
        """
        return float(1.0 - math.exp(-self.time_since_last_visit_sec / self.recency_tau_sec))

    def to_contract(self) -> ObjectMemoryItemV2:
        return ObjectMemoryItemV2(
            object_id=self.object_id,
            estimated_value=round(self.estimated_value, 5),
            confidence=round(self.confidence, 4),
            time_since_last_visit_sec=round(self.time_since_last_visit_sec, 2),
            recency_normalized=round(self.recency_normalized, 4),
            last_known_pos_xy=self.last_known_pos_xy,
        )

    def to_dict(self) -> Dict[str, Any]:
        return self.to_contract().model_dump()

