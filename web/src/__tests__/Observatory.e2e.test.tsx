import React from "react";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { Observatory } from "../components/Observatory";

// Mock WebSocket class
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  readyState: number = 0; // CONNECTING

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      this.readyState = 1; // OPEN
      if (this.onopen) this.onopen();
    }, 10);
  }

  send(data: string) {}

  close() {
    this.readyState = 3; // CLOSED
    if (this.onclose) this.onclose();
  }

  // Helper for test to dispatch incoming server message
  receiveMessage(data: any) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) });
    }
  }
}

describe("Observatory End-to-End & WebSocket Reconnection", () => {
  const initialPet = {
    id: "pet_hammy_01",
    user_id: "usr_hammy_default",
    name: "Hammy",
    species: "Syrian Hamster",
    morphology_version: "simple_agent_v1",
    birth_date: "2026-10-01T00:00:00Z",
    created_at: "2026-10-01T00:00:00Z",
  };

  const initialState = {
    pet_id: "pet_hammy_01",
    version: 10,
    schema_version: "2.0.0",
    environment_version: "cage_v1",
    sim_time_sec: 100.0,
    simulated_age_days: 5.0,
    real_time_scale: 1.0,
    last_simulated_at: "2026-11-14T09:00:00Z",
    is_paused: false,
    drives: {
      hunger: 0.2,
      thirst: 0.3,
      energy: 0.9,
      comfort: 0.8,
      stress: 0.1,
      curiosity: 0.5,
      circadian_phase: 0.0,
    },
    position_xyz: [0, 0, 0],
    yaw_rad: 0,
    velocity_xy: [0, 0],
    angular_velocity_z: 0,
    inside_hideout: false,
    inside_tunnel: false,
    on_wheel: false,
    cheek_pouch_fill: 0.0,
    active_skill: "explore",
    updated_at: "2026-11-14T09:00:00Z",
  };

  const initialEvents = [
    {
      event_id: "evt_init_1",
      pet_id: "pet_hammy_01",
      world_tick: 10,
      sim_time_sec: 100.0,
      event_type: "world_tick",
      skill_name: null,
      origin: "rule",
      behaviour_type: "rule",
      seed: 1,
      payload: {},
      created_at: "2026-11-14T09:00:00Z",
    },
  ];

  beforeEach(() => {
    MockWebSocket.instances = [];
    (global as any).WebSocket = MockWebSocket;

    global.fetch = vi.fn().mockImplementation((url: string, options?: any) => {
      if (url.includes("/api/v1/pets/pet_hammy_01/state")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(initialState),
        });
      }
      if (url.includes("/api/v1/pets/pet_hammy_01/events")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(initialEvents),
        });
      }
      if (url.includes("/api/v1/pets/pet_hammy_01/simulation/pause")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ok: true, status: "paused" }),
        });
      }
      if (url.includes("/api/v1/pets/pet_hammy_01/simulation/resume")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ok: true, status: "resumed" }),
        });
      }
      if (url.includes("/api/v1/pets/pet_hammy_01")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(initialPet),
        });
      }
      return Promise.reject(new Error(`Unhandled URL in mock fetch: ${url}`));
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("hydrates from REST API, connects WebSocket, updates state on snapshot, and restores state on reconnect", async () => {
    render(<Observatory petId="pet_hammy_01" />);

    // 1. Initial REST Hydration
    await waitFor(() => {
      expect(screen.getByTestId("observatory-root")).toBeInTheDocument();
      expect(screen.getByTestId("status-indicator")).toHaveTextContent("RUNNING");
      expect(screen.getByTestId("drive-hunger-val")).toHaveTextContent("20.0%");
    });

    // 2. WebSocket Connected
    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBeGreaterThan(0);
      expect(screen.getByTestId("connection-status")).toHaveTextContent("CONNECTED");
    });

    const activeWs = MockWebSocket.instances[0];

    // 3. Server pushes a real-time snapshot over WebSocket
    act(() => {
      activeWs.receiveMessage({
        type: "snapshot",
        version: 11,
        sim_time_sec: 110.0,
        is_paused: false,
        drives: {
          hunger: 0.45, // Hunger increased on authoritative server
          thirst: 0.35,
          energy: 0.85,
          comfort: 0.8,
          stress: 0.1,
          curiosity: 0.5,
          circadian_phase: 0.2,
        },
        position_xyz: [0.5, 0.2, 0.0],
      });
    });

    // Verify UI reflects new server snapshot
    await waitFor(() => {
      expect(screen.getByTestId("drive-hunger-val")).toHaveTextContent("45.0%");
      expect(screen.getByTestId("state-version")).toHaveTextContent("#11");
    });

    // 4. WebSocket Disconnection & State Restoration
    // Simulate connection drop
    act(() => {
      activeWs.close();
    });

    await waitFor(() => {
      expect(screen.getByTestId("connection-status")).toHaveTextContent("RECONNECTING");
    });

    // Reconnection initiates a new WebSocket instance
    expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(1);

    // Let the new WebSocket reconnect and send authoritative snapshot
    const reconnectedWs = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    act(() => {
      if (reconnectedWs.onopen) reconnectedWs.onopen();
    });

    await waitFor(() => {
      expect(screen.getByTestId("connection-status")).toHaveTextContent("CONNECTED");
    });

    // Restores latest state snapshot from server upon reconnect
    act(() => {
      reconnectedWs.receiveMessage({
        type: "snapshot",
        version: 15,
        sim_time_sec: 150.0,
        is_paused: false,
        drives: {
          hunger: 0.62,
          thirst: 0.5,
          energy: 0.7,
          comfort: 0.8,
          stress: 0.2,
          curiosity: 0.4,
          circadian_phase: 0.5,
        },
        position_xyz: [1.2, -0.4, 0.0],
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId("drive-hunger-val")).toHaveTextContent("62.0%");
      expect(screen.getByTestId("state-version")).toHaveTextContent("#15");
    });

    // 5. User Pauses Simulation
    const pauseBtn = screen.getByTestId("pause-btn");
    fireEvent.click(pauseBtn);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/simulation/pause"),
        expect.objectContaining({ method: "POST" })
      );
    });
  });
});

