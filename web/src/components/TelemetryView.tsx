import React from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Brain,
  Clock,
  Cpu,
  Database,
  Gauge,
  Pause,
  Play,
  Radio,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { usePetObservatory } from "../hooks/usePetObservatory";
import { ActiveBrainView } from "./ActiveBrainView";
import { DrivesPanel } from "./DrivesPanel";
import { EventsFeed } from "./EventsFeed";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AUTONOMOUS_FALLBACK_EVENTS,
  AUTONOMOUS_FALLBACK_PET,
  AUTONOMOUS_FALLBACK_STATE,
} from "../lib/fallbackObservatoryData";

interface TelemetryViewProps {
  petId?: string;
  token?: string;
  onNavigateHabitat?: () => void;
}

export const TelemetryView: React.FC<TelemetryViewProps> = ({
  petId = "pet_hammy_01",
  token,
  onNavigateHabitat,
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
    setTimeScale,
    triggerTick,
    refresh,
  } = usePetObservatory(petId, token);

  if (loading && !state) {
    return (
      <div
        className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-[#F4EDE0]/80"
        data-testid="telemetry-loading"
      >
        <div className="h-11 w-11 rounded-full border-2 border-[#F4EDE0]/20 border-t-[#FF6B5B] animate-spin" />
        <p className="font-display text-2xl tracking-wide text-[#F4EDE0]">
          Loading HAMMY Brain &amp; Telemetry...
        </p>
      </div>
    );
  }

  const effectivePet = pet ?? AUTONOMOUS_FALLBACK_PET;
  const effectiveState = state ?? AUTONOMOUS_FALLBACK_STATE;
  const effectiveEvents =
    events.length > 0 ? events : state ? events : AUTONOMOUS_FALLBACK_EVENTS;

  const isPaused = effectiveState.is_paused ?? false;
  const timeScale = effectiveState.real_time_scale ?? 1.0;
  const connectionVariant =
    connectionStatus === "connected"
      ? "success"
      : connectionStatus === "reconnecting"
      ? "warning"
      : "default";

  return (
    <div
      className="max-w-[1600px] mx-auto w-full px-4 sm:px-6 py-4 space-y-5"
      data-testid="telemetry-root"
    >
      {/* Unified Telemetry Command Header */}
      <header className="relative overflow-hidden rounded-2xl glass-surface fluted-glass-backdrop px-5 py-4 border border-[#F4EDE0]/15">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-20 left-1/4 h-44 w-80 -translate-x-1/2 rounded-full bg-[#FF6B5B]/25 blur-[70px]"
        />
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="coralSolid" className="px-2.5 py-0.5 text-[11px]">
                <Brain className="h-3 w-3 mr-1" />
                BRAIN &amp; TELEMETRY
              </Badge>
              <Badge
                variant={isPaused ? "warning" : "success"}
                className="px-2.5 py-0.5 text-[11px] tracking-wider uppercase"
                data-testid="status-indicator"
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    isPaused
                      ? "bg-amber-400"
                      : "bg-emerald-400 shadow-[0_0_8px_#34d399]"
                  }`}
                />
                {isPaused ? "PAUSED" : "RUNNING"}
              </Badge>
              <Badge
                variant={connectionVariant}
                className="px-2.5 py-0.5 text-[11px] tracking-wider uppercase"
                data-testid="connection-status"
              >
                <Radio className="h-3 w-3" />
                {connectionStatus.toUpperCase()}
              </Badge>
              <div
                className="inline-flex items-center gap-1 rounded-full border border-[#F4EDE0]/15 bg-[#14213D]/65 px-2.5 py-0.5 text-[11px] text-[#F4EDE0]/75"
                data-testid="time-scale"
              >
                <Gauge className="h-3 w-3 text-[#FF6B5B]" />
                <span>Time Scale:</span>
                <strong className="text-[#F4EDE0] font-mono mr-1">
                  {timeScale.toFixed(1)}x
                </strong>
                {[1, 10, 60, 300].map((mult) => {
                  const active = Math.abs(timeScale - mult) < 0.5;
                  return (
                    <button
                      key={mult}
                      type="button"
                      data-testid={`telemetry-timescale-${mult}x`}
                      onClick={() => setTimeScale(mult)}
                      className={`px-1.5 py-0.5 rounded-full font-mono text-[10px] transition ${
                        active
                          ? "bg-[#FF6B5B] text-[#0B1325] font-bold"
                          : "text-[#F4EDE0]/70 hover:bg-[#F4EDE0]/15 hover:text-[#F4EDE0]"
                      }`}
                    >
                      {mult}x
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex flex-wrap items-baseline gap-3">
              <h1 className="font-display text-3xl text-[#F4EDE0] tracking-tight leading-none">
                {effectivePet.name}{" "}
                <span className="italic text-[#FF6B5B]">Cognitive Observatory</span>
              </h1>
              <span className="text-xs text-[#F4EDE0]/65">
                Active policy context, 6-axis homeostatic physiology &amp; immutable world ledger.
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            {error && (
              <div
                className="inline-flex items-center gap-1.5 rounded-full border border-[#FF6B5B]/40 bg-[#FF6B5B]/15 px-3 py-1 text-xs text-[#F4EDE0]"
                data-testid="telemetry-error"
              >
                <AlertTriangle className="h-3.5 w-3.5 text-[#FF6B5B]" />
                <span>Offline Fallback</span>
              </div>
            )}
            {onNavigateHabitat && (
              <Button
                type="button"
                variant="glass"
                size="sm"
                onClick={onNavigateHabitat}
                className="h-8 px-3 text-xs gap-1.5"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                3D Habitat
              </Button>
            )}
            {isPaused ? (
              <Button
                type="button"
                variant="coral"
                size="sm"
                onClick={resume}
                data-testid="resume-btn"
                className="h-8 px-3.5 text-xs"
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                Resume
              </Button>
            ) : (
              <Button
                type="button"
                variant="coral"
                size="sm"
                onClick={pause}
                data-testid="pause-btn"
                className="h-8 px-3.5 text-xs"
              >
                <Pause className="h-3.5 w-3.5 fill-current" />
                Pause
              </Button>
            )}
            <Button
              type="button"
              variant="glass"
              size="sm"
              onClick={triggerTick}
              data-testid="step-brain-btn"
              title="Run one immediate RL brain decision tick"
              className="h-8 px-3 text-xs gap-1.5 border-emerald-400/35 text-emerald-200 hover:bg-emerald-400/15"
            >
              <Brain className="h-3.5 w-3.5" />
              Step Brain
            </Button>
            <Button
              type="button"
              variant="glass"
              size="sm"
              onClick={refresh}
              data-testid="refresh-btn"
              className="h-8 px-3 text-xs"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      {/* 4-Card Live KPI Summary Strip */}
      <section
        aria-label="Live Telemetry Summary"
        className="grid grid-cols-2 lg:grid-cols-4 gap-3.5"
      >
        <div className="glass-card rounded-2xl px-4 py-3.5 border border-[#F4EDE0]/12 flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#F4EDE0]/55">
              Active Skill
            </p>
            <p className="font-mono text-base font-semibold text-[#FF6B5B] mt-0.5">
              {effectiveState.active_skill || "idle"}
            </p>
          </div>
          <div className="h-9 w-9 rounded-xl bg-[#FF6B5B]/15 border border-[#FF6B5B]/30 flex items-center justify-center shrink-0">
            <Cpu className="h-4 w-4 text-[#FF6B5B]" />
          </div>
        </div>

        <div className="glass-card rounded-2xl px-4 py-3.5 border border-[#F4EDE0]/12 flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#F4EDE0]/55">
              World Tick &amp; Sim Time
            </p>
            <p className="font-mono text-base font-semibold text-[#F4EDE0] mt-0.5">
              #{effectiveState.version}{" "}
              <span className="text-xs font-normal text-[#F4EDE0]/60">
                • {effectiveState.sim_time_sec.toFixed(1)}s
              </span>
            </p>
          </div>
          <div className="h-9 w-9 rounded-xl bg-[#F4EDE0]/10 border border-[#F4EDE0]/15 flex items-center justify-center shrink-0">
            <Clock className="h-4 w-4 text-[#F4EDE0]/80" />
          </div>
        </div>

        <div className="glass-card rounded-2xl px-4 py-3.5 border border-[#F4EDE0]/12 flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#F4EDE0]/55">
              Simulated Age
            </p>
            <p className="font-mono text-base font-semibold text-[#F4EDE0] mt-0.5">
              {effectiveState.simulated_age_days.toFixed(1)} days
            </p>
          </div>
          <div className="h-9 w-9 rounded-xl bg-[#F4EDE0]/10 border border-[#F4EDE0]/15 flex items-center justify-center shrink-0">
            <Sparkles className="h-4 w-4 text-[#FF6B5B]" />
          </div>
        </div>

        <div className="glass-card rounded-2xl px-4 py-3.5 border border-[#F4EDE0]/12 flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#F4EDE0]/55">
              Ledger Records
            </p>
            <p className="font-mono text-base font-semibold text-[#F4EDE0] mt-0.5">
              {effectiveEvents.length}{" "}
              <span className="text-xs font-normal text-[#F4EDE0]/60">events</span>
            </p>
          </div>
          <div className="h-9 w-9 rounded-xl bg-[#F4EDE0]/10 border border-[#F4EDE0]/15 flex items-center justify-center shrink-0">
            <Database className="h-4 w-4 text-[#F4EDE0]/80" />
          </div>
        </div>
      </section>

      {/* Main Telemetry Workspace: Active Brain + Drives on Left, Events Ledger on Right */}
      <main className="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
        <div className="xl:col-span-5 space-y-5">
          <ActiveBrainView pet={effectivePet} state={effectiveState} />
          <DrivesPanel drives={effectiveState.drives ?? null} />
        </div>

        <div className="xl:col-span-7 min-w-0">
          <EventsFeed events={effectiveEvents} />
        </div>
      </main>
    </div>
  );
};
