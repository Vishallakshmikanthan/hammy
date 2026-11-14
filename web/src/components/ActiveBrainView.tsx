import React from "react";
import { Brain, Cpu, Compass, Home, Layers, Sparkles } from "lucide-react";
import { Pet, PetState } from "../types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface ActiveBrainViewProps {
  pet: Pet | null;
  state: PetState | null;
}

export const ActiveBrainView: React.FC<ActiveBrainViewProps> = ({ pet, state }) => {
  if (!state) {
    return (
      <Card data-testid="active-brain-view">
        <CardHeader>
          <CardTitle className="font-display text-2xl font-normal">Active Brain &amp; Simulation View</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-[#F4EDE0]/65">No simulation state loaded.</p>
        </CardContent>
      </Card>
    );
  }

  const activeSkill = state.active_skill || "idle";
  const policyVersion = "scripted_homeostatic_v1";
  const schemaVersion = state.schema_version || "2.0.0";
  const morphologyVersion = pet?.morphology_version || "simple_agent_v1";
  const environmentVersion = state.environment_version || "cage_v1";

  const pos = state.position_xyz || [0, 0, 0];
  const posX = pos[0]?.toFixed(2) ?? "0.00";
  const posY = pos[1]?.toFixed(2) ?? "0.00";
  const posZ = pos[2]?.toFixed(2) ?? "0.00";

  return (
    <Card className="relative overflow-hidden" data-testid="active-brain-view">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full bg-[#FF6B5B]/15 blur-2xl"
      />
      <CardHeader className="pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#FF6B5B] mb-1">
            <Brain className="h-3.5 w-3.5" />
            Cognitive Controller
          </div>
          <CardTitle className="font-display text-2xl font-normal tracking-wide text-[#F4EDE0]">
            Active Brain &amp; Policy Context
          </CardTitle>
          <CardDescription>Real-time policy execution &amp; spatial coordinates</CardDescription>
        </div>
        <Badge
          variant="coralSolid"
          className="px-3.5 py-1 text-xs"
          data-testid="active-skill-badge"
        >
          <Sparkles className="h-3 w-3" />
          Skill: <strong>{activeSkill}</strong>
        </Badge>
      </CardHeader>

      <CardContent className="space-y-5">
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-2 gap-2.5">
          <div className="rounded-xl border border-[#F4EDE0]/12 bg-[#0B1325]/55 p-3 backdrop-blur-md">
            <span className="block text-[11px] uppercase tracking-wider text-[#F4EDE0]/55 mb-1">
              Policy Version
            </span>
            <span
              className="font-mono text-xs font-semibold text-[#F4EDE0] break-all"
              data-testid="policy-version"
            >
              {policyVersion}
            </span>
          </div>

          <div className="rounded-xl border border-[#F4EDE0]/12 bg-[#0B1325]/55 p-3 backdrop-blur-md">
            <span className="block text-[11px] uppercase tracking-wider text-[#F4EDE0]/55 mb-1">
              Schema Version
            </span>
            <span
              className="font-mono text-xs font-semibold text-[#F4EDE0]"
              data-testid="schema-version"
            >
              v{schemaVersion}
            </span>
          </div>

          <div className="rounded-xl border border-[#F4EDE0]/12 bg-[#0B1325]/55 p-3 backdrop-blur-md">
            <span className="block text-[11px] uppercase tracking-wider text-[#F4EDE0]/55 mb-1">
              Morphology Version
            </span>
            <span
              className="font-mono text-xs font-semibold text-[#F4EDE0]"
              data-testid="morphology-version"
            >
              {morphologyVersion}
            </span>
          </div>

          <div className="rounded-xl border border-[#F4EDE0]/12 bg-[#0B1325]/55 p-3 backdrop-blur-md">
            <span className="block text-[11px] uppercase tracking-wider text-[#F4EDE0]/55 mb-1">
              Environment
            </span>
            <span
              className="font-mono text-xs font-semibold text-[#F4EDE0]"
              data-testid="env-version"
            >
              {environmentVersion}
            </span>
          </div>

          <div className="rounded-xl border border-[#F4EDE0]/12 bg-[#0B1325]/55 p-3 backdrop-blur-md">
            <span className="block text-[11px] uppercase tracking-wider text-[#F4EDE0]/55 mb-1">
              Simulated Age
            </span>
            <span
              className="text-sm font-semibold text-[#F4EDE0]"
              data-testid="simulated-age"
            >
              {state.simulated_age_days.toFixed(1)} days
            </span>
          </div>

          <div className="rounded-xl border border-[#F4EDE0]/12 bg-[#0B1325]/55 p-3 backdrop-blur-md">
            <span className="block text-[11px] uppercase tracking-wider text-[#F4EDE0]/55 mb-1">
              Sim Time
            </span>
            <span
              className="font-mono text-sm font-semibold text-[#F4EDE0]"
              data-testid="sim-time"
            >
              {state.sim_time_sec.toFixed(1)} s
            </span>
          </div>

          <div className="rounded-xl border border-[#F4EDE0]/12 bg-[#0B1325]/55 p-3 backdrop-blur-md">
            <span className="block text-[11px] uppercase tracking-wider text-[#F4EDE0]/55 mb-1">
              State Version / Tick
            </span>
            <span
              className="font-mono text-sm font-semibold text-[#FF6B5B]"
              data-testid="state-version"
            >
              #{state.version}
            </span>
          </div>

          <div className="rounded-xl border border-[#F4EDE0]/12 bg-[#0B1325]/55 p-3 backdrop-blur-md">
            <span className="block text-[11px] uppercase tracking-wider text-[#F4EDE0]/55 mb-1">
              Position (X, Y, Z)
            </span>
            <span
              className="font-mono text-xs font-semibold text-[#F4EDE0]"
              data-testid="position-xyz"
            >
              ({posX}, {posY}, {posZ})
            </span>
          </div>
        </div>

        <div className="space-y-2.5 pt-1">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[#F4EDE0]/65">
            <Compass className="h-3.5 w-3.5 text-[#FF6B5B]" />
            <h3>Morphology &amp; Habitat Physical State</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge
              variant={state.inside_hideout ? "success" : "navy"}
              className="px-3 py-1"
              data-testid="tag-hideout"
            >
              <Home className="h-3 w-3" />
              {state.inside_hideout ? "Inside Hideout" : "Outside Hideout"}
            </Badge>
            <Badge
              variant={state.inside_tunnel ? "success" : "navy"}
              className="px-3 py-1"
              data-testid="tag-tunnel"
            >
              <Layers className="h-3 w-3" />
              {state.inside_tunnel ? "In Tunnel" : "Outside Tunnel"}
            </Badge>
            <Badge
              variant={state.on_wheel ? "success" : "navy"}
              className="px-3 py-1"
              data-testid="tag-wheel"
            >
              <Cpu className="h-3 w-3" />
              {state.on_wheel ? "On Running Wheel" : "Off Wheel"}
            </Badge>
            <Badge
              variant="default"
              className="px-3 py-1"
              data-testid="tag-pouch"
            >
              🐹 Cheek Pouch: {(state.cheek_pouch_fill * 100).toFixed(0)}%
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
