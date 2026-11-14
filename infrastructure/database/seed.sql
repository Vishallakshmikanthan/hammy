-- ==============================================================================
-- HAMMY — Database Seed SQL (`infrastructure/database/seed.sql`).
-- Seeds initial default user, pet, state, habitat, and standard props.
-- ==============================================================================

-- 1. Default User
INSERT INTO users (id, email, created_at, updated_at)
VALUES ('usr_hammy_default', 'owner@hammy.local', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- 2. Notification Preferences
INSERT INTO notification_preferences (
    user_id, telegram_chat_id, daily_digest_enabled, daily_digest_time_utc,
    urgent_alerts_enabled, quiet_hours_start_utc, quiet_hours_end_utc, updated_at
)
VALUES (
    'usr_hammy_default', '123456789', TRUE, '08:00',
    TRUE, '22:00', '07:00', NOW()
)
ON CONFLICT (user_id) DO NOTHING;

-- 3. Default Pet
INSERT INTO pets (
    id, user_id, name, species, morphology_version, birth_date, created_at
)
VALUES (
    'pet_hammy_01', 'usr_hammy_default', 'Hammy', 'syrian_hamster',
    'simple_agent_v1', NOW() - INTERVAL '30 days', NOW()
)
ON CONFLICT (id) DO NOTHING;

-- 4. Default Pet State
INSERT INTO pet_state (
    pet_id, version, schema_version, environment_version,
    sim_time_sec, simulated_age_days, real_time_scale, last_simulated_at, is_paused,
    drives, position_xyz, yaw_rad, velocity_xy, angular_velocity_z,
    inside_hideout, inside_tunnel, on_wheel, cheek_pouch_fill,
    active_skill, active_skill_started_at, updated_at
)
VALUES (
    'pet_hammy_01', 1, '2.0.0', 'habitat_v1',
    0.0, 30.0, 1.0, NOW(), FALSE,
    '{"hunger": 0.15, "thirst": 0.20, "energy": 0.85, "comfort": 0.90, "stress": 0.10, "curiosity": 0.70, "circadian_phase": 0.25}'::jsonb,
    '[0.0, 0.0, 0.165]'::jsonb,
    0.0, '[0.0, 0.0]'::jsonb, 0.0,
    FALSE, FALSE, FALSE, 0.0,
    NULL, NULL, NOW()
)
ON CONFLICT (pet_id) DO NOTHING;

-- 5. Default Habitat
INSERT INTO habitats (
    id, pet_id, environment_version, name, dimensions_xyz, floor_bounds, created_at
)
VALUES (
    'habitat_v1_main', 'pet_hammy_01', 'habitat_v1', 'Hammy''s Habitat',
    '{"length_x": 1.0, "width_y": 0.5, "wall_height_z": 0.4, "bedding_surface_z": 0.165}'::jsonb,
    '{"x_min": -0.5, "x_max": 0.5, "y_min": -0.25, "y_max": 0.25}'::jsonb,
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- 6. Habitat Objects
INSERT INTO habitat_objects (
    id, habitat_id, object_type, blender_name, pose_xyz_m,
    interaction_radius_m, affordances, resource_state, updated_at
)
VALUES
(
    'prop_bowl_main', 'habitat_v1_main', 'food_bowl', 'prop_bowl',
    '[0.28, -0.11, 0.165]'::jsonb, 0.065,
    '["eat", "hoard"]'::jsonb,
    '{"food_level": 1.0, "capacity_grams": 25.0}'::jsonb,
    NOW()
),
(
    'prop_bottle_main', 'habitat_v1_main', 'water_bottle', 'prop_bottle_spout',
    '[0.433, -0.02, 0.183]'::jsonb, 0.055,
    '["drink"]'::jsonb,
    '{"water_level": 1.0, "capacity_ml": 150.0}'::jsonb,
    NOW()
),
(
    'prop_hideout_main', 'habitat_v1_main', 'hideout', 'prop_hideout',
    '[0.28, 0.11, 0.165]'::jsonb, 0.095,
    '["rest", "hide", "sleep", "nest"]'::jsonb,
    '{"hoard_food_level": 0.25, "bedding_comfort": 0.92}'::jsonb,
    NOW()
),
(
    'prop_tunnel_main', 'habitat_v1_main', 'tunnel', 'prop_tunnel_curve',
    '[-0.04, -0.05, 0.165]'::jsonb, 0.085,
    '["enter_tunnel", "hide", "explore"]'::jsonb,
    '{"resource_level": 1.0}'::jsonb,
    NOW()
),
(
    'prop_wheel_main', 'habitat_v1_main', 'wheel', 'prop_wheel_drum',
    '[-0.30, 0.13, 0.165]'::jsonb, 0.145,
    '["run_wheel", "explore"]'::jsonb,
    '{"resource_level": 1.0, "diameter_m": 0.28}'::jsonb,
    NOW()
),
(
    'prop_chew_block_main', 'habitat_v1_main', 'chew_toy', 'prop_chew_block',
    '[0.17, -0.05, 0.165]'::jsonb, 0.045,
    '["gnaw", "explore"]'::jsonb,
    '{"durability_level": 0.95}'::jsonb,
    NOW()
)
ON CONFLICT (id) DO NOTHING;

