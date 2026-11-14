"""
HAMMY — Database Seed Script (`infrastructure/database/seeds.py`).
Seeds 1 user, 1 pet, 1 habitat with standard objects, initial pet_state, and notification preferences.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict

from sqlalchemy.orm import Session

from infrastructure.database.connection import engine, get_db_session
from infrastructure.database.models import (
    Habitat,
    HabitatObject,
    NotificationPreference,
    Pet,
    PetState,
    User,
)

HABITAT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "simulation" / "habitats" / "v1.json"


def load_habitat_v1_data() -> Dict[str, Any]:
    if HABITAT_CONFIG_PATH.exists():
        with open(HABITAT_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback default habitat layout
    return {
        "habitat_id": "habitat_v1",
        "environment_version": "habitat_v1",
        "dimensions_m": {
            "length_x": 1.0,
            "width_y": 0.5,
            "wall_height_z": 0.4,
            "bedding_surface_z": 0.165,
        },
        "objects": [
            {
                "object_id": "prop_bowl_main",
                "object_type": "food_bowl",
                "blender_name": "prop_bowl",
                "pose_xyz_m": [0.28, -0.11, 0.165],
                "interaction_radius_m": 0.065,
                "affordances": ["eat", "hoard"],
                "resource_state": {"food_level": 1.0, "capacity_grams": 25.0},
            },
            {
                "object_id": "prop_bottle_main",
                "object_type": "water_bottle",
                "blender_name": "prop_bottle_spout",
                "pose_xyz_m": [0.433, -0.02, 0.183],
                "interaction_radius_m": 0.055,
                "affordances": ["drink"],
                "resource_state": {"water_level": 1.0, "capacity_ml": 150.0},
            },
            {
                "object_id": "prop_hideout_main",
                "object_type": "hideout",
                "blender_name": "prop_hideout",
                "pose_xyz_m": [0.28, 0.11, 0.165],
                "interaction_radius_m": 0.095,
                "affordances": ["rest", "hide", "sleep", "nest"],
                "resource_state": {"hoard_food_level": 0.25, "bedding_comfort": 0.92},
            },
            {
                "object_id": "prop_tunnel_main",
                "object_type": "tunnel",
                "blender_name": "prop_tunnel_curve",
                "pose_xyz_m": [-0.04, -0.05, 0.165],
                "interaction_radius_m": 0.085,
                "affordances": ["enter_tunnel", "hide", "explore"],
                "resource_state": {"resource_level": 1.0},
            },
            {
                "object_id": "prop_wheel_main",
                "object_type": "wheel",
                "blender_name": "prop_wheel_drum",
                "pose_xyz_m": [-0.30, 0.13, 0.165],
                "interaction_radius_m": 0.145,
                "affordances": ["run_wheel", "explore"],
                "resource_state": {"resource_level": 1.0, "diameter_m": 0.28},
            },
            {
                "object_id": "prop_chew_block_main",
                "object_type": "chew_toy",
                "blender_name": "prop_chew_block",
                "pose_xyz_m": [0.17, -0.05, 0.165],
                "interaction_radius_m": 0.045,
                "affordances": ["gnaw", "explore"],
                "resource_state": {"durability_level": 0.95},
            },
        ],
    }


def seed_database(session: Session) -> Dict[str, Any]:
    """
    Populates database with initial seed records:
      - 1 User ('usr_hammy_default')
      - 1 Pet ('pet_hammy_01')
      - 1 PetState (initial drives, pose, and status)
      - 1 Habitat ('habitat_v1_main')
      - 6 HabitatObjects (bowl, bottle, hideout, tunnel, wheel, chew toy)
      - 1 NotificationPreference
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. User
    user = session.get(User, "usr_hammy_default")
    if not user:
        user = User(
            id="usr_hammy_default",
            email="owner@hammy.local",
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.flush()

    # 2. Notification Preferences
    notif_pref = session.get(NotificationPreference, user.id)
    if not notif_pref:
        notif_pref = NotificationPreference(
            user_id=user.id,
            telegram_chat_id="123456789",
            daily_digest_enabled=True,
            daily_digest_time_utc="08:00",
            urgent_alerts_enabled=True,
            quiet_hours_start_utc="22:00",
            quiet_hours_end_utc="07:00",
            updated_at=now,
        )
        session.add(notif_pref)

    # 3. Pet
    pet = session.get(Pet, "pet_hammy_01")
    if not pet:
        birth_date = now - datetime.timedelta(days=30)
        pet = Pet(
            id="pet_hammy_01",
            user_id=user.id,
            name="Hammy",
            species="syrian_hamster",
            morphology_version="simple_agent_v1",
            birth_date=birth_date,
            created_at=now,
        )
        session.add(pet)
        session.flush()

    # 4. PetState
    pet_state = session.get(PetState, pet.id)
    if not pet_state:
        pet_state = PetState(
            pet_id=pet.id,
            version=1,
            schema_version="2.0.0",
            environment_version="habitat_v1",
            sim_time_sec=0.0,
            simulated_age_days=30.0,
            real_time_scale=1.0,
            last_simulated_at=now,
            is_paused=False,
            drives={
                "hunger": 0.15,
                "thirst": 0.20,
                "energy": 0.85,
                "comfort": 0.90,
                "stress": 0.10,
                "curiosity": 0.70,
                "circadian_phase": 0.25,
            },
            position_xyz=[0.0, 0.0, 0.165],
            yaw_rad=0.0,
            velocity_xy=[0.0, 0.0],
            angular_velocity_z=0.0,
            inside_hideout=False,
            inside_tunnel=False,
            on_wheel=False,
            cheek_pouch_fill=0.0,
            active_skill=None,
            active_skill_started_at=None,
            updated_at=now,
        )
        session.add(pet_state)

    # 5. Habitat
    habitat = session.get(Habitat, "habitat_v1_main")
    habitat_raw = load_habitat_v1_data()
    dims = habitat_raw.get("dimensions_m", {})
    length_x = dims.get("length_x", 1.0)
    width_y = dims.get("width_y", 0.5)

    if not habitat:
        habitat = Habitat(
            id="habitat_v1_main",
            pet_id=pet.id,
            environment_version="habitat_v1",
            name="Hammy's Habitat",
            dimensions_xyz=dims,
            floor_bounds={
                "x_min": -length_x / 2.0,
                "x_max": length_x / 2.0,
                "y_min": -width_y / 2.0,
                "y_max": width_y / 2.0,
            },
            created_at=now,
        )
        session.add(habitat)
        session.flush()

    # 6. Habitat Objects
    seeded_objects = []
    for obj in habitat_raw.get("objects", []):
        obj_id = obj["object_id"]
        hab_obj = session.get(HabitatObject, obj_id)
        if not hab_obj:
            hab_obj = HabitatObject(
                id=obj_id,
                habitat_id=habitat.id,
                object_type=obj["object_type"],
                blender_name=obj["blender_name"],
                pose_xyz_m=obj["pose_xyz_m"],
                interaction_radius_m=float(obj["interaction_radius_m"]),
                affordances=obj["affordances"],
                resource_state=obj["resource_state"],
                updated_at=now,
            )
            session.add(hab_obj)
        seeded_objects.append(obj_id)

    session.commit()

    return {
        "user_id": user.id,
        "pet_id": pet.id,
        "habitat_id": habitat.id,
        "object_ids": seeded_objects,
    }


if __name__ == "__main__":
    with get_db_session() as session:
        result = seed_database(session)
        print(f"Database seeded successfully: {result}")

