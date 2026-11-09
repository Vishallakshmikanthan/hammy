# HAMMY — Autonomous AI Virtual Syrian Hamster & Photoreal Cycles Pipeline

## Overview
- **Photorealistic Blender 5.2 Cycles + OptiX Art Pipeline (`blender/scripts/`):**
  - `00_check_env.py`: Verifies Blender 5.2.3 LTS, Python 3.13, and NVIDIA RTX 5070 OptiX GPU.
  - `10_cage.py`: Builds the 1.00 m × 0.50 m × 0.40 m enclosure, acrylic panels, open-front 0.28 m wheel, ceramic bowl, water bottle, arched wooden hideout, and 3-section burrow tunnel.
  - `20_clutter.py`: Generates displaced bedding, 2,550 curled wood/paper shavings, seed mix hoard, chew twigs, and chewed doorway notches.
  - `30_materials.py`: Applies scanned CC0 Poly Haven PBR textures (`fine_grained_wood`, `plywood`, `bark_brown_02`, `concrete_floor_worn_001`), ray-traced AO edge wear, smudged clear acrylic, anisotropic brushed steel, and subsurface-scattered bedding.
  - `40_lighting_camera.py`: Configures `day`, `evening`, and `night` lighting presets, Poly Haven indoor HDRI (`brown_photostudio_02_1k.hdr`), and 3 calibrated DoF cameras (`cam_macro_85mm`, `cam_three_quarter_50mm`, `cam_wide_35mm`).
  - `50_fur_setup.py`: Builds the Syrian hamster mesh (`ham_body` matched against `reference/photos/images.cv_23mpmrt35vasncelu0dtfo`), 3-layer modern `HairCurves` + `Geometry Nodes` viewport preview toggle (`undercoat`, `guard_hairs`, `face_fur`, `whiskers`), anisotropic `Principled Hair BSDF` (`CHIANG`), and side-by-side reference comparison (`renders/compare/05_compare_with_reference.png`).
- **Core Simulation, Contracts & Homeostatic Cognition (`contracts/`, `simulation/`, `ai/`):**
  - `contracts/schemas.py`: Versioned Pydantic + JSON Schema contracts (`ObservationV1`, `ActionV1`, `WorldEventV1`, `CommandV1`) enforcing honesty labels (`learned`, `scripted`, `rule`), event origins (`observed_physics`, `sampled_from_skill_model`, `rule`), and idempotency keys (`command_id`).
  - `simulation/habitats/v1.xml` & `v1.json`: MuJoCo MJCF and affordance sidecar matching the exact metric coordinates of `blender/scene.blend`.
  - `simulation/habitat_env.py`: Seeded, deterministic `HabitatEnv` stepping planar locomotion, object affordances, and homeostatic drives.
  - `ai/cognition/drives.py`: 6-drive homeostatic state vector (`hunger`, `thirst`, `energy`, `comfort`, `stress`, `curiosity`) + 24h crepuscular/nocturnal circadian cycle and squared-deviation reduction reward.
  - `ai/policies/skills.py`: Skill catalog (`eat_at_bowl`, `drink_at_bottle`, `sleep_in_hideout`, `hide_in_tunnel`, `run_on_wheel`, `gnaw_chew_block`) and `ScriptedHomeostaticBaselinePolicy`.

