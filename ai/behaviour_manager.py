"""Stage 4: Internal drives, transparent autonomous skill selection, and petting/taming response.

Follows HAMSTER_Technical_Blueprint.md Sections 2.2, 8, 9.9, and 10:
- Bounded computational drive vector: [hunger, thirst, energy, comfort, stress, curiosity, familiarity]
- Explicit honesty labels on every decision: LEARNED / RULE-BASED / ANIMATION-DRIVEN
- Non-forced parent petting/treat response driven by repeated familiarity + stress state
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np

HonestyLabel = Literal["LEARNED", "RULE-BASED", "ANIMATION-DRIVEN"]


@dataclass
class InternalDrives:
    """Normalized bounded internal state in [0.0, 1.0].

    Note: Computational state variables (Blueprint Section 8), not claims of subjective feelings.
    - hunger / thirst / stress / curiosity: higher = stronger need/drive
    - energy / comfort / familiarity: higher = better rested / comfortable / tamed
    """

    hunger: float = 0.40
    thirst: float = 0.35
    energy: float = 0.75
    comfort: float = 0.65
    stress: float = 0.30
    curiosity: float = 0.55
    familiarity: float = 0.15

    def clamp(self) -> None:
        for k in ("hunger", "thirst", "energy", "comfort", "stress", "curiosity", "familiarity"):
            setattr(self, k, float(np.clip(getattr(self, k), 0.0, 1.0)))

    def step_time(self, dt_sec: float) -> None:
        """Advance physiological drives over elapsed simulation seconds."""
        dt_h = dt_sec / 3600.0
        self.hunger += 0.08 * dt_h
        self.thirst += 0.10 * dt_h
        self.energy -= 0.05 * dt_h
        self.curiosity += 0.12 * dt_h
        # Stress slowly decays toward baseline
        self.stress -= 0.04 * dt_h
        self.clamp()

    def to_dict(self) -> dict[str, float]:
        return {k: round(float(v), 4) for k, v in asdict(self).items()}


@dataclass
class BehaviourDecision:
    skill_name: str
    target_object_id: str | None
    locomotion_label: HonestyLabel
    interaction_label: HonestyLabel
    selection_label: HonestyLabel
    utilities: dict[str, float]
    rationale: str


@dataclass
class PettingOutcome:
    action_requested: str
    hamster_response: Literal["avoid_and_retreat", "cautious_sniff", "accept_petting"]
    target_object_id: str
    locomotion_label: HonestyLabel
    interaction_label: HonestyLabel
    familiarity_before: float
    familiarity_after: float
    stress_before: float
    stress_after: float
    rationale: str


class AutonomousBehaviourManager:
    """Transparent RULE-BASED utility skill selector + repeated-interaction taming model."""

    def __init__(self, drives: InternalDrives | None = None) -> None:
        self.drives = drives or InternalDrives()
        self.drives.clamp()
        self.interaction_count: int = 0
        self.event_log: list[dict] = []

    def select_autonomous_skill(
        self,
        food_available: float = 1.0,
        water_available: float = 1.0,
    ) -> BehaviourDecision:
        d = self.drives
        utilities = {
            "forage_bowl": float(d.hunger * (1.2 if food_available > 0.05 else 0.05)),
            "drink_water": float(d.thirst * (1.2 if water_available > 0.05 else 0.05)),
            "retreat_to_hideout": float(0.85 * d.stress + 0.70 * (1.0 - d.energy) + 0.25 * (1.0 - d.comfort)),
            "enter_tunnel": float(0.85 * d.curiosity * (1.0 - 0.5 * d.stress)),
            "explore_wheel": float(0.75 * d.curiosity * d.energy * (1.0 - 0.6 * d.stress)),
            "groom_rest": float(0.35 * (1.0 - d.energy) + 0.30 * d.comfort * (1.0 - d.hunger)),
        }
        chosen = max(utilities.keys(), key=lambda k: utilities[k])

        target_map = {
            "forage_bowl": "prop_bowl_main",
            "drink_water": "prop_bottle_main",
            "retreat_to_hideout": "prop_hideout_main",
            "enter_tunnel": "prop_tunnel_main",
            "explore_wheel": "prop_wheel_main",
            "groom_rest": None,
        }
        decision = BehaviourDecision(
            skill_name=chosen,
            target_object_id=target_map[chosen],
            locomotion_label="LEARNED",
            interaction_label="RULE-BASED" if chosen != "groom_rest" else "ANIMATION-DRIVEN",
            selection_label="RULE-BASED",
            utilities={k: round(v, 4) for k, v in utilities.items()},
            rationale=f"Highest drive utility: {chosen}={utilities[chosen]:.3f}",
        )
        self.event_log.append(
            {
                "event_type": "skill_selected",
                "skill_name": decision.skill_name,
                "target_object_id": decision.target_object_id,
                "locomotion_label": decision.locomotion_label,
                "interaction_label": decision.interaction_label,
                "selection_label": decision.selection_label,
                "drives": self.drives.to_dict(),
                "utilities": decision.utilities,
            }
        )
        return decision

    def apply_skill_outcome(self, skill_name: str, success: bool) -> None:
        """Update drives after physical skill completion in MuJoCo."""
        d = self.drives
        if not success:
            d.stress += 0.05
            d.clamp()
            return

        if skill_name == "forage_bowl":
            d.hunger -= 0.35
            d.energy += 0.05
            d.comfort += 0.05
        elif skill_name == "drink_water":
            d.thirst -= 0.40
            d.comfort += 0.04
        elif skill_name == "retreat_to_hideout":
            d.stress -= 0.30
            d.energy += 0.25
            d.comfort += 0.20
        elif skill_name == "enter_tunnel":
            d.curiosity -= 0.30
            d.energy -= 0.08
            d.stress -= 0.05
        elif skill_name == "explore_wheel":
            d.curiosity -= 0.25
            d.energy -= 0.15
            d.stress -= 0.08
        elif skill_name == "groom_rest":
            d.stress -= 0.10
            d.comfort += 0.12
            d.energy += 0.08
        d.clamp()

    def handle_parent_interaction(
        self,
        action: Literal["offer_treat", "gentle_pet", "call_attention"] = "gentle_pet",
    ) -> PettingOutcome:
        """Non-forced hamster response to parent interaction based on repeated familiarity & stress.

        Per Blueprint Section 2.2 & 9.9:
        - The hamster is NOT forced to accept petting every time.
        - Stable familiarity builds gradually over repeated gentle interactions, not a single event.
        """
        d = self.drives
        fam_before = d.familiarity
        stress_before = d.stress
        self.interaction_count += 1

        # Trust score combines familiarity, low stress, and treat bonus
        treat_bonus = 0.22 if action == "offer_treat" else 0.0
        trust_score = d.familiarity + treat_bonus - 0.55 * d.stress

        if trust_score < 0.12:
            response: Literal["avoid_and_retreat", "cautious_sniff", "accept_petting"] = "avoid_and_retreat"
            target = "prop_hideout_main"
            # Gentle treat builds familiarity and calms slightly; premature petting adds mild stress
            d.familiarity += 0.18 if action == "offer_treat" else 0.05
            d.stress += -0.06 if action == "offer_treat" else 0.06
            rationale = f"Low trust ({trust_score:.2f}): retreats to hideout instead of forcing petting."
        elif trust_score < 0.42:
            response = "cautious_sniff"
            target = "prop_treat_zone"
            d.familiarity += 0.18 if action == "offer_treat" else 0.12
            d.stress -= 0.08 if action == "offer_treat" else 0.04
            d.curiosity -= 0.08
            rationale = f"Moderate trust ({trust_score:.2f}): cautiously approaches and sniffs interaction zone."
        else:
            response = "accept_petting"
            target = "prop_treat_zone"
            d.familiarity += 0.10
            d.stress -= 0.15
            d.comfort += 0.15
            if action == "offer_treat":
                d.hunger -= 0.12
            rationale = f"High trust ({trust_score:.2f}): approaches willingly and relaxes for gentle petting."

        d.clamp()
        outcome = PettingOutcome(
            action_requested=action,
            hamster_response=response,
            target_object_id=target,
            locomotion_label="LEARNED",
            interaction_label="RULE-BASED",
            familiarity_before=round(fam_before, 4),
            familiarity_after=round(d.familiarity, 4),
            stress_before=round(stress_before, 4),
            stress_after=round(d.stress, 4),
            rationale=rationale,
        )
        self.event_log.append({"event_type": "parent_interaction", **asdict(outcome)})
        return outcome
