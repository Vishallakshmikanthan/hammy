/**
 * HAMMY — Brain Observatory TypeScript Contracts (`web/src/types.ts`).
 * Matches versioned Pydantic & database contracts (Rule 5).
 */

export type EventOrigin = "observed_physics" | "sampled_from_skill_model" | "rule";

export type BehaviourType = "learned" | "scripted" | "rule";

export interface DriveVector {
  hunger: number;
  thirst: number;
  energy: number;
  comfort: number;
  stress: number;
  curiosity: number;
  circadian_phase: number;
}

export interface Pet {
  id: string;
  user_id: string;
  name: string;
  species: string;
  morphology_version: string;
  birth_date: string | null;
  created_at: string | null;
}

export interface PetState {
  pet_id: string;
  version: number;
  schema_version: string;
  environment_version: string;
  sim_time_sec: number;
  simulated_age_days: number;
  real_time_scale: number;
  last_simulated_at: string | null;
  is_paused: boolean;
  drives: DriveVector;
  position_xyz: [number, number, number];
  yaw_rad: number;
  velocity_xy: [number, number];
  angular_velocity_z: number;
  inside_hideout: boolean;
  inside_tunnel: boolean;
  on_wheel: boolean;
  cheek_pouch_fill: number;
  active_skill: string | null;
  updated_at: string | null;
}

export interface WorldEvent {
  event_id: string;
  pet_id: string;
  world_tick: number;
  sim_time_sec: number;
  event_type: string;
  skill_name: string | null;
  origin: EventOrigin;
  behaviour_type: BehaviourType;
  seed: number;
  payload: Record<string, any>;
  created_at: string | null;
}

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";

