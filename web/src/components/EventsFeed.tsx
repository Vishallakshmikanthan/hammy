import React from "react";
import { BehaviourType, EventOrigin, WorldEvent } from "../types";

interface EventsFeedProps {
  events: WorldEvent[];
}

export const EventsFeed: React.FC<EventsFeedProps> = ({ events }) => {
  const getOriginBadge = (origin: EventOrigin) => {
    switch (origin) {
      case "observed_physics":
        return <span className="badge badge-origin-physics" data-testid="origin-badge">observed_physics</span>;
      case "sampled_from_skill_model":
        return <span className="badge badge-origin-skill" data-testid="origin-badge">sampled_from_skill_model</span>;
      case "rule":
      default:
        return <span className="badge badge-origin-rule" data-testid="origin-badge">rule</span>;
    }
  };

  const getBehaviourBadge = (behaviour: BehaviourType) => {
    switch (behaviour) {
      case "learned":
        return <span className="badge badge-beh-learned" data-testid="behaviour-badge">learned</span>;
      case "scripted":
        return <span className="badge badge-beh-scripted" data-testid="behaviour-badge">scripted</span>;
      case "rule":
      default:
        return <span className="badge badge-beh-rule" data-testid="behaviour-badge">rule</span>;
    }
  };

  return (
    <section className="card events-card" data-testid="events-feed">
      <div className="card-header">
        <div>
          <h2>Authoritative Events Feed</h2>
          <p className="muted">
            Last {events.length} events recorded in PostgreSQL. Every row links to an immutable record.
          </p>
        </div>
        <span className="badge badge-count" data-testid="events-count">
          {events.length} Events
        </span>
      </div>

      {events.length === 0 ? (
        <div className="empty-state">
          <p>No events recorded yet for this pet.</p>
        </div>
      ) : (
        <div className="table-responsive">
          <table className="events-table">
            <thead>
              <tr>
                <th>Record ID</th>
                <th>Sim Time (s)</th>
                <th>Tick</th>
                <th>Type</th>
                <th>Skill</th>
                <th>Origin</th>
                <th>Behaviour</th>
                <th>Payload</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr key={ev.event_id} className="event-row" data-testid="event-item">
                  <td className="code-font event-id-cell" title={ev.event_id}>
                    <span className="id-pill">{ev.event_id.slice(0, 16)}...</span>
                  </td>
                  <td>{ev.sim_time_sec.toFixed(1)}</td>
                  <td>#{ev.world_tick}</td>
                  <td>
                    <span className="event-type-label">{ev.event_type}</span>
                  </td>
                  <td>{ev.skill_name || "—"}</td>
                  <td>{getOriginBadge(ev.origin)}</td>
                  <td>{getBehaviourBadge(ev.behaviour_type)}</td>
                  <td className="payload-cell">
                    <span className="code-font payload-summary">
                      {JSON.stringify(ev.payload || {})}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};

