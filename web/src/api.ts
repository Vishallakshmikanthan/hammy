/**
 * HAMMY — Observatory REST Client (`web/src/api.ts`).
 * Rule: Data from API only; no client-side simulation.
 */

import {
  AssetManifest,
  CostumeSlot,
  Pet,
  PetState,
  ShelvesLayoutState,
  WorldEvent,
} from "./types";

const API_BASE = "/api/v1";

function getHeaders(token?: string): HeadersInit {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export async function fetchPet(petId: string, token?: string): Promise<Pet> {
  const res = await fetch(`${API_BASE}/pets/${petId}`, { headers: getHeaders(token) });
  if (!res.ok) throw new Error(`Failed to fetch pet: ${res.statusText}`);
  return res.json();
}

export async function fetchPetState(petId: string, token?: string): Promise<PetState> {
  const res = await fetch(`${API_BASE}/pets/${petId}/state`, { headers: getHeaders(token) });
  if (!res.ok) throw new Error(`Failed to fetch pet state: ${res.statusText}`);
  return res.json();
}

export async function fetchPetEvents(
  petId: string,
  limit: number = 50,
  token?: string
): Promise<WorldEvent[]> {
  const res = await fetch(`${API_BASE}/pets/${petId}/events?limit=${limit}`, {
    headers: getHeaders(token),
  });
  if (!res.ok) throw new Error(`Failed to fetch pet events: ${res.statusText}`);
  return res.json();
}

export async function pauseSimulation(petId: string, token?: string): Promise<void> {
  const commandId = `cmd_web_pause_${Date.now()}`;
  const res = await fetch(`${API_BASE}/pets/${petId}/simulation/pause`, {
    method: "POST",
    headers: getHeaders(token),
    body: JSON.stringify({ command_id: commandId }),
  });
  if (!res.ok) throw new Error(`Failed to pause simulation: ${res.statusText}`);
}

export async function resumeSimulation(petId: string, token?: string): Promise<void> {
  const commandId = `cmd_web_resume_${Date.now()}`;
  const res = await fetch(`${API_BASE}/pets/${petId}/simulation/resume`, {
    method: "POST",
    headers: getHeaders(token),
    body: JSON.stringify({ command_id: commandId }),
  });
  if (!res.ok) throw new Error(`Failed to resume simulation: ${res.statusText}`);
}

export async function fetchAssetManifest(): Promise<AssetManifest> {
  try {
    const res = await fetch(`${API_BASE}/assets/manifest`);
    if (res.ok) return res.json();
  } catch {
    // Fallback to static public manifest
  }
  const res = await fetch("/assets/manifest.json");
  if (!res.ok) throw new Error(`Failed to load assets manifest: ${res.statusText}`);
  return res.json();
}

export async function fetchShelvesState(petId: string, token?: string): Promise<ShelvesLayoutState> {
  const res = await fetch(`${API_BASE}/pets/${petId}/shelves/state`, {
    headers: getHeaders(token),
  });
  if (!res.ok) throw new Error(`Failed to fetch shelves layout: ${res.statusText}`);
  return res.json();
}

async function postShelfCommand(
  petId: string,
  endpoint: string,
  payload: Record<string, unknown>,
  token?: string
): Promise<{ status: string; message: string; layout: ShelvesLayoutState }> {
  const res = await fetch(`${API_BASE}/pets/${petId}/shelves/${endpoint}`, {
    method: "POST",
    headers: getHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const errJson = await res.json();
      detail = errJson.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function offerFoodCommand(
  petId: string,
  itemId: string,
  quantity: number = 1,
  commandId: string = `cmd_offer_${itemId}_${Date.now()}`,
  token?: string
) {
  return postShelfCommand(petId, "offer_food", { command_id: commandId, item_id: itemId, quantity }, token);
}

export async function refillFoodCommand(
  petId: string,
  amountGrams: number = 25,
  commandId: string = `cmd_refill_food_${Date.now()}`,
  token?: string
) {
  return postShelfCommand(petId, "refill_food", { command_id: commandId, amount_grams: amountGrams }, token);
}

export async function refillWaterCommand(
  petId: string,
  amountMl: number = 150,
  commandId: string = `cmd_refill_water_${Date.now()}`,
  token?: string
) {
  return postShelfCommand(petId, "refill_water", { command_id: commandId, amount_ml: amountMl }, token);
}

export async function equipCostumeCommand(
  petId: string,
  itemId: string,
  commandId: string = `cmd_equip_${itemId}_${Date.now()}`,
  token?: string
) {
  return postShelfCommand(petId, "equip_costume", { command_id: commandId, item_id: itemId }, token);
}

export async function unequipCostumeCommand(
  petId: string,
  slot: CostumeSlot | "all" = "all",
  commandId: string = `cmd_unequip_${slot}_${Date.now()}`,
  token?: string
) {
  return postShelfCommand(petId, "unequip_costume", { command_id: commandId, slot }, token);
}

export async function placePropCommand(
  petId: string,
  itemId: string,
  poseXyzM: [number, number, number],
  rotationYRad: number = 0,
  commandId: string = `cmd_place_${itemId}_${Date.now()}`,
  token?: string
) {
  return postShelfCommand(
    petId,
    "place_prop",
    {
      command_id: commandId,
      item_id: itemId,
      pose_xyz_m: poseXyzM,
      rotation_y_rad: rotationYRad,
    },
    token
  );
}

export async function movePropCommand(
  petId: string,
  objectId: string,
  poseXyzM: [number, number, number],
  rotationYRad?: number,
  commandId: string = `cmd_move_${objectId}_${Date.now()}`,
  token?: string
) {
  return postShelfCommand(
    petId,
    "move_prop",
    {
      command_id: commandId,
      object_id: objectId,
      pose_xyz_m: poseXyzM,
      rotation_y_rad: rotationYRad,
    },
    token
  );
}

export async function removePropCommand(
  petId: string,
  objectId: string,
  commandId: string = `cmd_remove_${objectId}_${Date.now()}`,
  token?: string
) {
  return postShelfCommand(petId, "remove_prop", { command_id: commandId, object_id: objectId }, token);
}

export async function consumeFoodCommand(
  petId: string,
  objectId?: string,
  commandId: string = `cmd_eat_${objectId || "food"}_${Date.now()}`,
  token?: string
) {
  return postShelfCommand(petId, "consume_food", { command_id: commandId, object_id: objectId }, token);
}

export async function consumeWaterCommand(
  petId: string,
  commandId: string = `cmd_drink_${Date.now()}`,
  token?: string
) {
  return postShelfCommand(petId, "consume_water", { command_id: commandId }, token);
}

export async function resetCleanCageCommand(
  petId: string,
  commandId: string = `cmd_reset_clean_${Date.now()}`,
  token?: string
) {
  return postShelfCommand(petId, "reset_clean_cage", { command_id: commandId }, token);
}


