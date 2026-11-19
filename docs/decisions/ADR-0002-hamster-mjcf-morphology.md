# ADR-0002: Stage 1 Syrian Hamster MJCF Morphology (`hamster_mjcf_v1.0.0`) & Versioned Locomotion Contracts

**Date:** 2026-11-19  
**Status:** Accepted  

## Context
Stage 1 requires a physically grounded MuJoCo MJCF model of a Syrian hamster (*Mesocricetus auratus*) with ~16 actuated DoF, separated visual and collision geometry, torque-limited position actuators, and versioned observation/action contracts in `contracts/`. No calibration photos or real robot exist; proportions must be grounded in published Syrian hamster morphometrics and cross-checked against our video measurements.

## Proportions, Assumptions, and Uncertainties
| Parameter | Value in `hamster.xml` | Published Syrian Range | Uncertainty / Notes |
| :--- | :---: | :---: | :--- |
| Total mass | `0.125 kg` | `0.100–0.140 kg` | ±15 g; distributed as pelvis `0.042`, torso `0.038`, head `0.020`, 4 legs `0.024`, tail `0.001` |
| Nose-to-rump length | `~0.145 m` | `0.130–0.160 m` | ±10 mm; no metric fiducial in videos |
| Pelvis / torso width | `0.062 m` / `0.056 m` | `0.055–0.068 m` | Stout pear-shaped Syrian silhouette |
| Standing dorsal height | `~0.068 m` | `0.055–0.070 m` | Cross-checked with `hamster-video1.mp4` crouched ratio `height/length = 0.705` |
| Limb lengths (fore / hind) | `0.034 m` / `0.038 m` | ~22–26% of body length | Cross-checked with `hamster-video6.mp4` wheel diameter (`1035.9 px`) |
| Tail length | `0.013 m` | `0.012–0.016 m` | 1 passive DoF (`stiffness=0.02`, `damping=0.005`) |

## Decisions
1. **16 Actuated DoF + 1 Passive Tail DoF:**
   - Spine: `spine_pitch`, `spine_yaw` (2)
   - Neck/head: `neck_pitch`, `neck_yaw` (2)
   - Four legs × 3 (`hip_abd`, `hip_pitch`, `knee_pitch`) (12)
   - Tail: `tail_pitch` (passive spring-damper)
2. **Separated Visual (`group="2"`) & Collision (`group="3"`) Geometry:**
   - Collision geoms use simple capsules and spheres with parent-child `<contact><exclude>` pairs to prevent false self-collision while maintaining crisp floor contact.
   - Visual geoms render golden-agouti coat, cream belly/cheeks, rosy ears, eyes, pink nose, and pink paws for unambiguous visual inspection.
3. **Actuator Gains & Torque Limits:**
   - Position servos (`kp=0.80, kv=0.03, forcerange=[-0.25, 0.25] N·m` on legs; `kp=1.00, kv=0.04, forcerange=[-0.30, 0.30] N·m` on spine; `kp=0.40, kv=0.02, forcerange=[-0.15, 0.15] N·m` on neck).
   - Physics timestep `0.002 s` (500 Hz) with Newton solver (`iterations=60`) and 50 Hz RL control loop (10 substeps/action).
4. **Versioned Contracts (`contracts/locomotion_contracts.py`):**
   - `MODEL_VERSION = "hamster_mjcf_v1.0.0"`
   - `OBS_CONTRACT_VERSION = "locomotion_obs_v1.0.0"` (fixed 64-dim vector with zero-padded command & reference-phase slots per `microduck_rl` pattern).
   - `ACTION_CONTRACT_VERSION = "locomotion_act_v1.0.0"` (16-dim joint position targets with `clamp_joint_targets()` safety layer).
