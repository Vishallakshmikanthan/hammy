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

export type AssetCategory = "food" | "water" | "costume" | "prop" | "decor";

export type CostumeSlot = "head_slot" | "neck_slot" | "back_slot";

export interface ManifestAssetItem {
  id: string;
  name: string;
  category: AssetCategory;
  file_path: string;
  web_url: string;
  source_blend: string;
  thumbnail: string;
  thumbnail_url: string;
  scale: [number, number, number];
  dimensions_m: [number, number, number];
  collision_radius_m: number;
  pivot: string;
  attachment_slot: CostumeSlot | "paw_hold" | null;
  hamster_safe: boolean | null;
  safety_note?: string | null;
  licence: string;
  author: string;
  source: string;
  origin_label: "GENERATED" | "DOWNLOADED";
  vertices: number;
  polygon_count: number;
  triangle_count: number;
  file_size_bytes: number;
}

export interface AssetManifest {
  schema_version: string;
  default_cage_policy: string;
  default_cage_items: string[];
  default_cage_assumption_note: string;
  cage_bounds_m: {
    min_x: number;
    max_x: number;
    min_y: number;
    max_y: number;
    floor_z: number;
  };
  total_assets: number;
  items: ManifestAssetItem[];
}

export interface EquippedCostumeEntry {
  object_id: string;
  item_id: string;
  name: string;
  slot: CostumeSlot;
}

export interface OfferedFoodEntry {
  object_id: string;
  item_id: string;
  name: string;
  quantity: number;
  pose_xyz_m: [number, number, number];
  spoils_at_sim_sec: number;
  spoiled: boolean;
}

export interface WaterSourceEntry {
  object_id: string;
  item_id: string;
  name: string;
  pose_xyz_m: [number, number, number];
  water_level: number;
  capacity_ml: number;
}

export interface PlacedItemEntry {
  object_id: string;
  item_id: string;
  name: string;
  category: "prop" | "decor" | "water";
  pose_xyz_m: [number, number, number];
  rotation_y_rad: number;
  collision_radius_m: number;
}

export interface ShelvesLayoutState {
  pet_id: string;
  sim_time_sec: number;
  cheek_pouch_fill: number;
  water_level: number;
  equipped_costumes: Partial<Record<CostumeSlot, EquippedCostumeEntry>>;
  offered_foods: OfferedFoodEntry[];
  water_sources: WaterSourceEntry[];
  placed_items: PlacedItemEntry[];
}

export interface PlacementDraft {
  item: ManifestAssetItem;
  pose_xyz_m: [number, number, number];
  rotation_y_rad: number;
  editingObjectId?: string;
}


