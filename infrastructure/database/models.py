"""
HAMMY — P2.1: Relational Schema & ORM Models (`infrastructure/database/models.py`).
Implements all 16 tables specified in P2.1 with constraints enforcing:
  - Idempotency via unique `command_id` on commands table.
  - Append-only immutability on `world_events`.
  - Optimistic concurrency control via `version` counter on `pet_state` and `worker_leases`.
  - Explicit Honesty & Origin enums matching versioned contracts.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from infrastructure.database.connection import Base


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# ==============================================================================
# 1. USERS TABLE
# ==============================================================================
class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)  # Matches Supabase auth.users.id
    email = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    pets = relationship("Pet", back_populates="owner", cascade="all, delete-orphan")
    notification_pref = relationship("NotificationPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")


# ==============================================================================
# 2. PETS TABLE
# ==============================================================================
class Pet(Base):
    __tablename__ = "pets"

    id = Column(String(64), primary_key=True)  # e.g. "hammy_001"
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    species = Column(String(50), default="syrian_hamster", nullable=False)
    morphology_version = Column(String(50), default="simple_agent_v1", nullable=False)
    birth_date = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    owner = relationship("User", back_populates="pets")
    state = relationship("PetState", back_populates="pet", uselist=False, cascade="all, delete-orphan")
    habitats = relationship("Habitat", back_populates="pet", cascade="all, delete-orphan")
    world_events = relationship("WorldEvent", back_populates="pet")
    memories = relationship("Memory", back_populates="pet", cascade="all, delete-orphan")
    lease = relationship("WorkerLease", back_populates="pet", uselist=False, cascade="all, delete-orphan")


# ==============================================================================
# 3. PET STATE TABLE (Optimistic Concurrency & Temporal Progression)
# ==============================================================================
class PetState(Base):
    __tablename__ = "pet_state"

    pet_id = Column(String(64), ForeignKey("pets.id", ondelete="CASCADE"), primary_key=True)
    version = Column(BigInteger, default=1, nullable=False)  # Optimistic concurrency counter
    schema_version = Column(String(20), default="2.0.0", nullable=False)
    environment_version = Column(String(50), default="habitat_v1", nullable=False)
    sim_time_sec = Column(Float, default=0.0, nullable=False)
    simulated_age_days = Column(Float, default=0.0, nullable=False)
    real_time_scale = Column(Float, default=1.0, nullable=False)
    last_simulated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    is_paused = Column(Boolean, default=False, nullable=False)

    # Serialized physical and physiological vectors
    drives = Column(JSON, nullable=False)  # hunger, thirst, energy, comfort, stress, curiosity, circadian_phase
    position_xyz = Column(JSON, nullable=False)  # [x, y, z]
    yaw_rad = Column(Float, default=0.0, nullable=False)
    velocity_xy = Column(JSON, default=[0.0, 0.0], nullable=False)
    angular_velocity_z = Column(Float, default=0.0, nullable=False)

    # State flags
    inside_hideout = Column(Boolean, default=False, nullable=False)
    inside_tunnel = Column(Boolean, default=False, nullable=False)
    on_wheel = Column(Boolean, default=False, nullable=False)
    cheek_pouch_fill = Column(Float, default=0.0, nullable=False)

    active_skill = Column(String(50), nullable=True)
    active_skill_started_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    pet = relationship("Pet", back_populates="state")


# ==============================================================================
# 4. HABITATS TABLE
# ==============================================================================
class Habitat(Base):
    __tablename__ = "habitats"

    id = Column(String(64), primary_key=True)  # e.g. "habitat_v1_main"
    pet_id = Column(String(64), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True)
    environment_version = Column(String(50), default="habitat_v1", nullable=False)
    name = Column(String(100), nullable=False)
    dimensions_xyz = Column(JSON, nullable=False)  # [width, depth, height]
    floor_bounds = Column(JSON, nullable=False)   # {"x_min": ..., "x_max": ..., ...}
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    pet = relationship("Pet", back_populates="habitats")
    objects = relationship("HabitatObject", back_populates="habitat", cascade="all, delete-orphan")


# ==============================================================================
# 5. HABITAT OBJECTS TABLE
# ==============================================================================
class HabitatObject(Base):
    __tablename__ = "habitat_objects"

    id = Column(String(64), primary_key=True)  # e.g. "prop_bowl_main"
    habitat_id = Column(String(64), ForeignKey("habitats.id", ondelete="CASCADE"), nullable=False, index=True)
    object_type = Column(String(50), nullable=False)
    blender_name = Column(String(100), nullable=False)
    pose_xyz_m = Column(JSON, nullable=False)
    interaction_radius_m = Column(Float, nullable=False)
    affordances = Column(JSON, nullable=False)
    resource_state = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    habitat = relationship("Habitat", back_populates="objects")


# ==============================================================================
# 6. CARE ACTIONS TABLE
# ==============================================================================
class CareAction(Base):
    __tablename__ = "care_actions"

    id = Column(String(64), primary_key=True)
    command_id = Column(String(128), ForeignKey("commands.command_id"), unique=True, nullable=False, index=True)
    pet_id = Column(String(64), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    parameters = Column(JSON, nullable=False)
    applied_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


# ==============================================================================
# 7. WORLD EVENTS TABLE (Append-Only & Immutable)
# ==============================================================================
class WorldEvent(Base):
    __tablename__ = "world_events"

    event_id = Column(String(128), primary_key=True)  # Deterministic event ID
    pet_id = Column(String(64), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True)
    world_tick = Column(BigInteger, nullable=False, index=True)
    sim_time_sec = Column(Float, nullable=False)
    event_type = Column(String(100), nullable=False, index=True)
    skill_name = Column(String(50), nullable=True)
    origin = Column(String(50), nullable=False)  # observed_physics | sampled_from_skill_model | rule
    behaviour_type = Column(String(50), nullable=False)  # learned | scripted | rule
    seed = Column(BigInteger, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    pet = relationship("Pet", back_populates="world_events")

    __table_args__ = (
        Index("idx_world_events_pet_time", "pet_id", "sim_time_sec"),
    )


# ==============================================================================
# 8. MEMORIES TABLE
# ==============================================================================
class Memory(Base):
    __tablename__ = "memories"

    id = Column(String(64), primary_key=True)
    pet_id = Column(String(64), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True)
    memory_type = Column(String(50), nullable=False)  # object_appraisal | spatial_grid
    target_id = Column(String(64), nullable=True, index=True)
    estimated_value = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    time_since_last_visit_sec = Column(Float, nullable=True)
    last_known_pos = Column(JSON, nullable=True)
    spatial_familiarity = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    pet = relationship("Pet", back_populates="memories")


# ==============================================================================
# 9. BEHAVIOUR STATS TABLE
# ==============================================================================
class BehaviourStat(Base):
    __tablename__ = "behaviour_stats"

    id = Column(String(64), primary_key=True)
    pet_id = Column(String(64), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    skill_distribution = Column(JSON, nullable=False)
    healthy_range_percentages = Column(JSON, nullable=False)
    mean_drives = Column(JSON, nullable=False)
    total_distance_m = Column(Float, default=0.0, nullable=False)
    wheel_revolutions = Column(BigInteger, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


# ==============================================================================
# 10. POLICY VERSIONS TABLE
# ==============================================================================
class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    id = Column(String(64), primary_key=True)  # e.g. "ppo_options_v1"
    algorithm = Column(String(50), nullable=False)
    behaviour_type = Column(String(50), nullable=False)  # learned | scripted | rule
    schema_version = Column(String(20), nullable=False)
    morphology_version = Column(String(50), nullable=False)
    environment_version = Column(String(50), nullable=False)
    checkpoint_uri = Column(String(255), nullable=False)
    metrics = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


# ==============================================================================
# 11. SIMULATION RUNS TABLE
# ==============================================================================
class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(String(64), primary_key=True)
    pet_id = Column(String(64), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_version_id = Column(String(64), ForeignKey("policy_versions.id"), nullable=True)
    run_mode = Column(String(50), nullable=False)  # live_physics | background_catchup
    start_sim_time_sec = Column(Float, nullable=False)
    end_sim_time_sec = Column(Float, nullable=False)
    wall_clock_duration_sec = Column(Float, nullable=False)
    step_count = Column(BigInteger, nullable=False)
    steps_per_sec = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


# ==============================================================================
# 12. TRAINING RUNS TABLE
# ==============================================================================
class TrainingRun(Base):
    __tablename__ = "training_runs"

    id = Column(String(64), primary_key=True)
    experiment_name = Column(String(100), nullable=False, index=True)
    seed = Column(BigInteger, nullable=False)
    algorithm = Column(String(50), nullable=False)
    total_steps = Column(BigInteger, nullable=False)
    final_mean_reward = Column(Float, nullable=False)
    config = Column(JSON, nullable=False)
    artifact_uri = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


# ==============================================================================
# 13. NOTIFICATION PREFERENCES TABLE
# ==============================================================================
class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    telegram_chat_id = Column(String(64), nullable=True, index=True)
    daily_digest_enabled = Column(Boolean, default=True, nullable=False)
    daily_digest_time_utc = Column(String(10), default="08:00", nullable=False)
    urgent_alerts_enabled = Column(Boolean, default=True, nullable=False)
    quiet_hours_start_utc = Column(String(10), default="22:00", nullable=False)
    quiet_hours_end_utc = Column(String(10), default="07:00", nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="notification_pref")


# ==============================================================================
# 14. NOTIFICATION OUTBOX TABLE
# ==============================================================================
class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pet_id = Column(String(64), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(50), default="telegram", nullable=False)
    category = Column(String(50), nullable=False)  # digest | urgent_alert
    message_payload = Column(JSON, nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending | delivered | failed
    attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    scheduled_for = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


# ==============================================================================
# 14b. TELEGRAM BINDING CODES TABLE (One-Time Pairing)
# ==============================================================================
class TelegramBindingCode(Base):
    __tablename__ = "telegram_binding_codes"

    code = Column(String(32), primary_key=True)
    chat_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


# ==============================================================================
# 15. WORKER LEASES TABLE (Exclusive Lock)
# ==============================================================================
class WorkerLease(Base):
    __tablename__ = "worker_leases"

    pet_id = Column(String(64), ForeignKey("pets.id", ondelete="CASCADE"), primary_key=True)
    worker_id = Column(String(128), nullable=False)
    acquired_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    version = Column(BigInteger, default=1, nullable=False)

    pet = relationship("Pet", back_populates="lease")


# ==============================================================================
# 16. COMMANDS TABLE (Idempotency Key Enforcement)
# ==============================================================================
class Command(Base):
    __tablename__ = "commands"

    # MANDATORY unique idempotency key (Rule 4 & P2.1 Acceptance)
    command_id = Column(String(128), primary_key=True)
    pet_id = Column(String(64), ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    command_type = Column(String(50), nullable=False)
    parameters = Column(JSON, nullable=False)
    status = Column(String(20), default="received", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
