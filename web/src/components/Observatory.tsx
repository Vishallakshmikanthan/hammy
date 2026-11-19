import React from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  Box,
  Brain,
  Gauge,
  Pause,
  Play,
  Radio,
  RefreshCw,
} from "lucide-react";
import { usePetObservatory } from "../hooks/usePetObservatory";
import { ParentInteractionPanel } from "./ParentInteractionPanel";
import { HabitatSceneView } from "../three/habitat/HabitatSceneView";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AUTONOMOUS_FALLBACK_EVENTS,
  AUTONOMOUS_FALLBACK_PET,
  AUTONOMOUS_FALLBACK_STATE,
} from "../lib/fallbackObservatoryData";

interface ObservatoryProps {
  petId?: string;
  token?: string;
  onOpenTelemetry?: () => void;
}

export const Observatory: React.FC<ObservatoryProps> = ({
  petId = "pet_hammy_01",
  token,
  onOpenTelemetry,
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
      className="max-w-[1600px] mx-auto w-full px-4 sm:px-6 py-3 space-y-3"
      data-testid="observatory-root"
    >
      {/* Unified Production Studio Command Strip */}
      <header
        className="relative overflow-hidden rounded-2xl glass-surface fluted-glass-backdrop px-4 sm:px-5 py-2.5 border border-[#F4EDE0]/15"
        data-testid="observatory-banner"
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-16 left-1/4 h-36 w-72 -translate-x-1/2 rounded-full bg-[#FF6B5B]/25 blur-[65px]"
        />

        <div className="relative z-10 flex flex-wrap items-center justify-between gap-3">
          {/* Left: Pet Identity + Live Telemetry Status */}
          <div className="flex flex-wrap items-center gap-2.5">
            <Badge variant="coralSolid" className="px-2.5 py-0.5 text-[11px]">
              <Box className="h-3 w-3" />
              LIVE 3D HABITAT
            </Badge>
            <h1 className="font-display text-2xl text-[#F4EDE0] tracking-wide leading-none">
              {effectivePet.name}
            </h1>
            <span className="hidden sm:inline text-xs text-[#F4EDE0]/65">
              {effectivePet.species}
            </span>

            <span className="hidden md:inline-block h-4 w-px bg-[#F4EDE0]/15 mx-0.5" />

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

            <span
              className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-[#F4EDE0]/15 bg-[#14213D]/65 px-2.5 py-0.5 text-[11px] text-[#F4EDE0]/75"
              data-testid="time-scale"
            >
              <Gauge className="h-3 w-3 text-[#FF6B5B]" />
              <strong className="text-[#F4EDE0] font-mono">
                {timeScale.toFixed(1)}x
              </strong>
            </span>

            {error && (
              <div
                className="inline-flex items-center gap-1.5 rounded-full border border-[#FF6B5B]/40 bg-[#FF6B5B]/15 px-2.5 py-0.5 text-[11px] text-[#F4EDE0]"
                data-testid="observatory-error"
              >
                <AlertTriangle className="h-3 w-3 text-[#FF6B5B]" />
                <span>Autonomous 3D Mode</span>
                <button
                  type="button"
                  onClick={refresh}
                  className="ml-1 underline font-semibold text-[#FF6B5B] hover:text-[#F4EDE0]"
                >
                  Retry
                </button>
              </div>
            )}
          </div>

          {/* Right: Telemetry Quick-Jump + Simulation Controls */}
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            {onOpenTelemetry && (
              <Button
                type="button"
                variant="glass"
                size="sm"
                onClick={onOpenTelemetry}
                data-testid="open-telemetry-btn"
                className="h-8 px-3 text-xs gap-1.5 border-[#FF6B5B]/30 hover:border-[#FF6B5B]/60"
              >
                <Brain className="h-3.5 w-3.5 text-[#FF6B5B]" />
                Brain &amp; Telemetry
                <ArrowUpRight className="h-3 w-3 text-[#F4EDE0]/60" />
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
              onClick={refresh}
              data-testid="refresh-btn"
              title="Refresh server state"
              className="h-8 px-3 text-xs"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      {/* Main 3D Habitat Stage + Right Lateral Tabbed Studio Panel */}
      <section aria-label="Live 3D Hamster Habitat" className="space-y-3">
        <HabitatSceneView
          petId={petId}
          token={token}
          embedded={true}
          externalState={effectiveState}
          externalEvents={effectiveEvents}
          externalConnectionStatus={connectionStatus}
        />

        {/* Parent Petting / Taming & MuJoCo ONNX Physics Interaction Dock */}
        <ParentInteractionPanel />
      </section>
    </div>
  );
};
