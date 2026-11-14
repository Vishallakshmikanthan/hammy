import React from "react";
import { ConnectionStatus, PetState } from "../types";

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
    : "No updates yet";

  return (
    <header className="observatory-banner" data-testid="observatory-banner">
      <div className="banner-left">
        <h1 className="banner-title">HAMMY Brain Observatory</h1>
        <div className="banner-badges">
          <span
            className={`status-pill ${isPaused ? "pill-paused" : "pill-running"}`}
            data-testid="status-indicator"
          >
            <span className="dot" />
            {isPaused ? "PAUSED" : "RUNNING"}
          </span>

          <span
            className={`status-pill pill-connection pill-${connectionStatus}`}
            data-testid="connection-status"
          >
            <span className="dot" />
            {connectionStatus.toUpperCase()}
          </span>

          <span className="info-chip" data-testid="time-scale">
            Time Scale: <strong>{timeScale.toFixed(1)}x</strong>
          </span>

          <span className="info-chip" data-testid="last-update">
            Last World Update: <strong>{lastUpdate}</strong>
          </span>
        </div>
      </div>

      <div className="banner-actions">
        {isPaused ? (
          <button
            type="button"
            className="btn btn-resume"
            onClick={onResume}
            data-testid="resume-btn"
          >
            ▶ Resume Simulation
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-pause"
            onClick={onPause}
            data-testid="pause-btn"
          >
            ⏸ Pause Simulation
          </button>
        )}
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onRefresh}
          data-testid="refresh-btn"
          title="Refresh server state"
        >
          🔄 Refresh
        </button>
      </div>
    </header>
  );
};

