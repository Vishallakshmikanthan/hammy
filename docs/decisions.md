# HAMMY — Architecture & Technical Decisions Log

## 2026-11-09: Environment Initialization & MCP Setup
- **Blender Version:** Blender 5.2.3 LTS verified.
- **Python Version:** 3.13.13 bundled with Blender.
- **Hardware Acceleration:** NVIDIA GeForce RTX 5070 Laptop GPU detected with OptiX Ray-Tracing & CUDA. OptiX configured as primary compute device for Cycles renders.
- **Bridge Setup:** Resolved port 9876 conflict between default extension and `mcp_connector_v2.py`. Live WebSocket server verified responsive at ~100ms latency.
- **Scripts Scaffold:** Initialized `blender/scripts/common.py` with idempotent collection and material management, metric unit enforcement, and dated scene snapshots.
- **Headless Pipeline:** Verified `blender -b -P blender/scripts/00_check_env.py` runs cleanly in background mode.

## 2026-11-13: P1.4 Cognitive Memory & Observation V2 Contract
- **Versioned Contract:** Introduced `ObservationV2` (`2.0.0`) in `contracts/schemas.py` and exported `observation_v2.schema.json`. Backward-compatible with `ObservationV1` (`1.0.0`).
- **Spatial Grid Discretization:** Selected 8x4 grid covering cage bounds `[-0.46, 0.46]` x `[-0.21, 0.21]` m (~0.11m cell size, matching ~1 hamster body length). Pooled to 4x2 coarse sectors (8 floats) for compact NN input.
- **Object Value & Recency Model:** Exponential moving average (alpha=0.25), saturating confidence (+0.30/visit, half-life ~11 min), recency normalized with tau=300 s.
- **Memory Feature Vector:** 28 floats (18 object appraisal + 10 spatial familiarity) appended to 41 base features, yielding 69-dim vector.
- **Habitat Randomisation:** Dynamic/scheduled relocation of food bowl and hideout with 0.14m clearance, verified by `WorldEventV1` logging.

## 2026-11-13: P1.5 Skill-Outcome Empirical Models for Background Life
- **Empirical Modeling Choice:** Parametric conditional distributions for each of the 8 skills fitted from 1,200 physics rollouts stored in `simulation/datasets/skill_outcomes.parquet`.
- **Event Origin (Rule 2):** Every outcome from `sample_skill_outcome()` enforces `origin = EventOrigin.SAMPLED_FROM_SKILL_MODEL`.
- **Validation:** Held-out testing (240 test rollouts) verified high success prediction accuracy and bounded duration MAE.
- **30-Day Catch-Up Fidelity:** Demonstrated statistical proximity (Wasserstein distance < 0.09 across all 6 drives) and a 48.5x wall-clock execution speedup (0.29s vs 14.1s for 30 full days).

## 2026-11-14: P2.1 Relational Schema, Concurrency & Security
- **16 Core Tables:** Relational schema declared in SQLAlchemy ORM (`infrastructure/database/models.py`) and raw PostgreSQL DDL (`infrastructure/database/schema.sql`).
- **Idempotency Guarantee (Rule 4):** Primary key uniqueness on `commands.command_id` guarantees duplicate command rejection at the database engine level.
- **Append-Only Immutability:** Implemented engine-level triggers on `world_events` (PL/pgSQL for PostgreSQL, `BEFORE UPDATE` trigger raising abort on SQLite) preventing in-place mutations.
- **Optimistic Concurrency:** Version counters on `pet_state` and `worker_leases` ensure conflict-free state mutations across distributed simulation workers.
- **Row-Level Security (RLS):** Supabase RLS policies configured across all user-facing tables, isolating user tenants while granting simulation worker daemons full operation via the service role key.
- **Seed Pipeline:** Automated seeding script (`infrastructure/database/seeds.py` & `seed.sql`) providing deterministic initialization of 1 user, 1 pet, 1 habitat, and 6 standard interactive props from `simulation/habitats/v1.json`.

## 2026-11-14: P2.2 World Worker with Leases & Catch-Up
- **Distributed Single-Writer:** Implemented per-pet mutual exclusion lease manager (`services/world_worker/lease.py`) with CAS version increments and automatic takeover upon TTL expiry.
- **Bounded Catch-Up Slicing:** Catch-up simulation (`services/world_worker/catchup.py`) slices long real-time offline durations into bounded chunks (max 3,600s / 50 steps per tick), updating `last_simulated_at` proportionally and logging `catch_up_in_progress` / `catch_up_completed` summary events.
- **Deterministic Deduplication:** Event IDs derived deterministically from `(pet_id, world_tick, event_type, seed)`, ensuring replays and retries never duplicate event records.
- **Pause Semantics:** When `pet_state.is_paused` is active, real time advances without stepping simulation or modifying drive vectors, updating `last_simulated_at` to prevent backlog accumulation.
- **Atomic Rollback:** Complete transaction rollback verified via `scripts/test_worker_rollback.py`, ensuring zero event leakage or corrupted state upon mid-transaction worker failure.

## 2026-11-14: P2.3 FastAPI Backend & Shared Command Handlers
- **Shared Command Layer:** Built `CommandHandler` in `services/commands/handler.py` supporting both FastAPI routes and Telegram bot commands. Enforces client-side `command_id` idempotency and parameter boundaries before committing state.
- **Idempotent Care Operations:** Acceptance test verified that submitting duplicate feeding commands (`test_feeding_twice_with_same_command_id_adds_food_once`) adds food to the bowl exactly once and replays cached results.
- **Multi-Tenant Security:** Implemented Supabase JWT verification (`services/api/auth.py`) and per-pet route authorization (`verify_pet_access`), rejecting unauthenticated requests (401) and cross-tenant access attempts (403).
- **Blueprint Coverage:** Exposed all 14 blueprint routes across `pets`, `habitat`, `care`, `simulation`, `system/health`, and real-time WebSocket (`/api/v1/pets/{pet_id}/ws`).
- **Protection & Docs:** In-memory sliding-window rate limiter (`RateLimiter`) with 429 response enforcement and auto-generated OpenAPI documentation at `/docs` and `/openapi.json`.

## 2026-11-14: P2.4 Telegram Bot & Notification Outbox
- **Outbox Pattern:** Implemented asynchronous outbox worker (`services/notification_worker/outbox.py`) decoupling world simulation from Telegram HTTP availability. Telegram outages cannot block the world simulation.
- **Delivery Guarantees:** Exponential backoff with jitter and dead-letter state transitions after 3 attempts; verified that one event produces exactly one delivered message on the Telegram API.
- **Secure Chat Binding:** Built one-time code pairing flow (`/start` generates `HAMMY-XXXX`, verified via API `POST /api/v1/notifications/telegram/confirm`). Unbound chats are rejected.
- **Conversational Care via Shared Layer:** Bot commands (`/status`, `/feed`, `/water`, `/pause`, `/resume`, `/report`) route exclusively through `CommandHandler`, preserving rule consistency and client idempotency.
- **Daily Digest with Plain Language Origins:** Constructed digest solely from recorded `world_events`, mapping enum origins to explicit text badges ("Predicted by behavioral AI model", "Simulated in full 3D physics", "Care action / Game rule").
- **Quiet Hours & Deduplication:** Added quiet hours delivery postponement and duplicate suppression window (300s).

## 2026-11-14: P2.5 Minimal Brain Observatory
- **Tech Stack:** React 18, TypeScript, Vite, Vitest, and Testing Library in `web/`.
- **Zero Client-Side Simulation Rule:** The frontend acts as a pure reactive viewer; drive evolution, age, and physics are strictly authoritative on the server and never approximated on the client.
- **WebSocket State Restoration:** Reconnecting the WebSocket restores the latest state snapshot (`snapshot` frame containing state version, sim time, drives, pause flag), verified via end-to-end tests.
- **Badge Auditability:** The events feed displays the last 50 events from PostgreSQL, rendering required `origin` (`observed_physics`, `sampled_from_skill_model`, `rule`) and `behaviour_type` (`learned`, `scripted`, `rule`) badges.
- **Controls & Status Banner:** Global banner surfaces paused/running state, real-time scale, last world update, connection indicator, and interactive pause/resume triggers.



