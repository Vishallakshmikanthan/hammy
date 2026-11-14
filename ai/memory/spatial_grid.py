"""
HAMMY — P1.4: Coarse Spatial Familiarity Grid (`ai/memory/spatial_grid.py`).
Implements:
  - 8x4 2D spatial grid covering the habitat floor: x in [-0.46, +0.46] m, y in [-0.21, +0.21] m.
  - Cell-level visit time accumulation and familiarity saturation in [0, 1].
  - Continuous temporal decay of unvisited territory familiarity.
  - Coarse 4x2 sector aggregation (8 floats) for compact neural network input.
  - Identification of current cell familiarity and least familiar territory (exploration targets).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple
import numpy as np

from contracts.schemas import SpatialMemoryV2


class SpatialFamiliarityGrid:
    """
    2D spatial familiarity map for the hamster habitat.
    Grid shape: (nx=8, ny=4) = 32 cells.
    Bounds: x in [-0.46, +0.46] m, y in [-0.21, +0.21] m.
    Each cell has dimensions dx = 0.115 m, dy = 0.105 m (~1 hamster body length).
    """

    def __init__(
        self,
        nx: int = 8,
        ny: int = 4,
        x_min: float = -0.46,
        x_max: float = 0.46,
        y_min: float = -0.21,
        y_max: float = 0.21,
        visit_saturation_sec: float = 30.0,
        decay_rate: float = 0.0003,  # Half-life ~2310 s (~38.5 min)
    ):
        self.nx = int(nx)
        self.ny = int(ny)
        self.x_min = float(x_min)
        self.x_max = float(x_max)
        self.y_min = float(y_min)
        self.y_max = float(y_max)
        self.visit_saturation_sec = float(visit_saturation_sec)
        self.decay_rate = float(decay_rate)

        # Total accumulated visit time per cell (seconds)
        self.visit_times = np.zeros((self.nx, self.ny), dtype=np.float64)

    def reset(self) -> None:
        self.visit_times.fill(0.0)

    def get_cell_index(self, pos_xy: Tuple[float, float] | List[float] | np.ndarray) -> Tuple[int, int]:
        """Maps continuous 2D coordinates (x, y) into discrete grid cell indices (ix, iy)."""
        x = float(np.clip(pos_xy[0], self.x_min, self.x_max))
        y = float(np.clip(pos_xy[1], self.y_min, self.y_max))

        u = (x - self.x_min) / max(1e-6, self.x_max - self.x_min)
        v = (y - self.y_min) / max(1e-6, self.y_max - self.y_min)

        ix = int(min(self.nx - 1, max(0, int(u * self.nx))))
        iy = int(min(self.ny - 1, max(0, int(v * self.ny))))
        return ix, iy

    def get_cell_center(self, ix: int, iy: int) -> Tuple[float, float]:
        """Returns the continuous 2D center coordinates (x, y) of grid cell (ix, iy)."""
        dx = (self.x_max - self.x_min) / self.nx
        dy = (self.y_max - self.y_min) / self.ny
        x = self.x_min + (ix + 0.5) * dx
        y = self.y_min + (iy + 0.5) * dy
        return float(x), float(y)

    def update(
        self,
        pos_xy: Tuple[float, float] | List[float] | np.ndarray,
        dt_sec: float,
    ) -> Tuple[int, int]:
        """
        Updates the spatial familiarity grid:
          1. Decays visit times across the entire grid.
          2. Adds elapsed dt_sec to the cell currently occupied by the agent.
        """
        dt = float(max(0.0, dt_sec))
        if dt > 0.0 and self.decay_rate > 0.0:
            self.visit_times *= math.exp(-self.decay_rate * dt)

        ix, iy = self.get_cell_index(pos_xy)
        self.visit_times[ix, iy] += dt
        return ix, iy

    @property
    def familiarity_matrix(self) -> np.ndarray:
        """
        Normalized familiarity matrix of shape (nx, ny) in [0.0, 1.0].
        Computed via saturating exponential response: 1 - exp(-T / T_sat).
        """
        return 1.0 - np.exp(-self.visit_times / max(1e-6, self.visit_saturation_sec))

    def get_current_familiarity(self, pos_xy: Tuple[float, float] | List[float] | np.ndarray) -> float:
        """Returns the familiarity score [0, 1] of the agent's current location."""
        ix, iy = self.get_cell_index(pos_xy)
        fam = self.familiarity_matrix
        return float(fam[ix, iy])

    def get_mean_familiarity(self) -> float:
        """Returns the average familiarity across all 32 grid cells in [0, 1]."""
        return float(np.mean(self.familiarity_matrix))

    def get_coarse_sectors(self) -> np.ndarray:
        """
        Aggregates the 8x4 fine grid into 4x2 coarse sectors (8 floats) by 2x2 average pooling.
        Sectors layout:
          Left to Right: 4 columns
          Bottom to Top: 2 rows
        Returns shape (8,) float32 vector in [0.0, 1.0].
        """
        fam = self.familiarity_matrix
        # 8x4 reshaped to (4, 2, 2, 2) and averaged over axis=(1, 3)
        coarse = fam.reshape(4, 2, 2, 2).mean(axis=(1, 3))
        return coarse.flatten().astype(np.float32)

    def get_least_familiar_cell(self) -> Tuple[Tuple[int, int], Tuple[float, float], float]:
        """
        Identifies the cell with the lowest familiarity score.
        Returns ((ix, iy), (x, y), min_familiarity).
        Useful for guiding exploratory foraging when habitat changes.
        """
        fam = self.familiarity_matrix
        idx = np.unravel_index(np.argmin(fam), fam.shape)
        ix, iy = int(idx[0]), int(idx[1])
        pos_xy = self.get_cell_center(ix, iy)
        return (ix, iy), pos_xy, float(fam[ix, iy])

    def to_contract(self, pos_xy: Tuple[float, float] | List[float] | np.ndarray) -> SpatialMemoryV2:
        ix, iy = self.get_cell_index(pos_xy)
        coarse = self.get_coarse_sectors().tolist()
        return SpatialMemoryV2(
            grid_shape=[self.nx, self.ny],
            current_cell_idx=[ix, iy],
            current_cell_familiarity=round(self.get_current_familiarity(pos_xy), 4),
            mean_familiarity=round(self.get_mean_familiarity(), 4),
            coarse_sectors=[round(float(v), 4) for v in coarse],
        )

