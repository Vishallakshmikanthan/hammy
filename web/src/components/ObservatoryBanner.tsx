import React from "react";
import { Play, Pause, RefreshCw, Radio, Clock, Gauge, Sparkles } from "lucide-react";
import { ConnectionStatus, PetState } from "../types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface ObservatoryBannerProps {
  state: PetState | null;
  connectionStatus: ConnectionStatus;
  onPause: () => void;
  onResume: () => void;
  onRefresh: () => void;
}

export const ObservatoryBanner: React.FC<ObservatoryBannerProps> = ({
  state,
  connectionStatus,
  onPause,
  onResume,
  onRefresh,
}) => {
  const isPaused = state?.is_paused ?? false;
  const timeScale = state?.real_time_scale ?? 1.0;
  const lastUpdate = state?.last_simulated_at
    ? new Date(state.last_simulated_at).toLocaleString()
    : "Autonomous Real-Time";

  const connectionVariant =
    connectionStatus === "connected"
      ? "success"
      : connectionStatus === "reconnecting"
      ? "warning"
      : "default";

  return (
    <header
      className="relative overflow-hidden rounded-3xl glass-surface fluted-glass-backdrop px-6 py-4 md:px-7 md:py-5 transition-all duration-300"
      data-testid="observatory-banner"
    >
      {/* Warm Coral Ambient Glow inside Hero Banner */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-20 left-1/3 h-52 w-96 -translate-x-1/2 rounded-full bg-[#FF6B5B]/32 blur-[75px] animate-coral-glow"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-16 right-10 h-40 w-64 rounded-full bg-[#F4EDE0]/10 blur-[60px]"
      />

      <div className="relative z-10 flex flex-col xl:flex-row xl:items-center justify-between gap-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="inline-flex items-center gap-1.5 rounded-full border border-[#F4EDE0]/20 bg-[#14213D]/65 px-3 py-0.5 text-[11px] text-[#F4EDE0]/90 backdrop-blur-xl">
              <Sparkles className="h-3 w-3 text-[#FF6B5B]" />
              <span>Authoritative Neuro-Physical Habitat</span>
            </div>

            <Badge
              variant={isPaused ? "warning" : "success"}
              className="px-2.5 py-0.5 text-[11px] tracking-wider uppercase"
              data-testid="status-indicator"
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  isPaused ? "bg-amber-400" : "bg-emerald-400 shadow-[0_0_8px_#34d399]"
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
              className="inline-flex items-center gap-1.5 rounded-full border border-[#F4EDE0]/15 bg-[#14213D]/65 px-2.5 py-0.5 text-[11px] text-[#F4EDE0]/75 backdrop-blur-md"
              data-testid="time-scale"
            >
              <Gauge className="h-3 w-3 text-[#FF6B5B]" />
              Time Scale: <strong className="text-[#F4EDE0] font-mono">{timeScale.toFixed(1)}x</strong>
            </span>

            <span
              className="inline-flex items-center gap-1.5 rounded-full border border-[#F4EDE0]/15 bg-[#14213D]/65 px-2.5 py-0.5 text-[11px] text-[#F4EDE0]/75 backdrop-blur-md"
              data-testid="last-update"
            >
              <Clock className="h-3 w-3 text-[#FF6B5B]" />
              Last World Update: <strong className="text-[#F4EDE0]">{lastUpdate}</strong>
            </span>
          </div>

          <div className="flex flex-col md:flex-row md:items-baseline gap-2 md:gap-4">
            <h1 className="font-display text-3xl sm:text-4xl md:text-[42px] font-normal tracking-tight text-[#F4EDE0] leading-none">
              A miniature life that{" "}
              <span className="italic text-[#FF6B5B]">breathes &amp; remembers.</span>
            </h1>
            <p className="text-xs text-[#F4EDE0]/70 max-w-md">
              HAMMY Brain Observatory — live 3D glass terrarium, homeostatic drives &amp; learned skill policies.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 shrink-0">
          {isPaused ? (
            <Button
              type="button"
              variant="coral"
              size="sm"
              onClick={onResume}
              data-testid="resume-btn"
              className="h-9 px-4"
            >
              <Play className="h-3.5 w-3.5 fill-current" />
              Resume Simulation
            </Button>
          ) : (
            <Button
              type="button"
              variant="coral"
              size="sm"
              onClick={onPause}
              data-testid="pause-btn"
              className="h-9 px-4"
            >
              <Pause className="h-3.5 w-3.5 fill-current" />
              Pause Simulation
            </Button>
          )}
          <Button
            type="button"
            variant="glass"
            size="sm"
            onClick={onRefresh}
            data-testid="refresh-btn"
            title="Refresh server state"
            className="h-9 px-4"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        </div>
      </div>
    </header>
  );
};
