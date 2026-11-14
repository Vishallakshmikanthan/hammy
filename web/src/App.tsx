import React, { useState } from "react";
import { Observatory } from "./components/Observatory";

export const App: React.FC = () => {
  const urlParams = new URLSearchParams(window.location.search);
  const initialPetId = urlParams.get("petId") || "pet_hammy_01";
  const initialToken = urlParams.get("token") || "";

  const [petId, setPetId] = useState(initialPetId);
  const [token, setToken] = useState(initialToken);
  const [activePetId, setActivePetId] = useState(initialPetId);
  const [activeToken, setActiveToken] = useState(initialToken);

  const handleApply = (e: React.FormEvent) => {
    e.preventDefault();
    setActivePetId(petId);
    setActiveToken(token);
  };

  return (
    <div className="app-layout">
      <nav className="top-nav">
        <div className="nav-brand">
          <span className="brand-icon">🐹</span>
          <span className="brand-name">HAMMY</span>
          <span className="brand-subtitle">Simulated Living Creature</span>
        </div>
        <form className="nav-controls" onSubmit={handleApply}>
          <label>
            Pet ID:
            <input
              type="text"
              value={petId}
              onChange={(e) => setPetId(e.target.value)}
              className="input-text"
              placeholder="e.g. pet_hammy_01"
            />
          </label>
          <label>
            JWT Token:
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="input-text"
              placeholder="(optional auth token)"
            />
          </label>
          <button type="submit" className="btn btn-primary btn-sm">
            Connect
          </button>
        </form>
      </nav>

      <Observatory petId={activePetId} token={activeToken || undefined} />
    </div>
  );
};

export default App;

