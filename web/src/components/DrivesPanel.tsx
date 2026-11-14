import React from "react";
import { DriveVector } from "../types";

interface DrivesPanelProps {
  drives: DriveVector | null;
}

interface DriveBarConfig {
  key: keyof Omit<DriveVector, "circadian_phase">;
  label: string;
  icon: string;
  invertedWarning?: boolean; // If true, lower value is worse (e.g. Energy, Comfort)
}

const DRIVE_CONFIGS: DriveBarConfig[] = [
  { key: "hunger", label: "Hunger", icon: "🥕" },
  { key: "thirst", label: "Thirst", icon: "💧" },
  { key: "energy", label: "Energy", icon: "⚡", invertedWarning: true },
  { key: "comfort", label: "Comfort", icon: "🛏️", invertedWarning: true },
  { key: "stress", label: "Stress", icon: "💥" },
  { key: "curiosity", label: "Curiosity", icon: "🔍" },
];

export const DrivesPanel: React.FC<DrivesPanelProps> = ({ drives }) => {
  if (!drives) {
    return (
      <section className="card drives-card" data-testid="drives-panel">
        <h2>Homeostatic Drives & Needs</h2>
        <p className="muted">No drive data available.</p>
      </section>
    );
  }

  // Circadian phase is [0, 2π) or [0, 24h]
  const phaseRad = drives.circadian_phase ?? 0;
  // Convert radians [0, 2π) to hours [0, 24)
  const phaseHours = ((phaseRad / (2 * Math.PI)) * 24) % 24;
  const isHamsterNight = phaseHours >= 18 || phaseHours < 6; // Nocturnal active period

  const getStatusClass = (value: number, inverted?: boolean) => {
    if (inverted) {
      if (value < 0.2) return "bar-danger";
      if (value < 0.4) return "bar-warning";
      return "bar-healthy";
    } else {
      if (value >= 0.8) return "bar-danger";
      if (value >= 0.6) return "bar-warning";
      return "bar-healthy";
    }
  };

  return (
    <section className="card drives-card" data-testid="drives-panel">
      <div className="card-header">
        <h2>Homeostatic Drives & Needs</h2>
        <span className="badge badge-neutral" data-testid="circadian-badge">
          Circadian: {isHamsterNight ? "🌙 Active (Night)" : "☀️ Rest (Day)"} (
          {phaseHours.toFixed(1)}h)
        </span>
      </div>

      <div className="drives-list">
        {DRIVE_CONFIGS.map(({ key, label, icon, invertedWarning }) => {
          const val = drives[key] ?? 0;
          const percentage = Math.min(Math.max(val * 100, 0), 100);
          const statusClass = getStatusClass(val, invertedWarning);

          return (
            <div
              key={key}
              className="drive-item"
              data-testid={`drive-${key}`}
            >
              <div className="drive-meta">
                <span className="drive-label">
                  <span className="drive-icon">{icon}</span> {label}
                </span>
                <span className="drive-pct" data-testid={`drive-${key}-val`}>
                  {percentage.toFixed(1)}%
                </span>
              </div>
              <div className="progress-track" role="progressbar" aria-valuenow={percentage} aria-valuemin={0} aria-valuemax={100}>
                <div
                  className={`progress-fill ${statusClass}`}
                  style={{ width: `${percentage}%` }}
                />
                {/* Safe / warning guideline at 60% */}
                <div className="guide-marker" style={{ left: "60%" }} title="Threshold" />
              </div>
            </div>
          );
        })}
      </div>

      <div className="circadian-meter" data-testid="circadian-meter">
        <div className="meter-label">
          <span>Circadian Phase Angle</span>
          <span className="code-font">{phaseRad.toFixed(3)} rad ({phaseHours.toFixed(1)} h)</span>
        </div>
        <div className="phase-track">
          <div
            className="phase-pin"
            style={{ left: `${(phaseHours / 24) * 100}%` }}
            title={`Phase: ${phaseHours.toFixed(1)}h`}
          />
          <div className="phase-zones">
            <span className="zone-night">Night (Active)</span>
            <span className="zone-day">Day (Sleeping)</span>
            <span className="zone-night">Night</span>
          </div>
        </div>
      </div>
    </section>
  );
};

