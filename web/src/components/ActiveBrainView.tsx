import React from "react";
import { Pet, PetState } from "../types";

interface ActiveBrainViewProps {
  pet: Pet | null;
  state: PetState | null;
}

export const ActiveBrainView: React.FC<ActiveBrainViewProps> = ({ pet, state }) => {
  if (!state) {
    return (
      <section className="card active-brain-card" data-testid="active-brain-view">
        <h2>Active Brain & Simulation View</h2>
        <p className="muted">No simulation state loaded.</p>
      </section>
    );
  }

  const activeSkill = state.active_skill || "idle";
  const policyVersion = "scripted_homeostatic_v1"; // Homeostatic policy baseline
  const schemaVersion = state.schema_version || "2.0.0";
  const morphologyVersion = pet?.morphology_version || "simple_agent_v1";
  const environmentVersion = state.environment_version || "cage_v1";

  const pos = state.position_xyz || [0, 0, 0];
  const posX = pos[0]?.toFixed(2) ?? "0.00";
  const posY = pos[1]?.toFixed(2) ?? "0.00";
  const posZ = pos[2]?.toFixed(2) ?? "0.00";

  return (
    <section className="card active-brain-card" data-testid="active-brain-view">
      <div className="card-header">
        <h2>Active Brain & Policy Context</h2>
        <span className="badge badge-primary" data-testid="active-skill-badge">
          Skill: <strong>{activeSkill}</strong>
        </span>
      </div>

      <div className="metrics-grid">
        <div className="metric-box">
          <span className="metric-label">Policy Version</span>
          <span className="metric-value code-font" data-testid="policy-version">
            {policyVersion}
          </span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Schema Version</span>
          <span className="metric-value code-font" data-testid="schema-version">
            v{schemaVersion}
          </span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Morphology Version</span>
          <span className="metric-value code-font" data-testid="morphology-version">
            {morphologyVersion}
          </span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Environment</span>
          <span className="metric-value code-font" data-testid="env-version">
            {environmentVersion}
          </span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Simulated Age</span>
          <span className="metric-value" data-testid="simulated-age">
            {state.simulated_age_days.toFixed(1)} days
          </span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Sim Time</span>
          <span className="metric-value" data-testid="sim-time">
            {state.sim_time_sec.toFixed(1)} s
          </span>
        </div>

        <div className="metric-box">
          <span className="metric-label">State Version / Tick</span>
          <span className="metric-value" data-testid="state-version">
            #{state.version}
          </span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Position (X, Y, Z)</span>
          <span className="metric-value code-font" data-testid="position-xyz">
            ({posX}, {posY}, {posZ})
          </span>
        </div>
      </div>

      <div className="sub-section">
        <h3>Morphology & Habitat Physical State</h3>
        <div className="tags-row">
          <span
            className={`state-tag ${state.inside_hideout ? "tag-active" : "tag-inactive"}`}
            data-testid="tag-hideout"
          >
            🏠 {state.inside_hideout ? "Inside Hideout" : "Outside Hideout"}
          </span>
          <span
            className={`state-tag ${state.inside_tunnel ? "tag-active" : "tag-inactive"}`}
            data-testid="tag-tunnel"
          >
            🚇 {state.inside_tunnel ? "In Tunnel" : "Outside Tunnel"}
          </span>
          <span
            className={`state-tag ${state.on_wheel ? "tag-active" : "tag-inactive"}`}
            data-testid="tag-wheel"
          >
            🎡 {state.on_wheel ? "On Running Wheel" : "Off Wheel"}
          </span>
          <span className="state-tag tag-info" data-testid="tag-pouch">
            🐹 Cheek Pouch: {(state.cheek_pouch_fill * 100).toFixed(0)}%
          </span>
        </div>
      </div>
    </section>
  );
};

