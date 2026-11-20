"""
HAMMY — Cognitive Brain v2 Contract, ObservationV3 Builder & ONNX Runtime Wrapper.

Shared single source of truth between:
  - GPU PyTorch CUDA vectorized trainer (`training/gpu_cognitive_env.py`)
  - Live FastAPI authoritative brain engine (`services/runtime/brain_engine.py`)
  - Persistent WorldWorker catch-up (`services/world_worker/catchup.py`)

Honesty guarantee:
  - All neural inferences are explicitly tagged `BehaviourType.LEARNED`.
  - Observation/action schemas and model version are strictly validated at load time.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

COGNITIVE_POLICY_VERSION = "hl_rppo_rnd_v2.0.0"
COGNITIVE_OBS_VERSION = "cognitive_obs_v3.0.0"
COGNITIVE_ACT_VERSION = "cognitive_act_v2.0.0"

COGNITIVE_SKILLS_V2: Tuple[str, ...] = (
    "approach_food",       # 0
    "eat",                 # 1
    "cheek_stuffing",      # 2
    "unload_hoard",        # 3
    "drink",               # 4
    "explore_area",        # 5
    "enter_tunnel",        # 6
    "run_on_wheel",        # 7
    "digging",             # 8
    "hind_leg_standing",   # 9
    "grooming",            # 10
    "nesting",             # 11
    "rest",                # 12
    "hide",                # 13
    "cautious_sniff",      # 14
    "accept_petting",      # 15
)

NUM_COGNITIVE_SKILLS = len(COGNITIVE_SKILLS_V2)  # 16
SKILL_TO_IDX: Dict[str, int] = {name: i for i, name in enumerate(COGNITIVE_SKILLS_V2)}

CORE_PROP_IDS: Tuple[str, ...] = (
    "prop_bowl_main",
    "prop_bottle_main",
    "prop_hideout_main",
    "prop_tunnel_main",
    "prop_wheel_main",
    "prop_chew_block_main",
)

# Typical biological bout durations (simulated seconds) for live & GPU SMDP stepping
SKILL_BASE_DURATIONS_SEC: Dict[str, float] = {
    "approach_food": 25.0,
    "eat": 55.0,
    "cheek_stuffing": 45.0,
    "unload_hoard": 40.0,
    "drink": 35.0,
    "explore_area": 75.0,
    "enter_tunnel": 50.0,
    "run_on_wheel": 110.0,
    "digging": 60.0,
    "hind_leg_standing": 22.0,
    "grooming": 50.0,
    "nesting": 90.0,
    "rest": 240.0,
    "hide": 100.0,
    "cautious_sniff": 30.0,
    "accept_petting": 45.0,
}

# Canonical habitat anchor coordinates matching habitat_v1 / Blender scene
DEFAULT_CORE_PROP_POS: Dict[str, Tuple[float, float, float]] = {
    "prop_bowl_main": (0.28, -0.11, 0.165),
    "prop_bottle_main": (0.433, -0.02, 0.183),
    "prop_hideout_main": (0.28, 0.11, 0.165),
    "prop_tunnel_main": (-0.04, -0.05, 0.165),
    "prop_wheel_main": (-0.30, 0.13, 0.165),
    "prop_chew_block_main": (0.17, -0.05, 0.165),
}

SKILL_TARGET_PROP: Dict[str, Optional[str]] = {
    "approach_food": "prop_bowl_main",
    "eat": "prop_bowl_main",
    "cheek_stuffing": "prop_bowl_main",
    "unload_hoard": "prop_hideout_main",
    "drink": "prop_bottle_main",
    "explore_area": None,
    "enter_tunnel": "prop_tunnel_main",
    "run_on_wheel": "prop_wheel_main",
    "digging": None,
    "hind_leg_standing": None,
    "grooming": None,
    "nesting": "prop_hideout_main",
    "rest": "prop_hideout_main",
    "hide": "prop_hideout_main",
    "cautious_sniff": None,
    "accept_petting": None,
}

# Exact ObservationV3 vector layout (96 floats):
#   [0..6]   7 drives: hunger, thirst, energy, comfort, stress, curiosity, familiarity
#   [7..12]  6 circadian/body: sin(2pi*circ), cos(2pi*circ), is_daylight, cheek_pouch_fill, nest_hoard_level, startle_level
#   [13..22] 10 spatial/body: pos_x/0.5, pos_y/0.25, cos(yaw), sin(yaw), vel_x/0.3, vel_y/0.3,
#                             inside_hideout, inside_tunnel, on_wheel, at_offered_food
#   [23..46] 24 core props: 6 props * [rel_x/0.5, rel_y/0.25, dist/0.6, resource_level]
#   [47..54] 8 dynamic stimuli: [has_offered_food, food_rel_x/0.5, food_rel_y/0.25, food_dist/0.6,
#                                has_novel_prop, prop_rel_x/0.5, prop_rel_y/0.25, prop_dist/0.6]
#   [55..70] 16 memory: 6 core props * [est_value, recency] (12) +
#                       [curr_cell_fam, mean_fam, least_fam_rel_x/0.5, least_fam_rel_y/0.25] (4)
#   [71..76] 6 parent context: [parent_active, is_offer_treat, is_gentle_pet, is_call_attention,
#                               trust_trend, time_since_parent_norm]
#   [77..92] 16 prev_skill one-hot
#   [93..95] 3 meta/temperament: [prev_skill_streak_norm, boldness, wheel_affinity]
OBS_V3_DIM = 96
GRU_HIDDEN_DIM = 128


@dataclass
class CognitiveObservationInput:
    """Structured live observation input converted deterministically into ObservationV3 (96 floats)."""

    hunger: float = 0.25
    thirst: float = 0.20
    energy: float = 0.80
    comfort: float = 0.78
    stress: float = 0.12
    curiosity: float = 0.35
    familiarity: float = 0.15
    circadian_phase: float = 0.85  # [0, 1) where 0.29..0.79 is daylight
    cheek_pouch_fill: float = 0.0
    nest_hoard_level: float = 0.25
    startle_level: float = 0.0

    pos_xy: Tuple[float, float] = (0.0, 0.0)
    yaw_rad: float = 0.0
    vel_xy: Tuple[float, float] = (0.0, 0.0)
    inside_hideout: bool = False
    inside_tunnel: bool = False
    on_wheel: bool = False

    # Core objects: {prop_id: (x, y, resource_level)}
    core_props: Dict[str, Tuple[float, float, float]] = field(default_factory=dict)

    # Dynamic shelf objects
    offered_food_xy: Optional[Tuple[float, float]] = None
    novel_prop_xy: Optional[Tuple[float, float]] = None

    # Memory features
    object_memory: Dict[str, Tuple[float, float]] = field(default_factory=dict)  # {prop_id: (est_val, recency)}
    curr_cell_familiarity: float = 0.5
    mean_familiarity: float = 0.5
    least_familiar_xy: Tuple[float, float] = (0.0, 0.0)

    # Parent interaction stimulus
    parent_active: bool = False
    parent_action: Optional[str] = None  # "offer_treat" | "gentle_pet" | "call_attention" | None
    trust_trend: float = 0.0
    time_since_parent_norm: float = 1.0

    # History & temperament
    prev_skill: Optional[str] = None
    prev_skill_streak: int = 0
    boldness: float = 0.55
    wheel_affinity: float = 0.65


def compute_action_mask(inp: CognitiveObservationInput) -> np.ndarray:
    """Computes biologically grounded valid-action mask [16] (True = allowed)."""
    mask = np.ones(NUM_COGNITIVE_SKILLS, dtype=bool)

    bowl_x, bowl_y, bowl_lvl = inp.core_props.get(
        "prop_bowl_main",
        (DEFAULT_CORE_PROP_POS["prop_bowl_main"][0], DEFAULT_CORE_PROP_POS["prop_bowl_main"][1], 1.0),
    )
    bottle_x, bottle_y, bottle_lvl = inp.core_props.get(
        "prop_bottle_main",
        (DEFAULT_CORE_PROP_POS["prop_bottle_main"][0], DEFAULT_CORE_PROP_POS["prop_bottle_main"][1], 0.75),
    )

    has_food = (bowl_lvl > 0.02) or (inp.offered_food_xy is not None)
    food_target_xy = inp.offered_food_xy if inp.offered_food_xy is not None else (bowl_x, bowl_y)
    dist_food = math.hypot(food_target_xy[0] - inp.pos_xy[0], food_target_xy[1] - inp.pos_xy[1])

    # 0: approach_food only makes sense when food exists and hamster is not already right at it
    if not has_food or dist_food <= 0.08:
        mask[SKILL_TO_IDX["approach_food"]] = False

    # 1: eat allowed when food exists or inside hideout with hoard
    can_eat_hoard = inp.inside_hideout and inp.nest_hoard_level > 0.05
    if not (has_food or can_eat_hoard):
        mask[SKILL_TO_IDX["eat"]] = False

    # 2: cheek_stuffing requires external food and pouch capacity remaining
    if (not has_food) or inp.cheek_pouch_fill >= 0.92:
        mask[SKILL_TO_IDX["cheek_stuffing"]] = False

    # 3: unload_hoard requires food carried in cheek pouches
    if inp.cheek_pouch_fill < 0.15:
        mask[SKILL_TO_IDX["unload_hoard"]] = False

    # 4: drink requires water available
    if bottle_lvl <= 0.01:
        mask[SKILL_TO_IDX["drink"]] = False

    # 14 & 15: parent interaction responses only valid while parent stimulus is active
    if not inp.parent_active:
        mask[SKILL_TO_IDX["cautious_sniff"]] = False
        mask[SKILL_TO_IDX["accept_petting"]] = False

    # Safety fallback: guarantee at least explore/groom/rest remain valid
    if not np.any(mask):
        mask[SKILL_TO_IDX["explore_area"]] = True
        mask[SKILL_TO_IDX["rest"]] = True
    return mask


def build_observation_v3(inp: CognitiveObservationInput) -> np.ndarray:
    """Packs CognitiveObservationInput into the exact 96-dim ObservationV3 float32 vector."""
    v = np.zeros(OBS_V3_DIM, dtype=np.float32)

    # [0..6] 7 internal drives
    v[0] = float(np.clip(inp.hunger, 0.0, 1.0))
    v[1] = float(np.clip(inp.thirst, 0.0, 1.0))
    v[2] = float(np.clip(inp.energy, 0.0, 1.0))
    v[3] = float(np.clip(inp.comfort, 0.0, 1.0))
    v[4] = float(np.clip(inp.stress, 0.0, 1.0))
    v[5] = float(np.clip(inp.curiosity, 0.0, 1.0))
    v[6] = float(np.clip(inp.familiarity, 0.0, 1.0))

    # [7..12] circadian & physical body state
    phase = float(inp.circadian_phase % 1.0)
    ang = 2.0 * math.pi * phase
    is_daylight = 1.0 if (0.29 <= phase <= 0.79) else 0.0
    v[7] = math.sin(ang)
    v[8] = math.cos(ang)
    v[9] = is_daylight
    v[10] = float(np.clip(inp.cheek_pouch_fill, 0.0, 1.0))
    v[11] = float(np.clip(inp.nest_hoard_level, 0.0, 1.0))
    v[12] = float(np.clip(inp.startle_level, 0.0, 1.0))

    # [13..22] spatial & posture flags
    px, py = float(inp.pos_xy[0]), float(inp.pos_xy[1])
    v[13] = np.clip(px / 0.50, -1.5, 1.5)
    v[14] = np.clip(py / 0.25, -1.5, 1.5)
    v[15] = math.cos(inp.yaw_rad)
    v[16] = math.sin(inp.yaw_rad)
    v[17] = np.clip(float(inp.vel_xy[0]) / 0.30, -2.0, 2.0)
    v[18] = np.clip(float(inp.vel_xy[1]) / 0.30, -2.0, 2.0)
    v[19] = 1.0 if inp.inside_hideout else 0.0
    v[20] = 1.0 if inp.inside_tunnel else 0.0
    v[21] = 1.0 if inp.on_wheel else 0.0

    if inp.offered_food_xy is not None:
        d_food = math.hypot(inp.offered_food_xy[0] - px, inp.offered_food_xy[1] - py)
        v[22] = 1.0 if d_food <= 0.14 else 0.0
    else:
        v[22] = 0.0

    # [23..46] 6 core habitat objects (24 floats)
    idx = 23
    for pid in CORE_PROP_IDS:
        default_xyz = DEFAULT_CORE_PROP_POS[pid]
        ox, oy, rlvl = inp.core_props.get(pid, (default_xyz[0], default_xyz[1], 1.0))
        rx = ox - px
        ry = oy - py
        dist = math.hypot(rx, ry)
        v[idx] = np.clip(rx / 0.50, -2.0, 2.0)
        v[idx + 1] = np.clip(ry / 0.25, -2.0, 2.0)
        v[idx + 2] = np.clip(dist / 0.60, 0.0, 2.0)
        v[idx + 3] = float(np.clip(rlvl, 0.0, 1.0))
        idx += 4

    # [47..54] dynamic offered food & novel prop (8 floats)
    if inp.offered_food_xy is not None:
        frx = inp.offered_food_xy[0] - px
        fry = inp.offered_food_xy[1] - py
        v[47] = 1.0
        v[48] = np.clip(frx / 0.50, -2.0, 2.0)
        v[49] = np.clip(fry / 0.25, -2.0, 2.0)
        v[50] = np.clip(math.hypot(frx, fry) / 0.60, 0.0, 2.0)
    else:
        v[47] = 0.0
        v[50] = 1.0

    if inp.novel_prop_xy is not None:
        nrx = inp.novel_prop_xy[0] - px
        nry = inp.novel_prop_xy[1] - py
        v[51] = 1.0
        v[52] = np.clip(nrx / 0.50, -2.0, 2.0)
        v[53] = np.clip(nry / 0.25, -2.0, 2.0)
        v[54] = np.clip(math.hypot(nrx, nry) / 0.60, 0.0, 2.0)
    else:
        v[51] = 0.0
        v[54] = 1.0

    # [55..70] object & spatial memory (16 floats)
    midx = 55
    for pid in CORE_PROP_IDS:
        est_v, rec = inp.object_memory.get(pid, (0.5, 0.5))
        v[midx] = float(np.clip(est_v, -1.0, 1.0))
        v[midx + 1] = float(np.clip(rec, 0.0, 1.0))
        midx += 2
    v[67] = float(np.clip(inp.curr_cell_familiarity, 0.0, 1.0))
    v[68] = float(np.clip(inp.mean_familiarity, 0.0, 1.0))
    v[69] = np.clip((inp.least_familiar_xy[0] - px) / 0.50, -2.0, 2.0)
    v[70] = np.clip((inp.least_familiar_xy[1] - py) / 0.25, -2.0, 2.0)

    # [71..76] parent interaction stimulus (6 floats)
    v[71] = 1.0 if inp.parent_active else 0.0
    v[72] = 1.0 if inp.parent_action == "offer_treat" else 0.0
    v[73] = 1.0 if inp.parent_action == "gentle_pet" else 0.0
    v[74] = 1.0 if inp.parent_action == "call_attention" else 0.0
    v[75] = float(np.clip(inp.trust_trend, -1.0, 1.0))
    v[76] = float(np.clip(inp.time_since_parent_norm, 0.0, 1.0))

    # [77..92] previous skill one-hot (16 floats)
    if inp.prev_skill and inp.prev_skill in SKILL_TO_IDX:
        v[77 + SKILL_TO_IDX[inp.prev_skill]] = 1.0

    # [93..95] streak + temperament (3 floats)
    v[93] = float(np.clip(inp.prev_skill_streak / 6.0, 0.0, 1.0))
    v[94] = float(np.clip(inp.boldness, 0.0, 1.0))
    v[95] = float(np.clip(inp.wheel_affinity, 0.0, 1.0))

    return v


@dataclass
class CognitiveBrainDecision:
    skill_name: str
    skill_idx: int
    skill_probs: Dict[str, float]
    top_skills: List[Dict[str, Any]]
    entropy: float
    value_ext: float
    value_int: float
    rnd_novelty: float
    policy_version: str
    behaviour_type: str = "learned"


class CognitiveBrainONNX:
    """Fast CPU ONNXRuntime inference engine for the GRU-Recurrent PPO + RND cognitive brain."""

    def __init__(
        self,
        policy_onnx_path: str | Path = "training/runs/brain_v2/high_level_brain_v2.onnx",
        rnd_onnx_path: Optional[str | Path] = "training/runs/brain_v2/rnd_curiosity_v2.onnx",
        temperature: float = 0.85,
    ) -> None:
        import onnx
        import onnxruntime as ort

        self.policy_path = Path(policy_onnx_path)
        if not self.policy_path.exists():
            raise FileNotFoundError(f"Cognitive brain ONNX not found at {self.policy_path}")

        proto = onnx.load(str(self.policy_path))
        self.meta: Dict[str, str] = {p.key: p.value for p in proto.metadata_props}
        self.policy_version = self.meta.get("policy_version", COGNITIVE_POLICY_VERSION)
        self.obs_version = self.meta.get("obs_schema_version", COGNITIVE_OBS_VERSION)
        if self.obs_version != COGNITIVE_OBS_VERSION:
            raise ValueError(
                f"Cognitive brain obs version mismatch: {self.obs_version} != {COGNITIVE_OBS_VERSION}"
            )

        self.session = ort.InferenceSession(str(self.policy_path), providers=["CPUExecutionProvider"])
        self.temperature = float(max(0.1, temperature))

        self.rnd_session = None
        if rnd_onnx_path is not None and Path(rnd_onnx_path).exists():
            self.rnd_session = ort.InferenceSession(str(rnd_onnx_path), providers=["CPUExecutionProvider"])

        # Per-pet recurrent GRU hidden state [1, GRU_HIDDEN_DIM]
        self._hidden_by_pet: Dict[str, np.ndarray] = {}

    def reset_pet(self, pet_id: str) -> None:
        self._hidden_by_pet[pet_id] = np.zeros((1, GRU_HIDDEN_DIM), dtype=np.float32)

    def get_hidden(self, pet_id: str) -> np.ndarray:
        h = self._hidden_by_pet.get(pet_id)
        if h is None:
            h = np.zeros((1, GRU_HIDDEN_DIM), dtype=np.float32)
            self._hidden_by_pet[pet_id] = h
        return h

    def compute_rnd_novelty(self, obs_vec: np.ndarray) -> float:
        if self.rnd_session is None:
            return 0.0
        out = self.rnd_session.run(["novelty"], {"obs": obs_vec[None, :].astype(np.float32)})[0]
        return float(np.clip(out.reshape(-1)[0], 0.0, 1.0))

    def decide(
        self,
        pet_id: str,
        obs_input: CognitiveObservationInput,
        *,
        rng: Optional[np.random.Generator] = None,
        deterministic: bool = False,
        temperature_override: Optional[float] = None,
    ) -> CognitiveBrainDecision:
        obs_vec = build_observation_v3(obs_input)
        mask = compute_action_mask(obs_input)
        h_in = self.get_hidden(pet_id)

        logits, v_ext, v_int, h_out = self.session.run(
            ["logits", "value_ext", "value_int", "h_out"],
            {"obs": obs_vec[None, :].astype(np.float32), "h_in": h_in},
        )
        self._hidden_by_pet[pet_id] = np.asarray(h_out, dtype=np.float32)

        raw_logits = np.asarray(logits[0], dtype=np.float64)
        temp = float(temperature_override or self.temperature)
        scaled = raw_logits / max(0.1, temp)
        scaled[~mask] = -1e9
        scaled -= np.max(scaled)
        probs = np.exp(scaled)
        probs[~mask] = 0.0
        probs_sum = float(np.sum(probs))
        if probs_sum <= 1e-12 or not np.all(np.isfinite(probs)):
            probs = mask.astype(np.float64) / max(1, int(np.sum(mask)))
        else:
            probs /= probs_sum

        if deterministic:
            skill_idx = int(np.argmax(probs))
        else:
            active_rng = rng or np.random.default_rng()
            skill_idx = int(active_rng.choice(NUM_COGNITIVE_SKILLS, p=probs))

        valid_probs = probs[probs > 1e-12]
        entropy = float(-np.sum(valid_probs * np.log(valid_probs)) / math.log(NUM_COGNITIVE_SKILLS))

        rnd_nov = self.compute_rnd_novelty(obs_vec)

        skill_probs = {COGNITIVE_SKILLS_V2[i]: round(float(probs[i]), 4) for i in range(NUM_COGNITIVE_SKILLS)}
        ranked = sorted(skill_probs.items(), key=lambda kv: kv[1], reverse=True)
        top_skills = [{"skill": k, "prob": p} for k, p in ranked[:5]]

        return CognitiveBrainDecision(
            skill_name=COGNITIVE_SKILLS_V2[skill_idx],
            skill_idx=skill_idx,
            skill_probs=skill_probs,
            top_skills=top_skills,
            entropy=round(entropy, 4),
            value_ext=round(float(v_ext.reshape(-1)[0]), 4),
            value_int=round(float(v_int.reshape(-1)[0]), 4),
            rnd_novelty=round(rnd_nov, 4),
            policy_version=self.policy_version,
            behaviour_type="learned",
        )
