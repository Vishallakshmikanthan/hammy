import React, { useState } from "react";
import { Sparkles, Box, Cpu, Layers, FlaskConical, KeyRound, PawPrint } from "lucide-react";
import { Observatory } from "./components/Observatory";
import { TrainingLabView } from "./components/TrainingLabView";
import { FurBenchmarkView } from "./three/fur/FurBenchmarkView";
import { RigStudioView } from "./three/rig/RigStudioView";
import { HabitatSceneView } from "./three/habitat/HabitatSceneView";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type AppView = "observatory" | "fur-benchmark" | "rig-studio" | "habitat" | "training-lab";

export const App: React.FC = () => {
  const urlParams = new URLSearchParams(window.location.search);
  const initialPetId = urlParams.get("petId") || "pet_hammy_01";
  const initialToken = urlParams.get("token") || "";
  const initialViewParam = urlParams.get("view") as AppView | null;
  const initialView: AppView =
    initialViewParam && ["observatory", "fur-benchmark", "rig-studio", "habitat", "training-lab"].includes(initialViewParam)
      ? initialViewParam
      : "observatory";

  const [view, setView] = useState<AppView>(initialView);
  const [petId, setPetId] = useState(initialPetId);
  const [token, setToken] = useState(initialToken);
  const [activePetId, setActivePetId] = useState(initialPetId);
  const [activeToken, setActiveToken] = useState(initialToken);

  const handleApply = (e: React.FormEvent) => {
    e.preventDefault();
    setActivePetId(petId);
    setActiveToken(token);
  };

  const navItems: { id: AppView; label: string; icon: React.ReactNode }[] = [
    { id: "observatory", label: "Home • 3D Habitat", icon: <Box className="h-3.5 w-3.5" /> },
    { id: "habitat", label: "P3.3 Studio", icon: <Sparkles className="h-3.5 w-3.5" /> },
    { id: "rig-studio", label: "P3.2 Rig", icon: <Cpu className="h-3.5 w-3.5" /> },
    { id: "fur-benchmark", label: "P3.1 Fur", icon: <Layers className="h-3.5 w-3.5" /> },
    { id: "training-lab", label: "P6/7 Lab", icon: <FlaskConical className="h-3.5 w-3.5" /> },
  ];

  return (
    <div className="min-h-screen flex flex-col relative selection:bg-[#FF6B5B]/30 selection:text-[#F4EDE0]">
      {/* Top Floating Glassmorphic Navigation Bar */}
      <header className="sticky top-0 z-40 px-4 sm:px-6 pt-3 pb-1.5">
        <nav className="max-w-[1600px] mx-auto glass-pill-nav rounded-2xl xl:rounded-full px-4 sm:px-5 py-2 flex flex-wrap items-center justify-between gap-3">
          {/* Brand Identity */}
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="h-8 w-8 rounded-full bg-gradient-to-br from-[#FF6B5B] to-[#E05243] flex items-center justify-center shadow-coral-glow text-base">
              🐹
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-display text-2xl tracking-wide text-[#F4EDE0]">
                HAMMY
              </span>
              <span className="hidden 2xl:inline-block text-[11px] text-[#F4EDE0]/60 border-l border-[#F4EDE0]/20 pl-2">
                Living Creature Observatory
              </span>
            </div>
          </div>

          {/* Center Pill Tabs with Coral Active Dot */}
          <div
            className="flex items-center gap-1 flex-wrap rounded-full bg-[#0B1325]/55 border border-[#F4EDE0]/15 p-1"
            role="tablist"
            aria-label="Views"
          >
            {navItems.map((item) => {
              const isActive = view === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setView(item.id)}
                  className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold transition-all duration-200 ${
                    isActive
                      ? "bg-[#F4EDE0]/15 text-[#F4EDE0] shadow-sm border border-[#F4EDE0]/25"
                      : "text-[#F4EDE0]/70 hover:text-[#F4EDE0] hover:bg-[#F4EDE0]/[0.06]"
                  }`}
                >
                  {isActive && (
                    <span className="h-2 w-2 rounded-full bg-[#FF6B5B] shadow-[0_0_8px_#FF6B5B]" />
                  )}
                  {item.icon}
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>

          {/* Right Connection Controls */}
          {(view === "observatory" || view === "habitat") && (
            <form
              className="flex items-center gap-1.5 text-xs shrink-0"
              onSubmit={handleApply}
            >
              <label className="flex items-center gap-1 text-[#F4EDE0]/75">
                <PawPrint className="h-3.5 w-3.5 text-[#FF6B5B]" />
                <span className="sr-only">Pet ID:</span>
                <Input
                  type="text"
                  value={petId}
                  onChange={(e) => setPetId(e.target.value)}
                  className="w-28 h-7 text-xs px-2.5"
                  placeholder="pet_hammy_01"
                />
              </label>
              <label className="flex items-center gap-1 text-[#F4EDE0]/75">
                <KeyRound className="h-3.5 w-3.5 text-[#FF6B5B]" />
                <span className="sr-only">JWT Token:</span>
                <Input
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  className="w-24 h-7 text-xs px-2.5"
                  placeholder="Token"
                />
              </label>
              <Button type="submit" variant="coral" size="sm" className="h-7 px-3 text-xs">
                Connect
              </Button>
            </form>
          )}
        </nav>
      </header>

      {/* Main View Content */}
      <div className="flex-1">
        {view === "observatory" && <Observatory petId={activePetId} token={activeToken || undefined} />}
        {view === "fur-benchmark" && <FurBenchmarkView />}
        {view === "rig-studio" && <RigStudioView />}
        {view === "habitat" && <HabitatSceneView petId={activePetId} token={activeToken || undefined} />}
        {view === "training-lab" && <TrainingLabView />}
      </div>
    </div>
  );
};

export default App;
