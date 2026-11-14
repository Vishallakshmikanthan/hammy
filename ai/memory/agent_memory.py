"""
HAMMY — P1.4: Integrated Agent Cognitive Memory System (`ai/memory/agent_memory.py`).
Orchestrates:
  1. Per-object value estimates, confidence, and recency (`ObjectMemory`).
  2. Coarse 2D spatial familiarity grid (`SpatialFamiliarityGrid`).
  3. Feature extraction yielding a deterministic 28-dimensional normalized memory vector.
  4. Conversion to versioned Pydantic contract `MemoryStateV2`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from contracts.schemas import MemoryStateV2, ObservationV1, ObservationV2
from ai.memory.object_memory import ObjectMemory
from ai.memory.spatial_grid import SpatialFamiliarityGrid


# Standard order of key habitat landmarks matching SMDP environment
DEFAULT_PROPS_ORDER = [
    "prop_bowl_main",
    "prop_bottle_main",
    "prop_hideout_main",
    "prop_tunnel_main",
    "prop_wheel_main",
    "prop_chew_block_main",
]

# Standard interaction radii matching simulation/habitats/v1.json
OBJECT_RADII = {
    "prop_bowl_main": 0.055,
    "prop_bottle_main": 0.050,
    "prop_hideout_main": 0.090,
    "prop_tunnel_main": 0.075,
    "prop_wheel_main": 0.080,
    "prop_chew_block_main": 0.050,
}


class AgentMemory:
    """
    Unified cognitive memory maintaining per-object appraisals and spatial familiarity.
    """

    def __init__(
        self,
        props_order: Optional[List[str]] = None,
        nx: int = 8,
        ny: int = 4,
        spatial_decay_rate: float = 0.0003,
        object_confidence_decay_rate: float = 0.001,
        object_value_decay_rate: float = 0.0005,
    ):
        self.props_order = list(props_order or DEFAULT_PROPS_ORDER)
        self.spatial = SpatialFamiliarityGrid(nx=nx, ny=ny, decay_rate=spatial_decay_rate)

        self.object_confidence_decay_rate = object_confidence_decay_rate
        self.object_value_decay_rate = object_value_decay_rate

        self.objects: Dict[str, ObjectMemory] = {}
        self._init_objects()

    def _init_objects(self):
        self.objects = {
            oid: ObjectMemory(
                object_id=oid,
                initial_value=0.0,
                initial_confidence=0.10,
                value_decay_rate=self.object_value_decay_rate,
                confidence_decay_rate=self.object_confidence_decay_rate,
                recency_tau_sec=300.0,
            )
            for oid in self.props_order
        }

    def reset(self) -> None:
        """Resets both spatial familiarity and object appraisal memories."""
        self.spatial.reset()
        self._init_objects()

    def update(
        self,
        obs: ObservationV1 | ObservationV2,
        dt_sec: float,
        reward: float = 0.0,
        interactions: Optional[Dict[str, bool]] = None,
    ) -> None:
        """
        Updates agent memory given a new observation and elapsed step time.
        """
        pos_xy = (obs.position_xyz[0], obs.position_xyz[1])
        dt = float(max(0.0, dt_sec))

        # 1. Update spatial familiarity grid
        self.spatial.update(pos_xy, dt)

        # 2. Map observed objects and proximity
        obj_map = {o.object_id: o for o in obs.nearby_objects}
        interact_map = interactions or {}

        for oid, mem in self.objects.items():
            is_at_object = False
            observed_utility = 0.0

            if oid in obj_map:
                o = obj_map[oid]
                rad = OBJECT_RADII.get(oid, 0.06)

                # Determine if agent is physically interacting or within stopping distance
                if o.distance_m <= rad:
                    is_at_object = True
                    # Estimate utility based on reward received or interaction success
                    if oid == "prop_bowl_main" and interact_map.get("eating", False):
                        observed_utility = max(0.5, reward * 5.0)
                    elif oid == "prop_bottle_main" and interact_map.get("drinking", False):
                        observed_utility = max(0.5, reward * 5.0)
                    elif oid == "prop_hideout_main" and (obs.inside_hideout or interact_map.get("sleeping", False)):
                        observed_utility = max(0.4, reward * 4.0)
                    elif oid == "prop_wheel_main" and obs.on_wheel:
                        observed_utility = max(0.3, reward * 3.0)
                    else:
                        observed_utility = max(0.1, reward)

                    # Compute absolute coordinates of the object
                    abs_obj_x = pos_xy[0] + o.rel_pos_xy[0]
                    abs_obj_y = pos_xy[1] + o.rel_pos_xy[1]
                    mem.record_visit((abs_obj_x, abs_obj_y), observed_utility, dt)

            if not is_at_object:
                mem.step_decay(dt)

    def get_feature_vector(self, pos_xy: Tuple[float, float] | List[float] | np.ndarray) -> np.ndarray:
        """
        Extracts a 28-dimensional normalized feature vector from memory:
          - 6 objects * 3 features (value, confidence, recency) = 18 floats
          - Current cell familiarity = 1 float
          - Mean habitat familiarity = 1 float
          - 4x2 coarse sector familiarities = 8 floats
        Total = 28 floats, all bounded and float32.
        """
        feats = []

        # 1. Per-object features (18 floats)
        for oid in self.props_order:
            if oid in self.objects:
                mem = self.objects[oid]
                val = float(np.clip(mem.estimated_value, -1.0, 1.0))
                conf = float(np.clip(mem.confidence, 0.0, 1.0))
                rec = float(np.clip(mem.recency_normalized, 0.0, 1.0))
                feats.extend([val, conf, rec])
            else:
                feats.extend([0.0, 0.0, 1.0])

        # 2. Spatial familiarity features (10 floats)
        cur_fam = float(np.clip(self.spatial.get_current_familiarity(pos_xy), 0.0, 1.0))
        mean_fam = float(np.clip(self.spatial.get_mean_familiarity(), 0.0, 1.0))
        coarse_sec = self.spatial.get_coarse_sectors()  # shape (8,)

        feats.append(cur_fam)
        feats.append(mean_fam)
        feats.extend(coarse_sec.tolist())

        arr = np.array(feats, dtype=np.float32)
        assert len(arr) == 28, f"Expected 28 memory features, got {len(arr)}"
        return arr

    def to_contract(self, obs: ObservationV1 | ObservationV2) -> MemoryStateV2:
        pos_xy = (obs.position_xyz[0], obs.position_xyz[1])
        item_contracts = [self.objects[oid].to_contract() for oid in self.props_order if oid in self.objects]
        spatial_contract = self.spatial.to_contract(pos_xy)
        return MemoryStateV2(
            object_memories=item_contracts,
            spatial=spatial_contract,
        )

