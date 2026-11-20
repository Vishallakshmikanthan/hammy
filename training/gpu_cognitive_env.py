"""
HAMMY — Pure PyTorch-CUDA Vectorized Batched Syrian Hamster Habitat Environment.

Runs N=2,048+ parallel Syrian hamster habitats directly on the RTX 5070 GPU at >500k steps/s,
faithfully matching `ai/cognition/drives.py` + `ai/cognition/cognitive_brain.py` (`ObservationV3`, 96 dims)
across all 16 naturalistic ethogram & social taming skills:
  - Nocturnal circadian rhythm & homeostatic drive regulation
  - Cheek-pouch foraging -> hideout nest hoarding loop
  - Spatial 4x2 familiarity memory + per-object recency/value memory
  - Random mid-episode habitat rearrangements, dynamic shelf props & offered treats
  - Diverse synthetic parent agents (patient treat-givers vs sudden premature petters)
    so organic non-forced taming (`hide -> cautious_sniff -> accept_petting`) emerges purely from RL!
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch

from ai.cognition.cognitive_brain import (
    COGNITIVE_SKILLS_V2,
    CORE_PROP_IDS,
    DEFAULT_CORE_PROP_POS,
    NUM_COGNITIVE_SKILLS,
    OBS_V3_DIM,
    SKILL_BASE_DURATIONS_SEC,
    SKILL_TO_IDX,
)


@dataclass
class GPUHabitatConfig:
    num_envs: int = 2048
    episode_steps: int = 256  # ~4–6 simulated days per episode
    enable_memory: bool = True
    domain_randomization: bool = True
    device: str = "cuda"


class GPUHamsterHabitatBatch:
    """Vectorized PyTorch CUDA simulator of N parallel Syrian hamster habitats."""

    def __init__(self, cfg: GPUHabitatConfig = GPUHabitatConfig(), seed: int = 42) -> None:
        self.cfg = cfg
        self.N = int(cfg.num_envs)
        self.device = torch.device(cfg.device if torch.cuda.is_available() else "cpu")
        self.gen = torch.Generator(device=self.device)
        self.gen.manual_seed(seed)

        # Static skill duration lookup [16]
        self.skill_durations = torch.tensor(
            [SKILL_BASE_DURATIONS_SEC[s] for s in COGNITIVE_SKILLS_V2],
            dtype=torch.float32,
            device=self.device,
        )

        # Default core prop XY positions [6, 2]
        self.default_prop_xy = torch.tensor(
            [[DEFAULT_CORE_PROP_POS[pid][0], DEFAULT_CORE_PROP_POS[pid][1]] for pid in CORE_PROP_IDS],
            dtype=torch.float32,
            device=self.device,
        )

        # Set points for homeostatic potential D(s) = sum_k w_k * (d_k - sp_k)^2
        # Drives: [hunger, thirst, energy, comfort, stress, curiosity]
        # Energy set-point at 0.72 so nocturnal wheel running from 0.85->0.72 REDUCES deviation!
        # Curiosity set-point at 0.06 so satisfying curiosity via wheel/explore/tunnel/digging rewards cleanly!
        self.set_points = torch.tensor(
            [0.12, 0.10, 0.72, 0.82, 0.06, 0.06],
            dtype=torch.float32,
            device=self.device,
        )
        self.drive_weights = torch.tensor(
            [1.65, 1.75, 1.35, 1.15, 1.50, 1.10],
            dtype=torch.float32,
            device=self.device,
        )

        # Healthy ranges [min, max]
        self.healthy_low = torch.tensor([0.0, 0.0, 0.35, 0.50, 0.0, 0.0], device=self.device)
        self.healthy_high = torch.tensor([0.45, 0.40, 1.0, 1.0, 0.35, 0.65], device=self.device)

        # Pre-allocate tensors
        self._alloc_state()
        self.reset_all()

    def _alloc_state(self) -> None:
        N, dev = self.N, self.device
        # 7 drives: hunger, thirst, energy, comfort, stress, curiosity, familiarity
        self.drives = torch.zeros((N, 7), dtype=torch.float32, device=dev)
        self.circadian = torch.zeros(N, dtype=torch.float32, device=dev)
        self.cheek_pouch = torch.zeros(N, dtype=torch.float32, device=dev)
        self.nest_hoard = torch.zeros(N, dtype=torch.float32, device=dev)
        self.startle = torch.zeros(N, dtype=torch.float32, device=dev)

        # Agent kinematics
        self.pos_xy = torch.zeros((N, 2), dtype=torch.float32, device=dev)
        self.yaw = torch.zeros(N, dtype=torch.float32, device=dev)
        self.vel_xy = torch.zeros((N, 2), dtype=torch.float32, device=dev)
        self.inside_hideout = torch.zeros(N, dtype=torch.bool, device=dev)
        self.inside_tunnel = torch.zeros(N, dtype=torch.bool, device=dev)
        self.on_wheel = torch.zeros(N, dtype=torch.bool, device=dev)

        # Core props [N, 6, 2] & resources [N, 6]
        self.prop_xy = torch.zeros((N, 6, 2), dtype=torch.float32, device=dev)
        self.prop_res = torch.ones((N, 6), dtype=torch.float32, device=dev)

        # Dynamic shelf stimuli
        self.has_offered_food = torch.zeros(N, dtype=torch.bool, device=dev)
        self.offered_food_xy = torch.zeros((N, 2), dtype=torch.float32, device=dev)
        self.has_novel_prop = torch.zeros(N, dtype=torch.bool, device=dev)
        self.novel_prop_xy = torch.zeros((N, 2), dtype=torch.float32, device=dev)
        self.novel_prop_inspected = torch.zeros(N, dtype=torch.bool, device=dev)

        # Cognitive memory: per-object [est_value, recency] + 4x2 spatial familiarity sectors
        self.obj_mem_val = torch.full((N, 6), 0.5, dtype=torch.float32, device=dev)
        self.obj_mem_rec = torch.full((N, 6), 0.5, dtype=torch.float32, device=dev)
        self.spatial_sectors = torch.full((N, 8), 0.4, dtype=torch.float32, device=dev)

        # Parent interaction stimulus & owner style
        self.parent_active = torch.zeros(N, dtype=torch.bool, device=dev)
        self.parent_action = torch.zeros(N, dtype=torch.long, device=dev)  # 0=none, 1=treat, 2=pet, 3=call
        self.owner_gentleness = torch.full((N,), 0.7, dtype=torch.float32, device=dev)
        self.trust_trend = torch.zeros(N, dtype=torch.float32, device=dev)
        self.time_since_parent = torch.ones(N, dtype=torch.float32, device=dev)

        # History & temperament
        self.prev_skill = torch.full((N,), SKILL_TO_IDX["explore_area"], dtype=torch.long, device=dev)
        self.prev_skill_streak = torch.zeros(N, dtype=torch.float32, device=dev)
        self.boldness = torch.full((N,), 0.55, dtype=torch.float32, device=dev)
        self.wheel_affinity = torch.full((N,), 0.65, dtype=torch.float32, device=dev)

        # Episode tracking + biological per-skill dopaminergic satiation (prevents robotic single-skill spam!)
        self.step_count = torch.zeros(N, dtype=torch.long, device=dev)
        self.sim_time = torch.zeros(N, dtype=torch.float32, device=dev)
        self.recent_eat_or_dig = torch.zeros(N, dtype=torch.float32, device=dev)
        self.recent_nested = torch.zeros(N, dtype=torch.float32, device=dev)
        self.skill_satiation = torch.zeros((N, NUM_COGNITIVE_SKILLS), dtype=torch.float32, device=dev)

    def _rand(self, shape: Tuple[int, ...]) -> torch.Tensor:
        return torch.rand(shape, generator=self.gen, device=self.device, dtype=torch.float32)

    def reset_envs(self, mask: torch.Tensor) -> None:
        idx = torch.nonzero(mask, as_tuple=False).squeeze(-1)
        m = int(idx.numel())
        if m == 0:
            return

        # Diverse initial physiological states so policy sees full state space
        self.drives[idx, 0] = 0.08 + 0.45 * self._rand((m,))  # hunger
        self.drives[idx, 1] = 0.08 + 0.40 * self._rand((m,))  # thirst
        self.drives[idx, 2] = 0.45 + 0.50 * self._rand((m,))  # energy
        self.drives[idx, 3] = 0.55 + 0.40 * self._rand((m,))  # comfort
        self.drives[idx, 4] = 0.05 + 0.45 * self._rand((m,))  # stress
        self.drives[idx, 5] = 0.15 + 0.55 * self._rand((m,))  # curiosity
        self.drives[idx, 6] = self._rand((m,))                # familiarity (full 0..1 taming range!)

        self.circadian[idx] = self._rand((m,))
        self.cheek_pouch[idx] = 0.4 * self._rand((m,)) * (self._rand((m,)) < 0.35).float()
        self.nest_hoard[idx] = 0.10 + 0.40 * self._rand((m,))
        self.startle[idx] = 0.3 * self._rand((m,)) * (self._rand((m,)) < 0.15).float()

        self.pos_xy[idx, 0] = (self._rand((m,)) * 2.0 - 1.0) * 0.34
        self.pos_xy[idx, 1] = (self._rand((m,)) * 2.0 - 1.0) * 0.14
        self.yaw[idx] = (self._rand((m,)) * 2.0 - 1.0) * math.pi
        self.vel_xy[idx] = 0.0
        self.inside_hideout[idx] = False
        self.inside_tunnel[idx] = False
        self.on_wheel[idx] = False

        # Core props with slight domain randomization
        base_xy = self.default_prop_xy.unsqueeze(0).expand(m, 6, 2).clone()
        if self.cfg.domain_randomization:
            jitter = (self._rand((m, 6, 2)) * 2.0 - 1.0) * 0.04
            base_xy = base_xy + jitter
            base_xy[..., 0].clamp_(-0.42, 0.42)
            base_xy[..., 1].clamp_(-0.18, 0.18)
        self.prop_xy[idx] = base_xy
        self.prop_res[idx] = 1.0
        self.prop_res[idx, 0] = 0.35 + 0.65 * self._rand((m,))  # bowl food
        self.prop_res[idx, 1] = 0.40 + 0.60 * self._rand((m,))  # bottle water

        self.has_offered_food[idx] = self._rand((m,)) < 0.15
        self.offered_food_xy[idx, 0] = (self._rand((m,)) * 2.0 - 1.0) * 0.32
        self.offered_food_xy[idx, 1] = (self._rand((m,)) * 2.0 - 1.0) * 0.14

        self.has_novel_prop[idx] = self._rand((m,)) < 0.20
        self.novel_prop_xy[idx, 0] = (self._rand((m,)) * 2.0 - 1.0) * 0.32
        self.novel_prop_xy[idx, 1] = (self._rand((m,)) * 2.0 - 1.0) * 0.14
        self.novel_prop_inspected[idx] = False

        self.obj_mem_val[idx] = 0.5
        self.obj_mem_rec[idx] = 0.35 + 0.45 * self._rand((m, 6))
        self.spatial_sectors[idx] = 0.25 + 0.35 * self._rand((m, 8))

        self.parent_active[idx] = False
        self.parent_action[idx] = 0
        self.owner_gentleness[idx] = 0.25 + 0.75 * self._rand((m,))
        self.trust_trend[idx] = 0.0
        self.time_since_parent[idx] = 1.0

        self.prev_skill[idx] = SKILL_TO_IDX["explore_area"]
        self.prev_skill_streak[idx] = 0.0
        self.boldness[idx] = 0.25 + 0.65 * self._rand((m,))
        self.wheel_affinity[idx] = 0.30 + 0.65 * self._rand((m,))

        self.step_count[idx] = 0
        self.sim_time[idx] = 0.0
        self.recent_eat_or_dig[idx] = 0.0
        self.recent_nested[idx] = 0.0
        self.skill_satiation[idx] = 0.0

    def reset_all(self) -> Tuple[torch.Tensor, torch.Tensor]:
        self.reset_envs(torch.ones(self.N, dtype=torch.bool, device=self.device))
        return self.get_obs(), self.get_action_mask()

    def _homeo_deviation(self) -> torch.Tensor:
        diff = self.drives[:, :6] - self.set_points.unsqueeze(0)
        return torch.sum(self.drive_weights.unsqueeze(0) * (diff * diff), dim=-1)

    def _sector_index(self, xy: torch.Tensor) -> torch.Tensor:
        col = torch.clamp(((xy[:, 0] + 0.46) / 0.92 * 4.0).long(), 0, 3)
        row = torch.clamp(((xy[:, 1] + 0.21) / 0.42 * 2.0).long(), 0, 1)
        return col * 2 + row  # [0..7]

    def _least_familiar_xy(self) -> torch.Tensor:
        min_sec = torch.argmin(self.spatial_sectors, dim=-1)  # [N]
        col = (min_sec // 2).float()
        row = (min_sec % 2).float()
        tx = -0.46 + (col + 0.5) * (0.92 / 4.0)
        ty = -0.21 + (row + 0.5) * (0.42 / 2.0)
        return torch.stack([tx, ty], dim=-1)

    def get_action_mask(self) -> torch.Tensor:
        mask = torch.ones((self.N, NUM_COGNITIVE_SKILLS), dtype=torch.bool, device=self.device)

        bowl_xy = self.prop_xy[:, 0, :]
        bowl_lvl = self.prop_res[:, 0]
        bottle_lvl = self.prop_res[:, 1]

        has_food = (bowl_lvl > 0.02) | self.has_offered_food
        food_xy = torch.where(self.has_offered_food.unsqueeze(-1), self.offered_food_xy, bowl_xy)
        dist_food = torch.linalg.norm(food_xy - self.pos_xy, dim=-1)

        mask[:, SKILL_TO_IDX["approach_food"]] = has_food & (dist_food > 0.08)
        can_eat_hoard = self.inside_hideout & (self.nest_hoard > 0.05)
        mask[:, SKILL_TO_IDX["eat"]] = has_food | can_eat_hoard
        mask[:, SKILL_TO_IDX["cheek_stuffing"]] = has_food & (self.cheek_pouch < 0.92)
        mask[:, SKILL_TO_IDX["unload_hoard"]] = self.cheek_pouch >= 0.15
        mask[:, SKILL_TO_IDX["drink"]] = bottle_lvl > 0.01
        mask[:, SKILL_TO_IDX["cautious_sniff"]] = self.parent_active
        mask[:, SKILL_TO_IDX["accept_petting"]] = self.parent_active
        return mask

    def get_obs(self) -> torch.Tensor:
        N, dev = self.N, self.device
        obs = torch.zeros((N, OBS_V3_DIM), dtype=torch.float32, device=dev)

        # [0..6] drives
        obs[:, 0:7] = self.drives

        # [7..12] circadian & physical body
        ang = 2.0 * math.pi * self.circadian
        is_day = ((self.circadian >= 0.29) & (self.circadian <= 0.79)).float()
        obs[:, 7] = torch.sin(ang)
        obs[:, 8] = torch.cos(ang)
        obs[:, 9] = is_day
        obs[:, 10] = self.cheek_pouch
        obs[:, 11] = self.nest_hoard
        obs[:, 12] = self.startle

        # [13..22] spatial & flags
        obs[:, 13] = torch.clamp(self.pos_xy[:, 0] / 0.50, -1.5, 1.5)
        obs[:, 14] = torch.clamp(self.pos_xy[:, 1] / 0.25, -1.5, 1.5)
        obs[:, 15] = torch.cos(self.yaw)
        obs[:, 16] = torch.sin(self.yaw)
        obs[:, 17] = torch.clamp(self.vel_xy[:, 0] / 0.30, -2.0, 2.0)
        obs[:, 18] = torch.clamp(self.vel_xy[:, 1] / 0.30, -2.0, 2.0)
        obs[:, 19] = self.inside_hideout.float()
        obs[:, 20] = self.inside_tunnel.float()
        obs[:, 21] = self.on_wheel.float()

        dist_off = torch.linalg.norm(self.offered_food_xy - self.pos_xy, dim=-1)
        obs[:, 22] = (self.has_offered_food & (dist_off <= 0.14)).float()

        # [23..46] 6 core props (24 floats)
        rel_props = self.prop_xy - self.pos_xy.unsqueeze(1)  # [N, 6, 2]
        dist_props = torch.linalg.norm(rel_props, dim=-1)     # [N, 6]
        for j in range(6):
            base = 23 + j * 4
            obs[:, base] = torch.clamp(rel_props[:, j, 0] / 0.50, -2.0, 2.0)
            obs[:, base + 1] = torch.clamp(rel_props[:, j, 1] / 0.25, -2.0, 2.0)
            obs[:, base + 2] = torch.clamp(dist_props[:, j] / 0.60, 0.0, 2.0)
            obs[:, base + 3] = self.prop_res[:, j]

        # [47..54] offered food & novel prop
        f_rel = self.offered_food_xy - self.pos_xy
        f_has = self.has_offered_food.float()
        obs[:, 47] = f_has
        obs[:, 48] = f_has * torch.clamp(f_rel[:, 0] / 0.50, -2.0, 2.0)
        obs[:, 49] = f_has * torch.clamp(f_rel[:, 1] / 0.25, -2.0, 2.0)
        obs[:, 50] = torch.where(self.has_offered_food, torch.clamp(dist_off / 0.60, 0.0, 2.0), torch.ones(N, device=dev))

        n_rel = self.novel_prop_xy - self.pos_xy
        n_dist = torch.linalg.norm(n_rel, dim=-1)
        n_has = self.has_novel_prop.float()
        obs[:, 51] = n_has
        obs[:, 52] = n_has * torch.clamp(n_rel[:, 0] / 0.50, -2.0, 2.0)
        obs[:, 53] = n_has * torch.clamp(n_rel[:, 1] / 0.25, -2.0, 2.0)
        obs[:, 54] = torch.where(self.has_novel_prop, torch.clamp(n_dist / 0.60, 0.0, 2.0), torch.ones(N, device=dev))

        # [55..70] cognitive memory (masked to neutral 0.5/0.0 when enable_memory=False for ablations)
        if self.cfg.enable_memory:
            for j in range(6):
                obs[:, 55 + j * 2] = self.obj_mem_val[:, j]
                obs[:, 55 + j * 2 + 1] = self.obj_mem_rec[:, j]
            sec_idx = self._sector_index(self.pos_xy)
            curr_fam = self.spatial_sectors.gather(1, sec_idx.unsqueeze(1)).squeeze(1)
            least_xy = self._least_familiar_xy()
            obs[:, 67] = curr_fam
            obs[:, 68] = self.spatial_sectors.mean(dim=-1)
            obs[:, 69] = torch.clamp((least_xy[:, 0] - self.pos_xy[:, 0]) / 0.50, -2.0, 2.0)
            obs[:, 70] = torch.clamp((least_xy[:, 1] - self.pos_xy[:, 1]) / 0.25, -2.0, 2.0)
        else:
            obs[:, 55:69] = 0.5

        # [71..76] parent interaction stimulus
        obs[:, 71] = self.parent_active.float()
        obs[:, 72] = (self.parent_active & (self.parent_action == 1)).float()
        obs[:, 73] = (self.parent_active & (self.parent_action == 2)).float()
        obs[:, 74] = (self.parent_active & (self.parent_action == 3)).float()
        obs[:, 75] = torch.clamp(self.trust_trend, -1.0, 1.0)
        obs[:, 76] = torch.clamp(self.time_since_parent, 0.0, 1.0)

        # [77..92] prev skill one-hot
        obs[:, 77:93].scatter_(1, self.prev_skill.unsqueeze(1), 1.0)

        # [93..95] streak & temperament
        obs[:, 93] = torch.clamp(self.prev_skill_streak / 6.0, 0.0, 1.0)
        obs[:, 94] = self.boldness
        obs[:, 95] = self.wheel_affinity
        return obs

    def step(
        self, actions: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, Dict[str, torch.Tensor]]:
        """Vectorized GPU SMDP transition for all N habitats simultaneously."""
        act = actions.long().view(self.N)
        dev_before = self._homeo_deviation()

        # Duration with natural stochastic jitter (±18%)
        dt_sec = self.skill_durations[act] * (0.82 + 0.36 * self._rand((self.N,)))
        dt_h = dt_sec / 3600.0
        is_day = (self.circadian >= 0.29) & (self.circadian <= 0.79)

        # Convenience boolean masks per chosen skill
        a_app_food = act == 0
        a_eat = act == 1
        a_stuff = act == 2
        a_unload = act == 3
        a_drink = act == 4
        a_explore = act == 5
        a_tunnel = act == 6
        a_wheel = act == 7
        a_dig = act == 8
        a_rear = act == 9
        a_groom = act == 10
        a_nest = act == 11
        a_rest = act == 12
        a_hide = act == 13
        a_sniff = act == 14
        a_pet = act == 15

        # ----------------------------------------------------------------------
        # 1. Spatial movement & physical state flags
        # ----------------------------------------------------------------------
        old_xy = self.pos_xy.clone()
        new_xy = self.pos_xy.clone()

        food_xy = torch.where(self.has_offered_food.unsqueeze(-1), self.offered_food_xy, self.prop_xy[:, 0, :])
        bottle_xy = self.prop_xy[:, 1, :]
        hideout_xy = self.prop_xy[:, 2, :]
        tunnel_xy = self.prop_xy[:, 3, :]
        wheel_xy = self.prop_xy[:, 4, :]

        # Explore navigates to novel prop (if present) or least familiar sector
        explore_target = torch.where(
            self.has_novel_prop.unsqueeze(-1),
            self.novel_prop_xy,
            self._least_familiar_xy(),
        )
        # Parent interaction zone at front-center of glass enclosure
        treat_zone_xy = torch.tensor([0.0, -0.15], dtype=torch.float32, device=self.device).unsqueeze(0).expand(self.N, 2)

        move_food = a_app_food | a_eat | a_stuff
        new_xy = torch.where(move_food.unsqueeze(-1), food_xy, new_xy)
        new_xy = torch.where((a_unload | a_nest | a_rest | a_hide).unsqueeze(-1), hideout_xy, new_xy)
        new_xy = torch.where(a_drink.unsqueeze(-1), bottle_xy, new_xy)
        new_xy = torch.where(a_tunnel.unsqueeze(-1), tunnel_xy, new_xy)
        new_xy = torch.where(a_wheel.unsqueeze(-1), wheel_xy, new_xy)
        new_xy = torch.where(a_explore.unsqueeze(-1), explore_target, new_xy)
        new_xy = torch.where((a_sniff | a_pet).unsqueeze(-1), treat_zone_xy, new_xy)

        # Small organic jitter around target
        jitter = (self._rand((self.N, 2)) * 2.0 - 1.0) * 0.025
        new_xy = new_xy + jitter * (~(a_rest | a_hide | a_wheel)).float().unsqueeze(-1)
        new_xy[:, 0].clamp_(-0.43, 0.43)
        new_xy[:, 1].clamp_(-0.18, 0.18)

        disp = new_xy - old_xy
        travel_dist = torch.linalg.norm(disp, dim=-1)
        self.pos_xy = new_xy
        moved = travel_dist > 0.01
        self.yaw = torch.where(moved, torch.atan2(disp[:, 1], disp[:, 0]), self.yaw)
        self.vel_xy = torch.where(moved.unsqueeze(-1), disp / torch.clamp(dt_sec.unsqueeze(-1), min=1.0), torch.zeros_like(disp))

        self.inside_hideout = a_unload | a_nest | a_rest | a_hide
        self.inside_tunnel = a_tunnel
        self.on_wheel = a_wheel
        is_sleeping = a_rest | a_nest
        is_sheltered = self.inside_hideout | self.inside_tunnel

        # ----------------------------------------------------------------------
        # 2. Homeostatic drive dynamics (calibrated to realistic Syrian biology)
        # ----------------------------------------------------------------------
        hunger = self.drives[:, 0]
        thirst = self.drives[:, 1]
        energy = self.drives[:, 2]
        comfort = self.drives[:, 3]
        stress = self.drives[:, 4]
        curiosity = self.drives[:, 5]
        familiarity = self.drives[:, 6]

        # Advance circadian phase
        self.circadian = (self.circadian + dt_sec / 86400.0) % 1.0
        self.sim_time += dt_sec

        # Passive physiological drift
        hunger = hunger + torch.where(is_sleeping, 0.028, 0.085) * dt_h
        thirst = thirst + torch.where(is_sleeping, 0.030, 0.095) * dt_h

        day_awake_mult = torch.where(is_day, 1.35, 1.0)
        sleep_boost = torch.where(is_day, 1.35, 0.95)
        nest_sleep_bonus = 1.0 + 0.20 * self.recent_nested
        energy = torch.where(
            is_sleeping,
            energy + 0.185 * sleep_boost * nest_sleep_bonus * dt_h,
            energy - 0.095 * day_awake_mult * dt_h - 0.012 * travel_dist,
        )

        # Comfort & Stress baseline
        comfort = torch.where(
            is_sheltered,
            comfort + 0.20 * dt_h,
            comfort - torch.where(is_day, 0.085, 0.042) * dt_h,
        )
        stress = torch.where(
            is_sheltered,
            stress - 0.18 * dt_h,
            stress + torch.where(is_day, 0.095, -0.025) * dt_h,
        )
        # High hunger/thirst elevates stress
        need_stress = ((hunger > 0.65) | (thirst > 0.60)).float()
        stress = stress + 0.12 * need_stress * dt_h

        # Curiosity rises naturally while awake, decays slowly asleep
        curiosity = torch.where(
            is_sleeping,
            curiosity - 0.03 * dt_h,
            curiosity + torch.where(is_day, 0.035, 0.125) * dt_h,
        )

        # ----------------------------------------------------------------------
        # 3. Skill-specific biological effects & resource interactions
        # ----------------------------------------------------------------------
        # Eating (from offered food, bowl, or nest hoard if inside hideout)
        ate_offered = a_eat & self.has_offered_food
        ate_bowl = a_eat & (~self.has_offered_food) & (self.prop_res[:, 0] > 0.02)
        ate_hoard = a_eat & (~ate_offered) & (~ate_bowl) & (self.nest_hoard > 0.05)
        ate_any = ate_offered | ate_bowl | ate_hoard

        hunger = torch.where(ate_any, hunger - 0.30, hunger)
        energy = torch.where(ate_any, energy + 0.04, energy)
        comfort = torch.where(ate_any, comfort + 0.05, comfort)
        self.has_offered_food = self.has_offered_food & (~ate_offered)
        self.prop_res[:, 0] = torch.clamp(self.prop_res[:, 0] - 0.10 * ate_bowl.float(), 0.0, 1.0)
        self.nest_hoard = torch.clamp(self.nest_hoard - 0.18 * ate_hoard.float(), 0.0, 1.0)

        # Cheek-pouch stuffing (natural Syrian hamster hoarding!)
        stuffed_off = a_stuff & self.has_offered_food
        stuffed_bowl = a_stuff & (~self.has_offered_food) & (self.prop_res[:, 0] > 0.02)
        stuffed_any = stuffed_off | stuffed_bowl
        self.cheek_pouch = torch.clamp(self.cheek_pouch + 0.35 * stuffed_any.float(), 0.0, 1.0)
        hunger = torch.where(stuffed_any, hunger - 0.08, hunger)
        self.has_offered_food = self.has_offered_food & (~stuffed_off)
        self.prop_res[:, 0] = torch.clamp(self.prop_res[:, 0] - 0.12 * stuffed_bowl.float(), 0.0, 1.0)

        # Unload hoard inside hideout
        unloaded_amt = torch.where(a_unload, self.cheek_pouch, torch.zeros_like(self.cheek_pouch))
        self.cheek_pouch = torch.where(a_unload, torch.zeros_like(self.cheek_pouch), self.cheek_pouch)
        self.nest_hoard = torch.clamp(self.nest_hoard + 0.70 * unloaded_amt, 0.0, 1.0)
        comfort = torch.where(a_unload, comfort + 0.12 * unloaded_amt, comfort)
        stress = torch.where(a_unload, stress - 0.06 * unloaded_amt, stress)

        # Drinking
        drank = a_drink & (self.prop_res[:, 1] > 0.01)
        thirst = torch.where(drank, thirst - 0.36, thirst)
        comfort = torch.where(drank, comfort + 0.04, comfort)
        self.prop_res[:, 1] = torch.clamp(self.prop_res[:, 1] - 0.06 * drank.float(), 0.0, 1.0)

        # Wheel running (real Syrian hamsters love nocturnal aerobic wheel sprints!)
        energy = torch.where(a_wheel, energy - 0.045, energy)
        curiosity = torch.where(a_wheel, curiosity - 0.24, curiosity)
        stress = torch.where(a_wheel, stress - 0.16, stress)
        comfort = torch.where(a_wheel, comfort + 0.08, comfort)

        # Exploring, tunneling, digging, bipedal rearing
        inspected_novel = a_explore & self.has_novel_prop
        curiosity = torch.where(a_explore, curiosity - torch.where(inspected_novel, 0.34, 0.22), curiosity)
        energy = torch.where(a_explore, energy - 0.025, energy)
        self.has_novel_prop = self.has_novel_prop & (~inspected_novel)

        curiosity = torch.where(a_tunnel, curiosity - 0.20, curiosity)
        stress = torch.where(a_tunnel, stress - 0.14, stress)
        comfort = torch.where(a_tunnel, comfort + 0.10, comfort)
        energy = torch.where(a_tunnel, energy - 0.020, energy)

        curiosity = torch.where(a_dig, curiosity - 0.22, curiosity)
        comfort = torch.where(a_dig, comfort + 0.11, comfort)
        stress = torch.where(a_dig, stress - 0.09, stress)
        energy = torch.where(a_dig, energy - 0.025, energy)

        curiosity = torch.where(a_rear, curiosity - 0.15, curiosity)
        self.startle = torch.clamp(self.startle - 0.30 * a_rear.float() - 0.18 * (a_hide | a_groom).float(), 0.0, 1.0)

        # Grooming (calms stress & refreshes comfort mainly after eating/digging or when stressed/uncomfortable)
        post_meal_groom = a_groom & (self.recent_eat_or_dig > 0.1)
        needs_groom = post_meal_groom | (stress > 0.18) | (comfort < 0.76)
        stress = torch.where(a_groom & needs_groom, stress - 0.12, stress)
        comfort = torch.where(a_groom & needs_groom, comfort + torch.where(post_meal_groom, 0.14, 0.07), comfort)
        energy = torch.where(a_groom, energy - 0.015, energy)

        # Nesting & resting
        comfort = torch.where(a_nest, comfort + 0.16, comfort)
        stress = torch.where(a_nest, stress - 0.10, stress)
        energy = torch.where(a_rest, energy + 0.20 * sleep_boost, energy)
        comfort = torch.where(a_rest, comfort + 0.10, comfort)
        stress = torch.where(a_rest, stress - 0.15, stress)

        # Hiding (strong stress relief when stressed/startled)
        stress = torch.where(a_hide, stress - 0.26, stress)
        comfort = torch.where(a_hide, comfort + 0.08, comfort)

        # ----------------------------------------------------------------------
        # 4. Non-forced parent interaction physics & operant conditioning!
        # ----------------------------------------------------------------------
        r_social = torch.zeros(self.N, dtype=torch.float32, device=self.device)
        p_act = self.parent_active
        is_treat = p_act & (self.parent_action == 1)
        is_gpet = p_act & (self.parent_action == 2)

        # Underlying latent readiness (biological trust state — policy must LEARN this!)
        readiness = familiarity + 0.22 * is_treat.float() + 0.15 * (self.boldness - 0.5) - 0.60 * stress - 0.40 * self.startle

        # If hamster chooses accept_petting while ready (high trust, low stress) -> rewarding calm bond!
        # If hamster chooses accept_petting while NOT ready -> startled stress spike (negative reward!)
        pet_ok = p_act & a_pet & (readiness >= 0.32)
        pet_forced_bad = p_act & a_pet & (readiness < 0.32)
        sniff_ok = p_act & a_sniff & (readiness >= 0.05) & (readiness < 0.55)
        sniff_scared = p_act & a_sniff & (readiness < 0.05)
        retreat_smart = p_act & a_hide & (readiness < 0.18)

        # Apply physiological effects of parent interaction outcome
        fam_before = familiarity.clone()
        familiarity = torch.where(pet_ok, familiarity + 0.10 * self.owner_gentleness, familiarity)
        stress = torch.where(pet_ok, stress - 0.16, stress)
        comfort = torch.where(pet_ok, comfort + 0.18, comfort)
        hunger = torch.where(pet_ok & is_treat, hunger - 0.15, hunger)
        r_social = r_social + 0.65 * pet_ok.float()

        stress = torch.where(pet_forced_bad, stress + 0.30, stress)
        comfort = torch.where(pet_forced_bad, comfort - 0.18, comfort)
        familiarity = torch.where(pet_forced_bad, familiarity - 0.05, familiarity)
        r_social = r_social - 0.80 * pet_forced_bad.float()

        familiarity = torch.where(sniff_ok, familiarity + torch.where(is_treat, 0.16, 0.10) * self.owner_gentleness, familiarity)
        stress = torch.where(sniff_ok, stress - 0.07, stress)
        curiosity = torch.where(sniff_ok, curiosity - 0.12, curiosity)
        hunger = torch.where(sniff_ok & is_treat, hunger - 0.10, hunger)
        r_social = r_social + 0.45 * sniff_ok.float()

        stress = torch.where(sniff_scared, stress + 0.16, stress)
        r_social = r_social - 0.35 * sniff_scared.float()

        familiarity = torch.where(retreat_smart & is_treat, familiarity + 0.08, familiarity)
        stress = torch.where(retreat_smart, stress - 0.12, stress)
        r_social = r_social + 0.38 * retreat_smart.float()

        # Ignoring a human hand right in front of the cage is biologically unlikely
        # (a real hamster reacts by retreating, cautiously sniffing, or accepting petting!)
        ignored_parent = p_act & (~(a_pet | a_sniff | a_hide))
        r_social = r_social - 0.45 * ignored_parent.float()
        # Slightly boost clear non-forced taming gradient so low->mid->high trust emerges sharply
        r_social = r_social + 0.35 * retreat_smart.float() + 0.35 * sniff_ok.float()

        # Update trust trend & clear consumed parent event
        self.trust_trend = torch.where(p_act, 0.6 * self.trust_trend + 0.4 * torch.clamp((familiarity - fam_before) * 5.0, -1.0, 1.0), 0.92 * self.trust_trend)
        self.parent_active = torch.zeros(self.N, dtype=torch.bool, device=self.device)
        self.parent_action = torch.zeros(self.N, dtype=torch.long, device=self.device)
        self.time_since_parent = torch.where(p_act, torch.zeros_like(self.time_since_parent), torch.clamp(self.time_since_parent + 0.08, 0.0, 1.0))

        # Clamp all drives to [0, 1]
        self.drives = torch.stack(
            [
                hunger.clamp(0.0, 1.0),
                thirst.clamp(0.0, 1.0),
                energy.clamp(0.0, 1.0),
                comfort.clamp(0.0, 1.0),
                stress.clamp(0.0, 1.0),
                curiosity.clamp(0.0, 1.0),
                familiarity.clamp(0.0, 1.0),
            ],
            dim=-1,
        )

        # ----------------------------------------------------------------------
        # 5. Update spatial & object memory
        # ----------------------------------------------------------------------
        sec_idx = self._sector_index(self.pos_xy)
        # Passive familiarity decay, active boost at current sector
        self.spatial_sectors = torch.clamp(self.spatial_sectors * (1.0 - 0.012 * dt_h.unsqueeze(-1)), 0.0, 1.0)
        cur_val = self.spatial_sectors.gather(1, sec_idx.unsqueeze(1))
        self.spatial_sectors.scatter_(1, sec_idx.unsqueeze(1), torch.clamp(cur_val + 0.24, 0.0, 1.0))

        # Object recency rises toward 1.0 over time, resets to 0 when visited
        self.obj_mem_rec = torch.clamp(self.obj_mem_rec + 0.15 * dt_h.unsqueeze(-1), 0.0, 1.0)
        dist_props = torch.linalg.norm(self.prop_xy - self.pos_xy.unsqueeze(1), dim=-1)
        visited = dist_props < 0.12
        self.obj_mem_rec = torch.where(visited, torch.zeros_like(self.obj_mem_rec), self.obj_mem_rec)
        # Object value estimate tracks observed resource utility
        self.obj_mem_val = torch.where(visited, 0.6 * self.obj_mem_val + 0.4 * self.prop_res, self.obj_mem_val)

        # ----------------------------------------------------------------------
        # 6. Multi-Objective Ethological Reward (Anti-Reward-Hacking Formulation!)
        # ----------------------------------------------------------------------
        dev_after = self._homeo_deviation()
        healthy_mask = (
            (self.drives[:, :6] >= self.healthy_low.unsqueeze(0))
            & (self.drives[:, :6] <= self.healthy_high.unsqueeze(0))
        )
        all_healthy = torch.all(healthy_mask, dim=-1)
        frac_healthy = healthy_mask.float().mean(dim=-1)

        # Direct homeostatic wellness + potential shaping (eliminates telescoping drift!)
        r_homeo = (
            (dev_before - dev_after) * 2.2
            - 1.45 * dev_after
            + 0.40 * all_healthy.float()
            + 0.25 * frac_healthy
        )

        # Steep quadratic distress penalty outside healthy thresholds
        out_of_range = (
            torch.relu(self.drives[:, 0] - 0.45) * 2.0
            + torch.relu(self.drives[:, 1] - 0.40) * 2.2
            + torch.relu(0.35 - self.drives[:, 2]) * 2.0
            + torch.relu(0.50 - self.drives[:, 3]) * 1.8
            + torch.relu(self.drives[:, 4] - 0.35) * 2.0
            + torch.relu(self.drives[:, 5] - 0.65) * 1.5
        )
        r_homeo = r_homeo - 0.85 * out_of_range

        # Biological circadian alignment prior (soft, non-rigid)
        day_rest_ok = is_day & is_sleeping
        night_active_ok = (~is_day) & (~is_sleeping)
        r_circ = 0.14 * day_rest_ok.float() + 0.10 * night_active_ok.float() - 0.10 * (is_day & a_wheel).float()

        # Biological per-skill dopaminergic freshness: doing one skill repeatedly saturates its
        # novelty/pleasure while fresh activities (wheel, tunnel, forage, hoard, explore, dig, rear, groom)
        # feel genuinely rewarding — creating rich, lifelike Syrian hamster behavioural rotation!
        chosen_sat = self.skill_satiation.gather(1, act.unsqueeze(1)).squeeze(1)
        freshness = torch.clamp(1.0 - chosen_sat, 0.05, 1.0)
        # Decay all skills' satiation smoothly, raise chosen skill's satiation (except daytime sleep)
        self.skill_satiation = torch.clamp(self.skill_satiation * 0.80, 0.0, 1.0)
        sat_bump = torch.where(a_rest & is_day, torch.full((self.N,), 0.15, device=self.device), torch.full((self.N,), 0.65, device=self.device))
        self.skill_satiation.scatter_add_(1, act.unsqueeze(1), sat_bump.unsqueeze(1))
        self.skill_satiation.clamp_(0.0, 1.0)

        # Natural Syrian hamster behavioural priors modulated by freshness (ALL 16 authentic skills balanced!)
        r_etho_raw = (
            0.34 * (unloaded_amt > 0.15).float()
            + 0.26 * (ate_any.float() * (hunger > 0.14).float())
            + 0.28 * (stuffed_any.float() * (self.nest_hoard < 0.85).float())
            + 0.24 * (a_app_food.float() * ((hunger > 0.18) | self.has_offered_food).float())
            + 0.22 * (drank.float() * (thirst > 0.14).float())
            + 0.34 * (a_wheel.float() * (0.45 + 0.55 * self.wheel_affinity) * (~is_day).float() * (energy > 0.38).float())
            + 0.38 * inspected_novel.float()
            + 0.26 * (a_explore.float() * (~is_day).float())
            + 0.28 * (a_tunnel.float() * (~is_day).float())
            + 0.24 * (a_dig.float() * (~is_day).float())
            + 0.22 * (a_rear.float() * (~is_day).float())
            + 0.20 * (a_groom.float() * (post_meal_groom | (stress > 0.14) | (comfort < 0.85)).float())
            + 0.22 * (a_nest.float() * (is_day | (comfort < 0.78)).float())
            + 0.18 * (a_hide.float() * (stress > 0.20).float())
        )
        r_etho = r_etho_raw * freshness

        # Anti-spam & natural bout rotation
        same_as_prev = act == self.prev_skill
        self.prev_skill_streak = torch.where(same_as_prev, self.prev_skill_streak + 1.0, torch.zeros_like(self.prev_skill_streak))
        repeat_cap = torch.where(a_rest & is_day, torch.full_like(self.prev_skill_streak, 3.0), torch.zeros_like(self.prev_skill_streak))
        c_spam = 0.28 * torch.relu(self.prev_skill_streak - repeat_cap) + 0.18 * chosen_sat * (~(a_rest & is_day)).float()
        c_switch = 0.004 * (~same_as_prev).float()

        # Update micro-sequence memories
        self.recent_eat_or_dig = torch.where(ate_any | stuffed_any | a_dig, torch.ones(self.N, device=self.device), self.recent_eat_or_dig * 0.4)
        self.recent_nested = torch.where(a_nest, torch.ones(self.N, device=self.device), self.recent_nested * 0.7)
        self.prev_skill = act

        # Total extrinsic reward
        reward = r_homeo + r_circ + r_etho + r_social - c_spam - c_switch

        # ----------------------------------------------------------------------
        # 7. World Events & Random Stimuli for Next Step
        # ----------------------------------------------------------------------
        # Periodic parent refilling when bowl/bottle gets low
        refill_bowl = (self.prop_res[:, 0] < 0.15) & (self._rand((self.N,)) < 0.35)
        refill_water = (self.prop_res[:, 1] < 0.15) & (self._rand((self.N,)) < 0.45)
        self.prop_res[:, 0] = torch.where(refill_bowl, torch.ones(self.N, device=self.device), self.prop_res[:, 0])
        self.prop_res[:, 1] = torch.where(refill_water, torch.ones(self.N, device=self.device), self.prop_res[:, 1])

        # Random offered food treat from shelf (4% chance per bout)
        spawn_food = (~self.has_offered_food) & (self._rand((self.N,)) < 0.04)
        self.has_offered_food = self.has_offered_food | spawn_food
        new_fx = (self._rand((self.N,)) * 2.0 - 1.0) * 0.32
        new_fy = (self._rand((self.N,)) * 2.0 - 1.0) * 0.14
        self.offered_food_xy[:, 0] = torch.where(spawn_food, new_fx, self.offered_food_xy[:, 0])
        self.offered_food_xy[:, 1] = torch.where(spawn_food, new_fy, self.offered_food_xy[:, 1])

        # Random novel shelf prop dropped (3.5% chance -> spikes curiosity!)
        spawn_prop = (~self.has_novel_prop) & (self._rand((self.N,)) < 0.035)
        self.has_novel_prop = self.has_novel_prop | spawn_prop
        new_px = (self._rand((self.N,)) * 2.0 - 1.0) * 0.32
        new_py = (self._rand((self.N,)) * 2.0 - 1.0) * 0.14
        self.novel_prop_xy[:, 0] = torch.where(spawn_prop, new_px, self.novel_prop_xy[:, 0])
        self.novel_prop_xy[:, 1] = torch.where(spawn_prop, new_py, self.novel_prop_xy[:, 1])
        self.drives[:, 5] = torch.clamp(self.drives[:, 5] + 0.32 * spawn_prop.float(), 0.0, 1.0)

        # Occasional mid-episode prop rearrangement (1.5% chance -> lowers familiarity & tests memory!)
        rearrange = self._rand((self.N,)) < 0.015
        if rearrange.any():
            r_idx = torch.nonzero(rearrange, as_tuple=False).squeeze(-1)
            rm = int(r_idx.numel())
            self.prop_xy[r_idx, 0, 0] = (self._rand((rm,)) * 2.0 - 1.0) * 0.34
            self.prop_xy[r_idx, 0, 1] = (self._rand((rm,)) * 2.0 - 1.0) * 0.14
            self.spatial_sectors[r_idx] *= 0.45
            self.obj_mem_rec[r_idx, 0] = 1.0
            self.drives[r_idx, 5] = torch.clamp(self.drives[r_idx, 5] + 0.25, 0.0, 1.0)

        # Occasional parent interaction stimulus (8% chance per bout)
        spawn_parent = self._rand((self.N,)) < 0.08
        self.parent_active = spawn_parent
        self.parent_action = torch.where(
            spawn_parent,
            torch.randint(1, 4, (self.N,), generator=self.gen, device=self.device),
            torch.zeros(self.N, dtype=torch.long, device=self.device),
        )
        # Sudden startle on call/pet from low-gentleness owner
        sudden_startle = spawn_parent & (self.parent_action >= 2) & (self.owner_gentleness < 0.5)
        self.startle = torch.clamp(self.startle + 0.40 * sudden_startle.float(), 0.0, 1.0)

        # Episode termination (fixed horizon truncation)
        self.step_count += 1
        dones = self.step_count >= self.cfg.episode_steps

        healthy = torch.all(
            (self.drives[:, :6] >= self.healthy_low.unsqueeze(0))
            & (self.drives[:, :6] <= self.healthy_high.unsqueeze(0)),
            dim=-1,
        )

        info = {
            "r_homeo": r_homeo.mean(),
            "r_circ": r_circ.mean(),
            "r_etho": r_etho.mean(),
            "r_social": r_social.mean(),
            "c_spam": c_spam.mean(),
            "healthy_rate": healthy.float().mean(),
            "familiarity": self.drives[:, 6].mean(),
            "curiosity": self.drives[:, 5].mean(),
            "hunger": self.drives[:, 0].mean(),
            "stress": self.drives[:, 4].mean(),
            "hoard": self.nest_hoard.mean(),
        }

        if dones.any():
            self.reset_envs(dones)

        next_obs = self.get_obs()
        next_mask = self.get_action_mask()
        return next_obs, reward, dones, next_mask, info
