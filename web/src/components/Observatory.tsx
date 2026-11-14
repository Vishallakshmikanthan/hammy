import React from "react";
import { AlertTriangle, Sparkles, ShieldCheck, Box } from "lucide-react";
import { usePetObservatory } from "../hooks/usePetObservatory";
import { ActiveBrainView } from "./ActiveBrainView";
import { DrivesPanel } from "./DrivesPanel";
import { EventsFeed } from "./EventsFeed";
import { ObservatoryBanner } from "./ObservatoryBanner";
import { HabitatSceneView } from "../three/habitat/HabitatSceneView";
import { Badge } from "@/components/ui/badge";
import type { Pet, PetState, WorldEvent } from "../types";

interface ObservatoryProps {
  petId?: string;
  token?: string;
}

const AUTONOMOUS_FALLBACK_PET: Pet = {
  id: "pet_hammy_01",
  user_id: "usr_hammy_default",
  name: "Hammy",
  species: "Syrian Hamster (Mesocricetus auratus)",
  morphology_version: "syrian_golden_rig_v3",
  birth_date: "2026-10-01T00:00:00Z",
  created_at: "2026-10-01T00:00:00Z",
};

const AUTONOMOUS_FALLBACK_STATE: PetState = {
  pet_id: "pet_hammy_01",
  version: 108,
  schema_version: "2.0.0",
  environment_version: "terrarium_pbr_v3",
  sim_time_sec: 50400.0,
  simulated_age_days: 18.4,
  real_time_scale: 1.0,
  last_simulated_at: null,
  is_paused: false,
  drives: {
    hunger: 0.28,
    thirst: 0.22,
    energy: 0.86,
    comfort: 0.91,
    stress: 0.12,
    curiosity: 0.74,
    circadian_phase: 3.665,
  },
  position_xyz: [-0.08, 0.16, 0.12],
  yaw_rad: 0.42,
  velocity_xy: [0.08, 0.03],
  angular_velocity_z: 0.0,
  inside_hideout: false,
  inside_tunnel: false,
  on_wheel: false,
  cheek_pouch_fill: 0.35,
  active_skill: "explore_habitat",
  updated_at: null,
};

const AUTONOMOUS_FALLBACK_EVENTS: WorldEvent[] = [
  {
    event_id: "evt_live_3d_wheel_sprint_01",
    pet_id: "pet_hammy_01",
    world_tick: 108,
    sim_time_sec: 50400.0,
    event_type: "autonomous_ethogram_step",
    skill_name: "wheel_run",
    origin: "observed_physics",
    behaviour_type: "learned",
    seed: 42108,
    payload: { zone: "running_wheel", bedding_deform: true },
    created_at: "2026-11-14T12:00:00Z",
  },
  {
    event_id: "evt_live_3d_forage_bowl_02",
    pet_id: "pet_hammy_01",
    world_tick: 107,
    sim_time_sec: 50370.0,
    event_type: "cheek_pouch_forage",
    skill_name: "forage",
    origin: "sampled_from_skill_model",
    behaviour_type: "learned",
    seed: 42107,
    payload: { seeds_collected: 3, pouch_fill: 0.35 },
    created_at: "2026-11-14T11:59:30Z",
  },
  {
    event_id: "evt_live_3d_bedding_dig_03",
    pet_id: "pet_hammy_01",
    world_tick: 106,
    sim_time_sec: 50340.0,
    event_type: "bedding_heightfield_scoop",
    skill_name: "digging",
    origin: "observed_physics",
    behaviour_type: "scripted",
    seed: 42106,
    payload: { paws_active: 4, depth_mm: 6.2 },
    created_at: "2026-11-14T11:59:00Z",
  },
];

export const Observatory: React.FC<ObservatoryProps> = ({
  petId = "pet_hammy_01",
  token,
}) => {
  const {
    pet,
    state,
    events,
    loading,
    error,
    connectionStatus,
    pause,
    resume,
    refresh,
  } = usePetObservatory(petId, token);

  if (loading && !state) {
    return (
      <div
        className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-[#F4EDE0]/80"
        data-testid="observatory-loading"
      >
        <div className="h-11 w-11 rounded-full border-2 border-[#F4EDE0]/20 border-t-[#FF6B5B] animate-spin" />
        <p className="font-display text-2xl tracking-wide text-[#F4EDE0]">
          Connecting to HAMMY authoritative world service...
        </p>
      </div>
    );
  }

  const effectivePet = pet ?? AUTONOMOUS_FALLBACK_PET;
  const effectiveState = state ?? AUTONOMOUS_FALLBACK_STATE;
  const effectiveEvents = events.length > 0 ? events : state ? events : AUTONOMOUS_FALLBACK_EVENTS;

  return (
    <div
      className="max-w-[1600px] mx-auto w-full px-4 sm:px-6 py-3 space-y-4"
      data-testid="observatory-root"
    >
      {/* Top Glass Hero Banner */}
      <ObservatoryBanner
        state={effectiveState}
        connectionStatus={connectionStatus}
        onPause={pause}
        onResume={resume}
        onRefresh={refresh}
      />

      {/* Prominent Home Page 3D Habitat Showcase Section — immediately visible above the fold */}
      <section aria-label="Live 3D Hamster Habitat" className="space-y-2.5">
        <div className="glass-card rounded-2xl px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <Badge variant="coralSolid" className="px-3 py-0.5 text-xs">
              <Box className="h-3.5 w-3.5" />
              LIVE 3D HABITAT
            </Badge>
            <h2 className="font-display text-2xl text-[#F4EDE0] tracking-wide">
              {effectivePet.name}
            </h2>
            <span className="text-xs text-[#F4EDE0]/70">
              Species: <strong className="text-[#F4EDE0]">{effectivePet.species}</strong>
            </span>
            <span className="rounded-full border border-[#F4EDE0]/15 bg-[#0B1325]/60 px-2.5 py-0.5 font-mono text-xs text-[#FF6B5B]">
              ID: {effectivePet.id || petId}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {error && (
              <div
                className="inline-flex items-center gap-2 rounded-full border border-[#FF6B5B]/40 bg-[#FF6B5B]/15 px-3 py-1 text-xs text-[#F4EDE0]"
                data-testid="observatory-error"
              >
                <AlertTriangle className="h-3.5 w-3.5 text-[#FF6B5B]" />
                <span>Autonomous 3D Mode ({error})</span>
                <button
                  type="button"
                  onClick={refresh}
                  className="ml-1 underline font-semibold text-[#FF6B5B] hover:text-[#F4EDE0]"
                >
                  Retry
                </button>
              </div>
            )}
            <div className="hidden md:flex items-center gap-1.5 text-xs text-[#F4EDE0]/70">
              <ShieldCheck className="h-3.5 w-3.5 text-[#FF6B5B]" />
              <span>Drag to Orbit • Scroll to Zoom</span>
            </div>
          </div>
        </div>

        {/* Embedded 3D Habitat right on the Home Page */}
        <HabitatSceneView
          petId={petId}
          token={token}
          embedded={true}
          externalState={effectiveState}
          externalEvents={effectiveEvents}
          externalConnectionStatus={connectionStatus}
        />
      </section>

      {/* Bento Telemetry Grid: Active Brain, Homeostatic Drives, and Authoritative Events */}
      <main className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start pt-1">
        <div className="lg:col-span-5 space-y-5">
          <ActiveBrainView pet={effectivePet} state={effectiveState} />
          <DrivesPanel drives={effectiveState.drives ?? null} />
        </div>

        <div className="lg:col-span-7 space-y-5">
          <EventsFeed events={effectiveEvents} />

          {/* Feature Highlights Strip */}
          <div className="glass-card rounded-2xl p-5 grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="space-y-1">
              <Sparkles className="h-4 w-4 text-[#FF6B5B]" />
              <p className="text-xs font-semibold text-[#F4EDE0]">Shell + Fin Fur</p>
              <p className="text-[11px] text-[#F4EDE0]/60">Anisotropic agouti coat shader</p>
            </div>
            <div className="space-y-1">
              <Sparkles className="h-4 w-4 text-[#FF6B5B]" />
              <p className="text-xs font-semibold text-[#F4EDE0]">Deformable Bedding</p>
              <p className="text-[11px] text-[#F4EDE0]/60">4-paw heightfield imprints</p>
            </div>
            <div className="space-y-1">
              <Sparkles className="h-4 w-4 text-[#FF6B5B]" />
              <p className="text-xs font-semibold text-[#F4EDE0]">Homeostatic Brain</p>
              <p className="text-[11px] text-[#F4EDE0]/60">6-drive utility &amp; RND curiosity</p>
            </div>
            <div className="space-y-1">
              <Sparkles className="h-4 w-4 text-[#FF6B5B]" />
              <p className="text-xs font-semibold text-[#F4EDE0]">Circadian Lighting</p>
              <p className="text-[11px] text-[#F4EDE0]/60">Solar key + nocturnal lamp</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};
