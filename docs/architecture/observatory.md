# HAMMY — Brain Observatory Architecture

## Overview
The **HAMMY Brain Observatory** is a real-time web dashboard built with React 18 and TypeScript (`web/`). It provides caretakers, researchers, and developers with transparent, authoritative observability into the simulated creature's active brain, policy context, homeostatic drives, and world events.

---

## Architectural Principles

### 1. Strict Authoritative Server (No Client Simulation)
In strict adherence to the project specification, **the frontend never simulates or predicts internal dynamics**. 
- Drive depletion, age progression, circadian drift, or physical movements are **never** calculated client-side.
- The UI is purely a reflection of authoritative PostgreSQL database records served through FastAPI REST endpoints and real-time WebSocket state snapshots.
- Every row in the events feed links directly to an immutable database record (`world_events.event_id`).

### 2. Behavioral & Origin Transparency
Every event and decision displayed in the Observatory surfaces the core audit labels required by project rules:
- **Event Origin (Rule 2):**
  - `observed_physics`: Outcome calculated during full 3D physics integration.
  - `sampled_from_skill_model`: Outcome sampled from statistical parametric skill distributions during fast background catch-up.
  - `rule`: Discrete deterministic game rule or user care action.
- **Behaviour Type (Rule 1):**
  - `learned`: Decision made by trained neural policy models (e.g. PPO / reinforcement learning).
  - `scripted`: Decision made by hierarchical state machine or homeostatic priority logic.
  - `rule`: Hard-coded biological constraint or environmental trigger.

---

## Component Structure

```
web/src/
├── api.ts                         # Typed REST client with error handling & auth
├── types.ts                       # Versioned contract interfaces matching backend models
├── hooks/
│   └── usePetObservatory.ts       # Hydration, WebSocket streaming & auto-reconnect restoration
├── components/
│   ├── ObservatoryBanner.tsx      # Paused/running status, time scale, update time, pause/resume
│   ├── ActiveBrainView.tsx        # Active skill, policy/schema/morphology versions, spatial telemetry
│   ├── DrivesPanel.tsx            # Hunger, thirst, energy, comfort, stress, curiosity, circadian phase
│   ├── EventsFeed.tsx             # Last 50 immutable events with origin & behaviour badges
│   └── Observatory.tsx            # Master grid container & error boundaries
├── App.tsx                        # Root layout, navigation & multi-pet selector
├── main.tsx                       # React DOM root mounting
└── index.css                      # Professional dark dashboard styling & responsive grid
```

---

## WebSocket Protocol & State Restoration

The Observatory establishes a persistent WebSocket connection to `/api/v1/pets/{pet_id}/ws`:
1. **Initial Hydration:**
   - On initial load, the dashboard fetches `/api/v1/pets/{pet_id}`, `/api/v1/pets/{pet_id}/state`, and `/api/v1/pets/{pet_id}/events?limit=50`.
2. **Streaming Snapshot:**
   - Upon connection, the server immediately emits a `snapshot` frame containing the authoritative state version, simulation time, drive vector, and pause flag.
3. **Reconnection & Resilience:**
   - If the network drops or the server restarts, `usePetObservatory` detects the close event, transitions connection status to `reconnecting`, and attempts reconnection using backoff.
   - Upon reconnection, the server immediately pushes the freshest authoritative state snapshot. State is restored without page refresh and without any desynchronization.

