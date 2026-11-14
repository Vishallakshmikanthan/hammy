-- ==============================================================================
-- HAMMY — P2.1: PostgreSQL DDL Migration with Supabase Row Level Security (RLS)
-- File: infrastructure/database/schema.sql
-- ==============================================================================

-- 0. Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==============================================================================
-- 1. USERS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY, -- Matches Supabase auth.users.id
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ==============================================================================
-- 2. PETS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS pets (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    species VARCHAR(50) DEFAULT 'syrian_hamster' NOT NULL,
    morphology_version VARCHAR(50) DEFAULT 'simple_agent_v1' NOT NULL,
    birth_date TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pets_user_id ON pets(user_id);

-- ==============================================================================
-- 3. PET STATE TABLE (Optimistic Concurrency Control)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS pet_state (
    pet_id VARCHAR(64) PRIMARY KEY REFERENCES pets(id) ON DELETE CASCADE,
    version BIGINT DEFAULT 1 NOT NULL, -- Optimistic concurrency counter
    schema_version VARCHAR(20) DEFAULT '2.0.0' NOT NULL,
    environment_version VARCHAR(50) DEFAULT 'habitat_v1' NOT NULL,
    sim_time_sec DOUBLE PRECISION DEFAULT 0.0 NOT NULL,
    simulated_age_days DOUBLE PRECISION DEFAULT 0.0 NOT NULL,
    real_time_scale DOUBLE PRECISION DEFAULT 1.0 NOT NULL,
    last_simulated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    is_paused BOOLEAN DEFAULT FALSE NOT NULL,
    drives JSONB NOT NULL,
    position_xyz JSONB NOT NULL,
    yaw_rad DOUBLE PRECISION DEFAULT 0.0 NOT NULL,
    velocity_xy JSONB DEFAULT '[0.0, 0.0]'::jsonb NOT NULL,
    angular_velocity_z DOUBLE PRECISION DEFAULT 0.0 NOT NULL,
    inside_hideout BOOLEAN DEFAULT FALSE NOT NULL,
    inside_tunnel BOOLEAN DEFAULT FALSE NOT NULL,
    on_wheel BOOLEAN DEFAULT FALSE NOT NULL,
    cheek_pouch_fill DOUBLE PRECISION DEFAULT 0.0 NOT NULL,
    active_skill VARCHAR(50),
    active_skill_started_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ==============================================================================
-- 4. HABITATS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS habitats (
    id VARCHAR(64) PRIMARY KEY,
    pet_id VARCHAR(64) NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    environment_version VARCHAR(50) DEFAULT 'habitat_v1' NOT NULL,
    name VARCHAR(100) NOT NULL,
    dimensions_xyz JSONB NOT NULL,
    floor_bounds JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_habitats_pet_id ON habitats(pet_id);

-- ==============================================================================
-- 5. HABITAT OBJECTS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS habitat_objects (
    id VARCHAR(64) PRIMARY KEY,
    habitat_id VARCHAR(64) NOT NULL REFERENCES habitats(id) ON DELETE CASCADE,
    object_type VARCHAR(50) NOT NULL,
    blender_name VARCHAR(100) NOT NULL,
    pose_xyz_m JSONB NOT NULL,
    interaction_radius_m DOUBLE PRECISION NOT NULL,
    affordances JSONB NOT NULL,
    resource_state JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_habitat_objects_habitat_id ON habitat_objects(habitat_id);

-- ==============================================================================
-- 16. COMMANDS TABLE (Idempotency Key Enforcement)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS commands (
    command_id VARCHAR(128) PRIMARY KEY, -- Mandatory Unique Idempotency Key
    pet_id VARCHAR(64) NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    command_type VARCHAR(50) NOT NULL,
    parameters JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'received' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    processed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_commands_pet_id ON commands(pet_id);
CREATE INDEX IF NOT EXISTS idx_commands_status ON commands(status);

-- ==============================================================================
-- 6. CARE ACTIONS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS care_actions (
    id VARCHAR(64) PRIMARY KEY,
    command_id VARCHAR(128) UNIQUE NOT NULL REFERENCES commands(command_id),
    pet_id VARCHAR(64) NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL,
    parameters JSONB NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_care_actions_pet_id ON care_actions(pet_id);

-- ==============================================================================
-- 7. WORLD EVENTS TABLE (Append-Only & Immutable)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS world_events (
    event_id VARCHAR(128) PRIMARY KEY,
    pet_id VARCHAR(64) NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    world_tick BIGINT NOT NULL,
    sim_time_sec DOUBLE PRECISION NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    skill_name VARCHAR(50),
    origin VARCHAR(50) NOT NULL, -- observed_physics | sampled_from_skill_model | rule
    behaviour_type VARCHAR(50) NOT NULL, -- learned | scripted | rule
    seed BIGINT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_world_events_pet_time ON world_events(pet_id, sim_time_sec);
CREATE INDEX IF NOT EXISTS idx_world_events_type ON world_events(event_type);

-- Trigger preventing updates on world_events (Acceptance Criterion 3)
CREATE OR REPLACE FUNCTION prevent_world_events_update_func()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'world_events is append-only and cannot be updated';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_world_events_update ON world_events;
CREATE TRIGGER trg_prevent_world_events_update
BEFORE UPDATE ON world_events
FOR EACH ROW
EXECUTE FUNCTION prevent_world_events_update_func();

-- ==============================================================================
-- 8. MEMORIES TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS memories (
    id VARCHAR(64) PRIMARY KEY,
    pet_id VARCHAR(64) NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    memory_type VARCHAR(50) NOT NULL,
    target_id VARCHAR(64),
    estimated_value DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    time_since_last_visit_sec DOUBLE PRECISION,
    last_known_pos JSONB,
    spatial_familiarity JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_pet_id ON memories(pet_id);

-- ==============================================================================
-- 9. BEHAVIOUR STATS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS behaviour_stats (
    id VARCHAR(64) PRIMARY KEY,
    pet_id VARCHAR(64) NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    skill_distribution JSONB NOT NULL,
    healthy_range_percentages JSONB NOT NULL,
    mean_drives JSONB NOT NULL,
    total_distance_m DOUBLE PRECISION DEFAULT 0.0 NOT NULL,
    wheel_revolutions BIGINT DEFAULT 0 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_behaviour_stats_pet_id ON behaviour_stats(pet_id);

-- ==============================================================================
-- 10. POLICY VERSIONS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS policy_versions (
    id VARCHAR(64) PRIMARY KEY,
    algorithm VARCHAR(50) NOT NULL,
    behaviour_type VARCHAR(50) NOT NULL,
    schema_version VARCHAR(20) NOT NULL,
    morphology_version VARCHAR(50) NOT NULL,
    environment_version VARCHAR(50) NOT NULL,
    checkpoint_uri VARCHAR(255) NOT NULL,
    metrics JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ==============================================================================
-- 11. SIMULATION RUNS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS simulation_runs (
    id VARCHAR(64) PRIMARY KEY,
    pet_id VARCHAR(64) NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    policy_version_id VARCHAR(64) REFERENCES policy_versions(id),
    run_mode VARCHAR(50) NOT NULL,
    start_sim_time_sec DOUBLE PRECISION NOT NULL,
    end_sim_time_sec DOUBLE PRECISION NOT NULL,
    wall_clock_duration_sec DOUBLE PRECISION NOT NULL,
    step_count BIGINT NOT NULL,
    steps_per_sec DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_pet_id ON simulation_runs(pet_id);

-- ==============================================================================
-- 12. TRAINING RUNS TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS training_runs (
    id VARCHAR(64) PRIMARY KEY,
    experiment_name VARCHAR(100) NOT NULL,
    seed BIGINT NOT NULL,
    algorithm VARCHAR(50) NOT NULL,
    total_steps BIGINT NOT NULL,
    final_mean_reward DOUBLE PRECISION NOT NULL,
    config JSONB NOT NULL,
    artifact_uri VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ==============================================================================
-- 13. NOTIFICATION PREFERENCES TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id VARCHAR(64) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    telegram_chat_id VARCHAR(64),
    daily_digest_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    daily_digest_time_utc VARCHAR(10) DEFAULT '08:00' NOT NULL,
    urgent_alerts_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    quiet_hours_start_utc VARCHAR(10) DEFAULT '22:00' NOT NULL,
    quiet_hours_end_utc VARCHAR(10) DEFAULT '07:00' NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ==============================================================================
-- 14. NOTIFICATION OUTBOX TABLE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS notification_outbox (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pet_id VARCHAR(64) NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    channel VARCHAR(50) DEFAULT 'telegram' NOT NULL,
    category VARCHAR(50) NOT NULL,
    message_payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    attempts INT DEFAULT 0 NOT NULL,
    last_error TEXT,
    scheduled_for TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notification_outbox_status ON notification_outbox(status);

-- ==============================================================================
-- 14b. TELEGRAM BINDING CODES TABLE (One-Time Pairing)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS telegram_binding_codes (
    code VARCHAR(32) PRIMARY KEY,
    chat_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_telegram_binding_codes_chat_id ON telegram_binding_codes(chat_id);

-- ==============================================================================
-- 15. WORKER LEASES TABLE (Exclusive Lock)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS worker_leases (
    pet_id VARCHAR(64) PRIMARY KEY REFERENCES pets(id) ON DELETE CASCADE,
    worker_id VARCHAR(128) NOT NULL,
    acquired_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    version BIGINT DEFAULT 1 NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_worker_leases_expires_at ON worker_leases(expires_at);

-- ==============================================================================
-- SUPABASE ROW-LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE pets ENABLE ROW LEVEL SECURITY;
ALTER TABLE pet_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE habitats ENABLE ROW LEVEL SECURITY;
ALTER TABLE habitat_objects ENABLE ROW LEVEL SECURITY;
ALTER TABLE care_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE world_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE commands ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_outbox ENABLE ROW LEVEL SECURITY;

-- Users policy
CREATE POLICY users_owner_policy ON users
    FOR ALL USING (auth.uid()::text = id);

-- Pets policy
CREATE POLICY pets_owner_policy ON pets
    FOR ALL USING (auth.uid()::text = user_id);

-- Pet state policy
CREATE POLICY pet_state_owner_policy ON pet_state
    FOR ALL USING (
        EXISTS (SELECT 1 FROM pets WHERE pets.id = pet_state.pet_id AND pets.user_id = auth.uid()::text)
    );

-- Habitats policy
CREATE POLICY habitats_owner_policy ON habitats
    FOR ALL USING (
        EXISTS (SELECT 1 FROM pets WHERE pets.id = habitats.pet_id AND pets.user_id = auth.uid()::text)
    );

-- World events policy (Read-only for owners)
CREATE POLICY world_events_owner_policy ON world_events
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM pets WHERE pets.id = world_events.pet_id AND pets.user_id = auth.uid()::text)
    );

-- Commands policy
CREATE POLICY commands_owner_policy ON commands
    FOR ALL USING (auth.uid()::text = user_id);

-- Service role bypasses RLS automatically in Supabase for background workers.

