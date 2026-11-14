import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ObservatoryBanner } from "../ObservatoryBanner";
import { ActiveBrainView } from "../ActiveBrainView";
import { DrivesPanel } from "../DrivesPanel";
import { EventsFeed } from "../EventsFeed";
import { Pet, PetState, WorldEvent } from "../../types";

const mockPet: Pet = {
  id: "pet_hammy_01",
  user_id: "usr_hammy_default",
  name: "Hammy",
  species: "Syrian Hamster (Mesocricetus auratus)",
  morphology_version: "simple_agent_v1",
  birth_date: "2026-10-01T00:00:00Z",
  created_at: "2026-10-01T00:00:00Z",
};

const mockState: PetState = {
  pet_id: "pet_hammy_01",
  version: 42,
  schema_version: "2.0.0",
  environment_version: "cage_v1",
  sim_time_sec: 1250.5,
  simulated_age_days: 14.5,
  real_time_scale: 1.0,
  last_simulated_at: "2026-11-14T09:00:00Z",
  is_paused: false,
  drives: {
    hunger: 0.35,
    thirst: 0.45,
    energy: 0.85,
    comfort: 0.9,
    stress: 0.15,
    curiosity: 0.6,
    circadian_phase: 1.57, // ~6h
  },
  position_xyz: [0.12, -0.05, 0.02],
  yaw_rad: 0.5,
  velocity_xy: [0.1, 0.0],
  angular_velocity_z: 0.0,
  inside_hideout: false,
  inside_tunnel: true,
  on_wheel: false,
  cheek_pouch_fill: 0.25,
  active_skill: "explore",
  updated_at: "2026-11-14T09:00:00Z",
};

const mockEvents: WorldEvent[] = [
  {
    event_id: "evt_001_physics",
    pet_id: "pet_hammy_01",
    world_tick: 40,
    sim_time_sec: 1200.0,
    event_type: "wheel_spun",
    skill_name: "wheel_run",
    origin: "observed_physics",
    behaviour_type: "scripted",
    seed: 12345,
    payload: { revs: 5 },
    created_at: "2026-11-14T08:58:00Z",
  },
  {
    event_id: "evt_002_model",
    pet_id: "pet_hammy_01",
    world_tick: 41,
    sim_time_sec: 1230.0,
    event_type: "forage_decision",
    skill_name: "forage",
    origin: "sampled_from_skill_model",
    behaviour_type: "learned",
    seed: 67890,
    payload: { food_detected: true },
    created_at: "2026-11-14T08:59:00Z",
  },
  {
    event_id: "evt_003_rule",
    pet_id: "pet_hammy_01",
    world_tick: 42,
    sim_time_sec: 1250.0,
    event_type: "care_action_applied",
    skill_name: null,
    origin: "rule",
    behaviour_type: "rule",
    seed: 99999,
    payload: { action: "feed", delta_hunger: -0.2 },
    created_at: "2026-11-14T09:00:00Z",
  },
];

describe("Observatory UI Components", () => {
  describe("ObservatoryBanner", () => {
    it("renders RUNNING state, time scale, and pause button when simulation is running", () => {
      const onPause = vi.fn();
      const onResume = vi.fn();
      const onRefresh = vi.fn();

      render(
        <ObservatoryBanner
          state={mockState}
          connectionStatus="connected"
          onPause={onPause}
          onResume={onResume}
          onRefresh={onRefresh}
        />
      );

      expect(screen.getByTestId("status-indicator")).toHaveTextContent("RUNNING");
      expect(screen.getByTestId("time-scale")).toHaveTextContent("1.0x");
      expect(screen.getByTestId("connection-status")).toHaveTextContent("CONNECTED");

      const pauseBtn = screen.getByTestId("pause-btn");
      expect(pauseBtn).toBeInTheDocument();
      fireEvent.click(pauseBtn);
      expect(onPause).toHaveBeenCalledTimes(1);
    });

    it("renders PAUSED state and resume button when simulation is paused", () => {
      const onPause = vi.fn();
      const onResume = vi.fn();
      const onRefresh = vi.fn();

      const pausedState = { ...mockState, is_paused: true };

      render(
        <ObservatoryBanner
          state={pausedState}
          connectionStatus="reconnecting"
          onPause={onPause}
          onResume={onResume}
          onRefresh={onRefresh}
        />
      );

      expect(screen.getByTestId("status-indicator")).toHaveTextContent("PAUSED");
      expect(screen.getByTestId("connection-status")).toHaveTextContent("RECONNECTING");

      const resumeBtn = screen.getByTestId("resume-btn");
      expect(resumeBtn).toBeInTheDocument();
      fireEvent.click(resumeBtn);
      expect(onResume).toHaveBeenCalledTimes(1);
    });
  });

  describe("ActiveBrainView", () => {
    it("renders active skill, policy version, schema version, and morphology", () => {
      render(<ActiveBrainView pet={mockPet} state={mockState} />);

      expect(screen.getByTestId("active-skill-badge")).toHaveTextContent("explore");
      expect(screen.getByTestId("policy-version")).toHaveTextContent("scripted_homeostatic_v1");
      expect(screen.getByTestId("schema-version")).toHaveTextContent("v2.0.0");
      expect(screen.getByTestId("morphology-version")).toHaveTextContent("simple_agent_v1");
      expect(screen.getByTestId("env-version")).toHaveTextContent("cage_v1");
      expect(screen.getByTestId("simulated-age")).toHaveTextContent("14.5 days");
      expect(screen.getByTestId("sim-time")).toHaveTextContent("1250.5 s");
      expect(screen.getByTestId("position-xyz")).toHaveTextContent("(0.12, -0.05, 0.02)");

      expect(screen.getByTestId("tag-tunnel")).toHaveTextContent("In Tunnel");
      expect(screen.getByTestId("tag-pouch")).toHaveTextContent("25%");
    });
  });

  describe("DrivesPanel", () => {
    it("renders all homeostatic drive percentages and circadian phase", () => {
      render(<DrivesPanel drives={mockState.drives} />);

      expect(screen.getByTestId("drive-hunger-val")).toHaveTextContent("35.0%");
      expect(screen.getByTestId("drive-thirst-val")).toHaveTextContent("45.0%");
      expect(screen.getByTestId("drive-energy-val")).toHaveTextContent("85.0%");
      expect(screen.getByTestId("drive-comfort-val")).toHaveTextContent("90.0%");
      expect(screen.getByTestId("drive-stress-val")).toHaveTextContent("15.0%");
      expect(screen.getByTestId("drive-curiosity-val")).toHaveTextContent("60.0%");

      expect(screen.getByTestId("circadian-badge")).toBeInTheDocument();
      expect(screen.getByTestId("circadian-meter")).toBeInTheDocument();
    });
  });

  describe("EventsFeed", () => {
    it("renders authoritative event list with origin badges and behaviour type badges", () => {
      render(<EventsFeed events={mockEvents} />);

      const eventRows = screen.getAllByTestId("event-item");
      expect(eventRows).toHaveLength(3);

      const originBadges = screen.getAllByTestId("origin-badge");
      expect(originBadges).toHaveLength(3);
      expect(originBadges[0]).toHaveTextContent("observed_physics");
      expect(originBadges[1]).toHaveTextContent("sampled_from_skill_model");
      expect(originBadges[2]).toHaveTextContent("rule");

      const behaviourBadges = screen.getAllByTestId("behaviour-badge");
      expect(behaviourBadges).toHaveLength(3);
      expect(behaviourBadges[0]).toHaveTextContent("scripted");
      expect(behaviourBadges[1]).toHaveTextContent("learned");
      expect(behaviourBadges[2]).toHaveTextContent("rule");
    });
  });
});

