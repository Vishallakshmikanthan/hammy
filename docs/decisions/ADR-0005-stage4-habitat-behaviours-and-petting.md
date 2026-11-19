# ADR-0005: Stage 4 MuJoCo Habitat Interaction, Autonomous Behaviours & Petting/Taming

**Date:** 2026-11-19  
**Status:** Accepted (Awaiting HUMAN CHECKPOINT 4)  

## Context
Stage 4 connects our exported Stage 3 ONNX locomotion policy (`training/runs/stage3/best_policy.onnx`) into a physical MuJoCo habitat (`1.0 m × 0.6 m` enclosure with 6 interactive props) governed by internal drives, autonomous skill selection, and a non-forced petting/taming response system.

## Key Engineering Decisions
1. **Single-Source Morphology via `mujoco.MjSpec` (`simulation/habitat_objects.py`):**
   - Instead of duplicating `hamster.xml`, `build_habitat_model()` loads `simulation/models/hamster/hamster.xml` (`hamster_mjcf_v1.0.0`) via `MjSpec` and attaches enclosure walls, overview camera, and 6 versioned props (`prop_bowl_main`, `prop_bottle_main`, `prop_hideout_main`, `prop_tunnel_main`, `prop_wheel_main`, `prop_treat_zone`).
2. **Yaw-Invariant Orientation Observation in Habitat Deployment:**
   - During continuous multi-skill navigation, turning past `±90°` caused raw world-frame `body_quat` to drift out of distribution relative to Stage 3 training (`yaw ≈ 0`). Removing world yaw from `body_quat` in `HabitatSkillController._build_obs()` (keeping pure roll/pitch tilt) raised continuous multi-skill task success from `75%` to **`100.0%`** at **`0.0%` falls**.
3. **Explicit Honesty Labeling:**
   - Locomotion & balance: **`LEARNED (ONNX) + RULE-BASED steering assist`** (gentle `±0.020 N·m` pelvis yaw-assist + spine/neck yaw bias compensates for the Stage 3 policy's weak yaw authority; gait & balance remain 100% driven by `best_policy.onnx`).
   - Skill selection & drive updates: **`RULE-BASED`** transparent utility scoring over bounded drives `[hunger, thirst, energy, comfort, stress, curiosity, familiarity]` in `[0, 1]`.
   - Interaction postures (foraging dip, drinking tilt, grooming, petting lean): **`RULE-BASED`** / **`ANIMATION-DRIVEN`**.
4. **Non-Forced Petting & Taming (`ai/behaviour_manager.py`):**
   - Parent interactions (`gentle_pet`, `offer_treat`, `call_attention`) never force acceptance. Low trust (`familiarity + treat_bonus - 0.55 * stress < 0.12`) triggers `avoid_and_retreat` to `prop_hideout_main`; repeated gentle treats build familiarity (`0.05 → 0.78`) and reduce stress (`0.45 → 0.03`), transitioning naturally through `cautious_sniff` to `accept_petting`.
