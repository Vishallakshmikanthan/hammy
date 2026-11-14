import React from "react";
import { usePetObservatory } from "../hooks/usePetObservatory";
import { ActiveBrainView } from "./ActiveBrainView";
import { DrivesPanel } from "./DrivesPanel";
import { EventsFeed } from "./EventsFeed";
import { ObservatoryBanner } from "./ObservatoryBanner";

interface ObservatoryProps {
  petId?: string;
  token?: string;
}

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
      <div className="observatory-loading" data-testid="observatory-loading">
        <div className="spinner" />
        <p>Connecting to HAMMY authoritative world service...</p>
      </div>
    );
  }

  return (
    <div className="observatory-container" data-testid="observatory-root">
      <ObservatoryBanner
        state={state}
        connectionStatus={connectionStatus}
        onPause={pause}
        onResume={resume}
        onRefresh={refresh}
      />

      {error && (
        <div className="alert-error" data-testid="observatory-error">
          <span>⚠️ {error}</span>
          <button type="button" onClick={refresh} className="btn btn-sm">
            Retry
          </button>
        </div>
      )}

      <main className="observatory-main">
        <div className="pet-overview-bar">
          <div className="pet-overview-info">
            <h2>{pet?.name || "Hammy"}</h2>
            <span className="pet-species-pill">
              Species: {pet?.species || "Syrian Hamster (Mesocricetus auratus)"}
            </span>
            <span className="pet-id-pill code-font">ID: {pet?.id || petId}</span>
          </div>
        </div>

        <div className="observatory-grid">
          <div className="grid-col-left">
            <ActiveBrainView pet={pet} state={state} />
            <DrivesPanel drives={state?.drives ?? null} />
          </div>

          <div className="grid-col-right">
            <EventsFeed events={events} />
          </div>
        </div>
      </main>
    </div>
  );
};

