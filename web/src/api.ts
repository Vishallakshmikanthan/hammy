/**
 * HAMMY — Observatory REST Client (`web/src/api.ts`).
 * Rule: Data from API only; no client-side simulation.
 */

import { Pet, PetState, WorldEvent } from "./types";

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

