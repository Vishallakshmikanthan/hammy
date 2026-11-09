# HAMMY — Versioned Contracts Specification (`/contracts`)

All payloads crossing between the physics simulation (`simulation/`), AI cognition & policies (`ai/`), persistent world worker (`services/world-worker/`), FastAPI backend (`services/api/`), Telegram bot, and future ROS 2 / ONNX hardware adapters are validated by `contracts/schemas.py` and exported as JSON Schemas in `contracts/json_schema/`.

## 1. Non-Negotiable Honesty & Origin Enums
- **`BehaviourType` (`learned` | `scripted` | `rule`):** Mandatory on every `ActionV1` and `WorldEventV1`. Scripted or rule-based controllers must never be labelled `learned`.
- **`EventOrigin` (`observed_physics` | `sampled_from_skill_model` | `rule`):** Mandatory on every `WorldEventV1` so the Brain Observatory and Telegram daily digest always state whether an event was physically simulated or sampled during background catch-up.

## 2. Version Registry (`SUPPORTED_SCHEMA_VERSIONS`)
- `observation`: `["1.0.0"]` (`contracts/json_schema/observation_v1.schema.json`)
- `action`: `["1.0.0"]` (`contracts/json_schema/action_v1.schema.json`)
- `event`: `["1.0.0"]` (`contracts/json_schema/event_v1.schema.json`)
- `command`: `["1.0.0"]` (`contracts/json_schema/command_v1.schema.json`)
- `morphology`: `["simple_agent_v1", "syrian_quadruped_v1"]`
- `environment`: `["habitat_v1"]`

Any payload with an unknown or mismatched version raises `SchemaCompatibilityError` (or Pydantic `ValidationError`).

