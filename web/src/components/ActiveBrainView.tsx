import React from "react";
import { Activity, Brain, Compass, Cpu, Home, Layers, Sparkles, Zap } from "lucide-react";
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
  const bt = state.brain_telemetry;
  const policyVersion = state.policy_version || bt?.policy_version || "scripted_homeostatic_v1";
  const motorPolicyVersion = state.motor_policy_version || bt?.motor_policy_version || null;
  const isLearned = bt?.behaviour_mode === "learned" || policyVersion.startsWith("hl_rppo");
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
            Cognitive Controller {isLearned ? "• LEARNED RL" : ""}
          </div>
          <CardTitle className="font-display text-2xl font-normal tracking-wide text-[#F4EDE0]">
            Active Brain &amp; Policy Context
          </CardTitle>
          <CardDescription>
            {isLearned
              ? "Live GPU GRU-Recurrent PPO + RND policy inference & motor context"
              : "Real-time policy execution & spatial coordinates"}
          </CardDescription>
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
              className={`font-mono text-xs font-semibold break-all ${
                isLearned ? "text-emerald-300" : "text-[#F4EDE0]"
              }`}
              data-testid="policy-version"
            >
              {policyVersion}
            </span>
            {motorPolicyVersion && (
              <span className="block font-mono text-[10px] text-[#F4EDE0]/55 mt-0.5 truncate">
                Motor: {motorPolicyVersion}
              </span>
            )}
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
            {bt && (
              <>
                <Badge variant="navy" className="px-3 py-1">
                  🏠 Nest Hoard: {(bt.nest_hoard_level * 100).toFixed(0)}%
                </Badge>
                <Badge variant="success" className="px-3 py-1">
                  🤝 Trust: {(bt.familiarity * 100).toFixed(0)}%
                </Badge>
              </>
            )}
          </div>
        </div>

        {/* Live Neural Policy Distribution, RND Novelty & Spatial Memory Heatmap */}
        {bt && (
          <div
            className="rounded-2xl border border-[#F4EDE0]/15 bg-[#0B1325]/65 p-3.5 space-y-3"
            data-testid="neural-brain-telemetry"
          >
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold uppercase tracking-wider text-emerald-300 flex items-center gap-1.5">
                <Activity className="h-3.5 w-3.5" />
                Live Policy Distribution &amp; RND Curiosity
              </span>
              <span className="font-mono text-[#F4EDE0]/75 flex items-center gap-2">
                <span>
                  <Zap className="h-3 w-3 inline text-amber-300 mr-0.5" />
                  RND: {(bt.rnd_novelty * 100).toFixed(1)}%
                </span>
                <span>H: {(bt.entropy * 100).toFixed(0)}%</span>
              </span>
            </div>

            {bt.top_skills && bt.top_skills.length > 0 && (
              <div className="space-y-1.5">
                {bt.top_skills.slice(0, 5).map(({ skill, prob }) => (
                  <div key={skill} className="space-y-0.5">
                    <div className="flex justify-between text-[11px]">
                      <span className="font-mono text-[#F4EDE0]/85">{skill}</span>
                      <span className="font-mono text-[#FF6B5B]">{(prob * 100).toFixed(1)}%</span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-[#14213D] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-[#FF6B5B] transition-all duration-300"
                        style={{ width: `${Math.min(100, prob * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {bt.spatial_familiarity && bt.spatial_familiarity.length === 8 && (
              <div className="pt-1 border-t border-[#F4EDE0]/10 space-y-1.5">
                <div className="flex justify-between text-[10px] uppercase tracking-wider text-[#F4EDE0]/55">
                  <span>Spatial Familiarity Memory (4x2 Cage Sectors)</span>
                  <span className="font-mono">
                    V_ext={bt.value_ext.toFixed(2)} • V_int={bt.value_int.toFixed(2)}
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-1">
                  {bt.spatial_familiarity.map((fam, idx) => (
                    <div
                      key={idx}
                      className="h-5 rounded flex items-center justify-center font-mono text-[10px] border border-[#F4EDE0]/10"
                      style={{
                        backgroundColor: `rgba(52, 211, 153, ${0.12 + fam * 0.55})`,
                        color: "#F4EDE0",
                      }}
                      title={`Sector ${idx + 1} familiarity: ${(fam * 100).toFixed(0)}%`}
                    >
                      {(fam * 100).toFixed(0)}%
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
