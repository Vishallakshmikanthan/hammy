# HAMMY — Coding-Agent Prompt Plan

*Copy-paste prompts for Claude Code, Cursor, or any coding agent, in build order. Pairs with the Implementation Plan and the Realistic Design Specification. Each prompt is one working session with a clear deliverable and acceptance test.*

## How to use this file

1. Start every session by pasting the **Master Context Prompt** (Section 1).
2. Run **one numbered prompt per session**. Do not chain several; agents drift on big requests.
3. After each session: run the tests, read the diff, commit with the prompt number in the message (for example `P1.2: homeostatic drives`).
4. If a prompt fails its acceptance test, use the **Repair Prompt** (Section 9) rather than rewriting the original.
5. Keep a `docs/decisions/` entry for anything the agent chose that you did not.
6. Never let the agent skip tests, invent benchmark numbers, or claim a behaviour is "learned" without an experiment report.

## 1. Master Context Prompt (paste at the start of every session)

```text
You are a senior engineer on HAMMY, an autonomous AI virtual hamster pet.

PROJECT: A persistent virtual hamster that lives in a physically simulated habitat (MuJoCo), is rendered in a realistic browser 3D view (Three.js / WebGPU), has learned behaviour (RL), memory and drives, keeps living in the cloud when the browser is closed, and reports to its parent through Telegram. The architecture must later allow a physical robot via shared observation/action contracts, ONNX and ROS 2.

NON-NEGOTIABLE RULES:
1. Honesty: every behaviour is labelled `learned`, `scripted`, or `rule` in code and logs. Never present scripted behaviour as learned.
2. Every event records its origin: `observed_physics`, `sampled_from_skill_model`, or `rule`.
3. The server is authoritative. The frontend never advances hunger, age, resources or memory.
4. World updates are transactional and idempotent (idempotency keys, DB constraints, leases).
5. Observation and action schemas are versioned in /contracts and every policy checkpoint records the schema, morphology and environment versions it was trained against. Reject incompatible policies.
6. Reproducibility: every experiment stores config, seed, code version, environment version, checkpoint and metrics.
7. Do not store per-timestep physics in PostgreSQL. Store events and summaries; trajectories go to files/object storage.
8. No secrets in source control. Secrets come from environment variables.
9. Write tests with the code. Do not claim a result you did not run. If you cannot run something, say so.
10. Check each dependency's license; log reused code in THIRD_PARTY_NOTICES.md.

STACK: Python 3.11+, MuJoCo (+MJX if benchmarks justify), PyTorch, Gymnasium, FastAPI, PostgreSQL (Supabase), ONNX/ONNX Runtime, React + TypeScript, Three.js (WebGPU with WebGL2 fallback), Telegram Bot API.

REPO LAYOUT: monorepo with apps/web, services/{api,world-worker,simulation-worker,notification-worker}, ai/, training/, simulation/, contracts/, infrastructure/, docs/.

WORKFLOW: First restate the task and list assumptions. Then plan briefly. Then implement in small commits. Finish with: what changed, how to run it, tests run and results, known gaps, and next suggested step. Ask before making any decision listed in docs/decisions as 'to confirm'.
```

## 2. Phase 0 — Foundations

### P0.1 — Environment and benchmark

```text
Task: Verify the dev environment and benchmark physics throughput.

Context: Windows laptop, NVIDIA RTX 5070 Laptop GPU (8 GB VRAM, Blackwell), 32 GB RAM. Prefer WSL2 Ubuntu if GPU-parallel tooling is easier there.

Do:
1. Write scripts/check_env.py that prints Python version, torch version, torch.version.cuda, torch.cuda.is_available(), GPU name and VRAM, MuJoCo version, and whether MJX imports.
2. If PyTorch cannot use the GPU, diagnose and tell me the exact install command for a build with CUDA 12.8+ support. Do not guess; reference the official selector.
3. Write scripts/bench_mujoco.py: load a small quadruped MJCF (use a MuJoCo Menagerie model if available, otherwise a minimal 12-joint test model), step it with random actions for N steps, and report CPU steps/sec for 1, 4 and 8 processes.
4. If MJX is available, write scripts/bench_mjx.py reporting steps/sec for 256, 1024 and 4096 parallel envs and GPU memory use.
5. Save results to docs/research/benchmarks.md with machine info and date.

Acceptance: both scripts run end-to-end, results are in the doc, and the doc states which training stack the numbers support. No invented numbers.
```

### P0.2 — Repo scaffold and contracts

```text
Task: Create the monorepo scaffold and versioned contracts.

Do:
1. Create only the directories needed for Phases 0–2 (see layout). Add README.md, pyproject.toml, .gitignore, THIRD_PARTY_NOTICES.md, docs/decisions/0001-template.md.
2. In /contracts create JSON Schemas (and matching Pydantic models in a shared Python package) for: observation v1 (generic agent), action v1, event v1 (include `origin` enum: observed_physics | sampled_from_skill_model | rule; `behaviour_type` enum: learned | scripted | rule), command v1 (with command_id idempotency key).
3. Add a schema-version registry and a function that rejects unknown or incompatible versions.
4. Add unit tests that validate good and bad payloads.

Acceptance: pytest passes, invalid payloads are rejected, schemas are documented in docs/architecture/contracts.md.
```

## 3. Phase 1 — Vertical slice with a simplified body

### P1.1 — Habitat environment with a simple body

```text
Task: Build the first MuJoCo habitat environment with a simple controllable body.

Do:
1. simulation/models/simple_agent/: an MJCF with a small body that accepts forward-speed and turn-rate commands (planar locomotion is fine). Mass, size and speed should be roughly hamster-scale (about 0.12 kg, 15 cm long).
2. simulation/habitats/v1.xml: a rectangular enclosure with a food bowl, water source, hideout, tunnel (a simple tube), and a wheel placeholder. Give each object a stable id and affordance metadata in a sidecar JSON (id, type, pose, affordances, resource state).
3. A Gymnasium environment `HabitatEnv` that follows the observation/action contract, with seeded resets and a configurable episode length.
4. A viewer script that renders the scene with mujoco.viewer.
5. Tests: model loads, steps without NaN, reset is deterministic given a seed, object ids are unique.

Acceptance: tests pass; a random-action rollout runs 10k steps stably.
```

### P1.2 — Drives and homeostatic reward

```text
Task: Implement internal drives and a homeostatic reward.

Do:
1. ai/cognition/drives.py: state vector (hunger, thirst, energy, comfort, stress, curiosity) normalised to [0,1], plus a circadian phase variable. Document the update rules and units. Hamsters are crepuscular/nocturnal, so energy and activity should follow a day/night cycle.
2. Homeostatic reward: reward = reduction in summed squared deviation from per-drive set points. Expose each drive's term separately in `info` for logging.
3. Config file for set points and rates; no magic numbers in code.
4. Unit tests for bounds, monotonic behaviour (hunger rises over time; eating lowers it) and reward sign.
5. A script that runs a scripted baseline for 100 simulated days and plots time-in-healthy-range per drive.

Acceptance: tests pass; plot saved; baseline numbers recorded in docs/research/baselines.md labelled `scripted`.
```

### P1.3 — Skill library and high-level policy

```text
Task: Implement a skill library (options) and a learned high-level policy over it.

Do:
1. ai/policies/skills.py: define Skill with initiation condition, low-level controller (initially a simple navigation controller labelled `scripted`), termination condition. Skills: approach_food, eat, drink, explore_area, rest, hide, enter_tunnel (placeholder).
2. A semi-Markov high-level environment where one step = one skill execution (with variable duration).
3. Train the high-level policy with PPO (Stable-Baselines3 is fine here) using the homeostatic reward.
4. Compare against two baselines: random skill selection and a hand-coded priority rule. Report time-in-healthy-range across 5 seeds.
5. Save the experiment config, seeds and results under training/experiments/.

Acceptance: learned policy beats random and is compared honestly to the rule baseline, with confidence intervals. State clearly if it does not.
```

### P1.4 — Memory features that change decisions

```text
Task: Add memory that feeds into the high-level policy.

Do:
1. ai/memory/: per-object value estimates (running mean with confidence and decay), a coarse spatial familiarity grid, and recency features (time since last visit per object).
2. Append these as inputs to the high-level observation (new versioned observation schema).
3. Add habitat randomisation: periodically move the food bowl or hideout.
4. Run the ablation: memory on vs. off, 5 seeds each, measuring homeostasis and adaptation speed after a rearrangement.

Acceptance: ablation report in docs/research/ablation-memory.md. If memory does not help, say so and propose why.
```

### P1.5 — Skill-outcome models for background life

```text
Task: Build the skill-outcome dataset and model used for background (browser-closed) simulation.

Do:
1. A headless runner that executes each skill many times under varied conditions (distance, obstacles, drive levels, habitat layout) and logs: success, duration, energy cost, collision count, final state.
2. Store results as Parquet with the seed, environment version and skill version.
3. Fit simple empirical models (conditional distributions or small gradient-boosted/NN models) that sample outcomes given context.
4. Validate: sampled-outcome statistics match held-out physics episodes (report error per skill).
5. Expose `sample_skill_outcome(skill, context, rng)` and mark every use with origin `sampled_from_skill_model`.

Acceptance: validation report; a 30-day catch-up run uses only sampled outcomes and produces drive trajectories statistically close to a full-physics run.
```

## 4. Phase 2 — Persistence, API, Telegram

### P2.1 — Database schema and migrations

```text
Task: Create the PostgreSQL schema and migrations.

Do:
1. Tables: users, pets, pet_state (with optimistic concurrency version, last_simulated_at, schema_version), habitats, habitat_objects, care_actions, world_events (append-only, unique event_id), memories, behaviour_stats, policy_versions, simulation_runs, training_runs, notification_preferences, notification_outbox, worker_leases, commands (unique command_id).
2. Use SQL migrations (Alembic or plain SQL) and row-level security notes for Supabase.
3. Constraints that enforce idempotency (unique idempotency keys) and prevent updating world_events.
4. Seed script for one user, one pet, one habitat.
5. Tests against a local Postgres (Docker).

Acceptance: migrations apply cleanly from empty; duplicate command_id inserts fail; world_events cannot be updated.
```

### P2.2 — World worker with leases and catch-up

```text
Task: Implement the persistent world worker.

Do:
1. services/world-worker: acquire a per-pet lease, read pet_state, compute elapsed time, run bounded catch-up chunks using the skill-outcome models and the high-level policy, write events and the new state in one transaction, release the lease.
2. Deterministic event ids derived from (pet_id, world_tick, event_type, seed) so retries cannot duplicate events.
3. Time scaling with an explicit simulated-age vs. real-time mapping stored in pet_state.
4. Pause/resume that actually stops progression.
5. Cap catch-up work per run (for example, at most N chunks) and continue next tick if more remains. Write a catch-up summary event.
6. Entrypoint that works as a scheduled job (one tick, then exit) and as a looping process.
7. Tests: crash mid-update leaves state consistent; double-run produces no duplicate events; a 7-day gap completes in bounded work; pause stops advancement.

Acceptance: all tests pass; a script that kills the worker mid-transaction proves rollback.
```

### P2.3 — FastAPI backend and command handlers

```text
Task: Build the parent API.

Do:
1. Endpoints from the blueprint: pet, state, events, memories, habitat; care/feed, care/water, enrichment, habitat/objects, simulation/pause, simulation/resume; system/health.
2. Authentication (Supabase JWT verification) and per-pet authorisation on every route.
3. Command validation (allowed object types, quantities, bounds) and idempotency by command_id.
4. A WebSocket endpoint that pushes state and event updates.
5. Rate limiting.
6. One shared command-handler layer used by both the API and the Telegram bot.
7. OpenAPI docs and tests (including a duplicate-command test and an unauthorised-access test).

Acceptance: tests pass; feeding twice with the same command_id adds food once.
```

### P2.4 — Telegram bot and notification outbox

```text
Task: Implement the Telegram integration.

Do:
1. services/notification-worker: outbox pattern with retries, backoff, dead-letter state, and delivery status.
2. Chat binding flow: /start returns a one-time code the parent confirms on the website; unbound chats are rejected.
3. Commands: /status, /feed, /water, /pause, /resume, /report, calling the shared command handlers (never writing the DB directly).
4. Daily digest built only from recorded events; include event origin (observed vs sampled vs rule) in plain language.
5. Quiet hours, per-category preferences, rate limits, duplicate suppression.
6. Token from environment variable only.
7. Tests with a mocked Telegram API: one event produces exactly one message even after retries; Telegram outage does not block the world worker.

Acceptance: tests pass; a manual test script sends one verified message to my bot.
```

### P2.5 — Minimal Brain Observatory

```text
Task: Build a minimal Observatory page in React + TypeScript.

Do:
1. Page showing active skill, drive values, last 50 events with origin and behaviour_type badges, policy version and schema versions.
2. Data from the API only; no client-side simulation.
3. A visible banner showing paused/running state, time scale, and last world update time.
4. Component tests and one end-to-end test with a mocked API.

Acceptance: tests pass; reconnecting the WebSocket restores the latest state; nothing shown is invented (every line links to a stored record).
```

## 5. Phase 3 — Realistic hamster rendering

*Art tasks (sculpting, grooming, textures) are done by you in Blender following the Design Specification. These prompts cover the engineering around them.*

### P3.1 — Fur rendering prototype (benchmark first)

```text
Task: Prototype three fur techniques in Three.js and benchmark them.

Do:
1. A standalone test page rendering a placeholder furry sphere/capsule with (a) shell texturing, (b) shells plus silhouette hair-card fins, (c) WebGPU compute strand rendering if the browser supports it (feature-detect, skip otherwise).
2. Parameters panel: shell count, hair length, density, clumping, gravity droop, wind off by default, rim-light strength.
3. An FPS and frame-time overlay, and a script/protocol to record results on this laptop and on a mid-range phone.
4. Write docs/research/fur-benchmark.md with measurements and screenshots, plus a recommendation. Do not claim numbers you did not measure.

Acceptance: working demo; benchmark doc filled with real measurements for at least the laptop.
```

### P3.2 — Hamster asset loader and visual rig

```text
Task: Load the hamster glTF and drive its visual rig.

Context: I will provide hamster.glb with a skeleton, blend shapes (cheek_pouch_left/right, blink, mouth_open, etc.) and LOD meshes.

Do:
1. A loader that validates required bones, blend shapes and LODs and reports missing ones clearly.
2. A pose-application layer that takes physics output (root pose, foot contacts, velocity) and drives the main rig.
3. A procedural layer, each module toggleable and tunable: breathing, whisker twitch (sniff-synchronised), ear orientation, blink and gaze micro-movements, tail, spring-bone fur/skin jiggle, cheek pouch fill 0–1.
4. A debug panel to preview each layer on an idle hamster.
5. LOD switching by camera distance and a quality preset system (low/medium/high/ultra).

Acceptance: demo scene runs at the target frame rate on the high preset on this laptop; each procedural module can be toggled; missing-asset errors are explicit.
```

### P3.3 — Environment and lighting

```text
Task: Build the realistic cage scene in Three.js.

Do:
1. Load the cage glTF, apply PBR materials, HDRI image-based lighting, soft shadows, ambient occlusion and subtle depth of field.
2. Day/night lighting cycle driven by server time.
3. Deformable bedding visual (heightfield or instanced particles) that responds to the hamster's paw positions.
4. Small dust motes, water droplet effects on the bottle, and food items as instanced meshes.
5. Quality presets and a performance HUD.

Acceptance: scene runs on the high preset; mobile low preset is usable; screenshots saved for A/B review.
```

## 6. Phase 4 — Learned locomotion

### P4.1 — Stand-in quadruped training pipeline

```text
Task: Train stand/walk/turn/stop with an existing small quadruped to prove the pipeline.

Do:
1. Use the stack chosen in docs/research/benchmarks.md (MJX/MuJoCo Playground or rsl_rl/skrl). Do not use plain Stable-Baselines3 on CPU for large runs.
2. Observation: joint pos/vel, body orientation, angular velocity, previous action, command. Action: joint position targets with limits.
3. Reward terms logged separately: velocity tracking, orientation, torque/energy, action rate, foot slip, falls.
4. Curriculum driven by measured success: stand, perturbation recovery, walk, turn, stop.
5. Domain randomisation: friction, mass, actuator strength, latency, sensor noise within plausible ranges.
6. Evaluation script separate from training; 5 seeds; report success rate, falls per episode, speed tracking error.
7. ONNX export and a test comparing PyTorch and ONNX outputs.

Acceptance: reproducible eval report; ONNX output matches within tolerance.
```

### P4.2 — Hamster morphology and style

```text
Task: Create the hamster MJCF and add a motion-style reward.

Do:
1. Build hamster.xml from the Design Specification's proportions: stout body, 2–3 spine joints, 3 joints per leg, simple collision primitives, separate from visual meshes. Validate masses, inertias, limits, stability.
2. Version the morphology; checkpoints record it.
3. Provide a keypoint ingestion script for hamster gait data (output from a pose-estimation tool) and an AMP-style discriminator reward as an optional experiment, with a plain-RL baseline.
4. Compare gait metrics (stride frequency, duty factor, speed range) to the reference data.

Acceptance: stable standing; walking benchmark; style experiment report with honest comparison to the baseline.
```

## 7. Phases 5–8 — Integration, behaviours, cognition, cinematics

### P5.1 — Trajectory clips and live replay

```text
Task: Generate server-side episode clips and replay them in the browser.

Do:
1. Define a compact clip format (fixed-rate keyframes: root pose, joint angles, contacts, skill id, seed, origin tag).
2. A simulation-worker job that renders a bounded episode into a clip and uploads it to object storage.
3. Frontend player with interpolation and seamless clip chaining.
4. A determinism test: replaying the stored seed reproduces the same clip within tolerance.

Acceptance: reconnecting after being offline shows a coherent continuation; clip metadata shows origin.
```

### P6.1 — One behaviour at a time (template)

```text
Task: Implement the hamster behaviour: <BEHAVIOUR: cheek stuffing | hind-leg standing | grooming | wheel running | digging | nesting>.

Do:
1. State the behaviour's implementation type honestly (learned / scripted-with-learned-selection / rule) in docs/research/behaviours.md.
2. Define its skill (initiation, termination, drive effects) and its visual treatment (animation clips, procedural layers) per the Design Specification.
3. Integrate it into the high-level policy as an additional skill and retrain/evaluate selection.
4. Collect skill-outcome data for background mode.
5. Add a side-by-side comparison page with reference footage for review.

Acceptance: appears in Observatory with correct labels; passes my realism review checklist.
```

### P7.1 — Curiosity and autonomy report

```text
Task: Add RND curiosity and generate the autonomy report.

Do:
1. Implement RND with intrinsic reward decay and a safeguard against noisy-TV behaviour.
2. Run ablations: memory on/off, curiosity on/off, 5 seeds each.
3. Metrics: homeostasis time-in-range, behavioural diversity, routine formation over 30 simulated days, adaptation after habitat rearrangement.
4. Generate a Training Lab page and a Markdown report from stored experiment data only.

Acceptance: report states which claims the data supports and which it does not.
```

### P8.1 — Cinematic moments (Blender Cycles pipeline)

```text
Task: Re-render a logged episode offline with Blender Cycles.

Do:
1. A Blender Python script that loads the hamster .blend (with full hair-curve groom), the cage .blend, and a clip file, applies the animation, sets camera/lighting, and renders to MP4 with denoising and optional audio.
2. Camera presets (low macro, three-quarter, wide) and automatic framing from the trajectory.
3. Render-time budget settings (samples, resolution) and a queue that runs when the GPU is idle.
4. Telegram delivery of the clip with a caption built from verified events only.

Acceptance: a daily clip is generated from a stored seed and delivered; re-running with the same seed gives the same result.
```

## 8. Review prompts (use after any phase)

```text
Task: Review this phase against the project rules.
Check: honesty labels present; event origins recorded; idempotency tests exist; no secrets; schema versions enforced; tests meaningful (not trivially passing); no invented benchmark numbers; documentation matches the code. List problems by severity with file/line references. Do not fix anything yet.
```

```text
Task: Write the experiment report for <experiment>.
Include config, seeds, code version, environment version, checkpoint id, metrics with confidence intervals, comparison to baseline, failure cases, and an honest conclusion. Do not describe the result as improvement unless the comparison supports it.
```

## 9. Repair prompt

```text
The previous session did not meet its acceptance criteria.
Failing: <paste failing test output or describe the issue>.
Do not rewrite working parts. Diagnose the root cause first and explain it. Then make the smallest change that fixes it, add a regression test, rerun the full test suite, and report results.
```

## 10. Order of execution (summary)

P0.1 → P0.2 → P1.1 → P1.2 → P1.3 → P1.4 → P1.5 → P2.1 → P2.2 → P2.3 → P2.4 → P2.5, with P3.1 → P3.2 → P3.3 running in parallel from about week 3. Then P4.1 → P4.2 → P5.1 → P6.1 (repeat per behaviour) → P7.1 → P8.1.

Do not start P4 until P1–P2 acceptance tests pass. That ordering is what keeps locomotion risk from blocking the rest.
