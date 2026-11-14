"""
HAMMY — P6.1: Signature Hamster Behaviours (`ai/policies/behaviours.py`).
Every behaviour here is explicitly labelled `BehaviourType.SCRIPTED` for low-level
execution with learned high-level selection (`scripted-with-learned-selection`)
per Non-Negotiable Rule 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
from contracts.schemas import ActionV1, BehaviourType, ObservationV1


@dataclass(frozen=True)
class BehaviourVisualSpec:
    name: str
    implementation_type: str  # "scripted-with-learned-selection"
    target_object: str | None
    drive_effects: Dict[str, str]
    morph_targets: List[str]
    procedural_layers: List[str]
    realism_notes: str


BEHAVIOUR_SPECS: Dict[str, BehaviourVisualSpec] = {
    "cheek_stuffing": BehaviourVisualSpec(
        name="cheek_stuffing",
        implementation_type="scripted-with-learned-selection",
        target_object="prop_bowl_main",
        drive_effects={"hunger": "-0.12", "comfort": "+0.08", "stress": "-0.05"},
        morph_targets=["cheek_pouch_left", "cheek_pouch_right", "mouth_open", "chew"],
        procedural_layers=["cheekPouch", "whiskerTwitch", "springJiggle"],
        realism_notes="Paws push seeds into mouth; pouches swell smoothly past shoulders.",
    ),
    "hind_leg_standing": BehaviourVisualSpec(
        name="hind_leg_standing",
        implementation_type="scripted-with-learned-selection",
        target_object=None,
        drive_effects={"curiosity": "-0.14", "stress": "-0.03"},
        morph_targets=["whisker_forward", "nose_wrinkle"],
        procedural_layers=["whiskerTwitch", "earOrientation", "blinkAndGaze"],
        realism_notes="Hind-leg stance, front paws tucked, head scanning, 5-10 Hz nose/whisker sniff.",
    ),
    "grooming": BehaviourVisualSpec(
        name="grooming",
        implementation_type="scripted-with-learned-selection",
        target_object=None,
        drive_effects={"stress": "-0.16", "comfort": "+0.12"},
        morph_targets=["squint", "blink", "mouth_open"],
        procedural_layers=["blinkAndGaze", "breathing", "springJiggle"],
        realism_notes="Sitting posture, bilateral front-paw face wash, subtle ear fold.",
    ),
    "digging": BehaviourVisualSpec(
        name="digging",
        implementation_type="scripted-with-learned-selection",
        target_object=None,
        drive_effects={"curiosity": "-0.18", "comfort": "+0.06", "energy": "-0.04"},
        morph_targets=["nose_wrinkle", "whisker_forward"],
        procedural_layers=["springJiggle", "whiskerTwitch", "tail"],
        realism_notes="Alternating front-paw scoops compressing bedding heightfield.",
    ),
    "nesting": BehaviourVisualSpec(
        name="nesting",
        implementation_type="scripted-with-learned-selection",
        target_object="prop_hideout_main",
        drive_effects={"comfort": "+0.18", "stress": "-0.14", "energy": "+0.05"},
        morph_targets=["ear_fold", "squint", "breath_in"],
        procedural_layers=["breathing", "earOrientation", "blinkAndGaze"],
        realism_notes="Gathers bedding near hideout and curls into low-profile rest posture.",
    ),
}


def step_cheek_stuffing(obs: ObservationV1) -> ActionV1:
    from ai.policies.skills import navigate_and_interact
    act, _ = navigate_and_interact(obs, target_object_id="prop_bowl_main", stop_dist_m=0.055)
    return act


def step_hind_leg_standing(obs: ObservationV1) -> ActionV1:
    return ActionV1(
        forward_speed_m_s=0.0,
        turn_rate_rad_s=0.35,
        interact_flag=True,
        behaviour_type=BehaviourType.SCRIPTED,
    )


def step_grooming(obs: ObservationV1) -> ActionV1:
    return ActionV1(
        forward_speed_m_s=0.0,
        turn_rate_rad_s=0.0,
        interact_flag=True,
        behaviour_type=BehaviourType.SCRIPTED,
    )


def step_digging(obs: ObservationV1) -> ActionV1:
    return ActionV1(
        forward_speed_m_s=0.04,
        turn_rate_rad_s=0.25,
        interact_flag=True,
        behaviour_type=BehaviourType.SCRIPTED,
    )


def step_nesting(obs: ObservationV1) -> ActionV1:
    from ai.policies.skills import navigate_and_interact
    act, _ = navigate_and_interact(obs, target_object_id="prop_hideout_main", stop_dist_m=0.075)
    return act

