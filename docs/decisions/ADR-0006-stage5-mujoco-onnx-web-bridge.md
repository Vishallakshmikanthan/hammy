# ADR-0006: Stage 5 MuJoCo + ONNX Physics Bridge to Photorealistic 3D Web Habitat (`hamster.glb` + FastAPI)

**Date:** 2026-11-19  
**Status:** Accepted  

## Context
Stage 5 bridges our Stage 3 trained ONNX locomotion policy (`best_policy.onnx`) and Stage 4 autonomous habitat & petting/taming manager into the existing photorealistic Three.js web habitat (`web/public/assets/hamster.glb`) and FastAPI backend (`services/api/main.py`) without modifying or degrading the realistic visual hamster asset.

## Decisions
1. **Backward-Compatible Contract Extension (`contracts/schemas.py`):**
   - Registered `hamster_mjcf_v1.0.0` (16 actuated DoF) and `habitat_mujoco_v1.0.0` in `SUPPORTED_SCHEMA_VERSIONS` and widened `TrajectoryKeyframeV1.joint_angles` `max_length` from `14` to `16` (keeping `min_length=12` backward-compatible with all legacy clips).
2. **Real MuJoCo + ONNX `TrajectoryClipV1` Generator (`services/simulation_worker/mujoco_clip_generator.py`):**
   - Runs `HabitatSkillController` with `best_policy.onnx` in real MuJoCo physics (`50 Hz`), downsamples to `20 Hz`, converts MuJoCo `(x, y, z_up)` / `[w, x, y, z]` to Three.js `(x, y_up, -y)` / `[x, y, z, w]`, and tags every clip with `origin="observed_physics"`, `behaviour_type="learned"`, and `morphology_version="hamster_mjcf_v1.0.0"`.
   - Exports 6 verified skill clips (`forage_bowl`, `drink_water`, `enter_tunnel`, `retreat_to_hideout`, `cautious_sniff`, `accept_petting`) to both `LocalObjectStorage` (`infrastructure/object_storage/clips/pet_hammy_01/`) and `web/public/assets/mujoco_clips/manifest.json`.
3. **FastAPI Petting & Bridge Routes (`services/api/routes/mujoco_bridge.py`):**
   - Added `/api/v1/mujoco/status`, `/api/v1/mujoco/interact`, and `/api/v1/mujoco/clips/{clip_id}` to expose live drive state, non-forced petting/taming outcomes, and matching MuJoCo + ONNX trajectory clips for `ClipPlayer`.
