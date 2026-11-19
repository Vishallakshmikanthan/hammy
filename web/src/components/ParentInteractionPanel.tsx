import React, { useEffect, useState } from "react";
import { Heart, Hand, Cookie, Bell, Cpu, Activity, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

type ParentAction = "offer_treat" | "gentle_pet" | "call_attention";
type HamsterResponse = "avoid_and_retreat" | "cautious_sniff" | "accept_petting";

interface MujocoClipMeta {
  clip_id: string;
  skill_id: string;
  origin: string;
  behaviour_type: string;
  morphology_version: string;
  fps: number;
  num_keyframes: number;
  duration_s: number;
  displacement_m: number;
  asset_url: string;
}

interface InteractionState {
  familiarity: number;
  stress: number;
  lastResponse: HamsterResponse | null;
  lastRationale: string;
  activeClip: MujocoClipMeta | null;
  sourceMode: "backend" | "local_manifest";
}

export const ParentInteractionPanel: React.FC = () => {
  const [clips, setClips] = useState<MujocoClipMeta[]>([]);
  const [busy, setBusy] = useState(false);
  const [state, setState] = useState<InteractionState>({
    familiarity: 0.1,
    stress: 0.4,
    lastResponse: null,
    lastRationale: "Offer treats patiently to build familiarity before gentle petting.",
    activeClip: null,
    sourceMode: "local_manifest",
  });

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const res = await fetch("/api/v1/mujoco/status");
        if (res.ok) {
          const data = await res.json();
          if (!mounted) return;
          setClips(data.available_clips || []);
          setState((prev) => ({
            ...prev,
            familiarity: data.drives?.familiarity ?? prev.familiarity,
            stress: data.drives?.stress ?? prev.stress,
            sourceMode: "backend",
          }));
          return;
        }
      } catch {
        // Fallback to static exported MuJoCo manifest
      }
      try {
        const res = await fetch("/assets/mujoco_clips/manifest.json");
        if (res.ok) {
          const manifest = await res.json();
          if (mounted) setClips(manifest.clips || []);
        }
      } catch {
        // Ignore if manifest unavailable in test env
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, []);

  const triggerInteraction = async (action: ParentAction) => {
    setBusy(true);
    try {
      const res = await fetch("/api/v1/mujoco/interact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        const data = await res.json();
        setState({
          familiarity: data.drives?.familiarity ?? state.familiarity,
          stress: data.drives?.stress ?? state.stress,
          lastResponse: data.outcome?.hamster_response ?? null,
          lastRationale: data.outcome?.rationale ?? "",
          activeClip: data.clip ?? null,
          sourceMode: "backend",
        });
        setBusy(false);
        return;
      }
    } catch {
      // Offline / frontend-only fallback mirroring ai/behaviour_manager.py
    }

    const treatBonus = action === "offer_treat" ? 0.22 : 0.0;
    const trust = state.familiarity + treatBonus - 0.55 * state.stress;
    let resp: HamsterResponse;
    let nextFam = state.familiarity;
    let nextStress = state.stress;
    let rationale: string;

    if (trust < 0.12) {
      resp = "avoid_and_retreat";
      nextFam += action === "offer_treat" ? 0.18 : 0.05;
      nextStress += action === "offer_treat" ? -0.06 : 0.06;
      rationale = `Low trust (${trust.toFixed(2)}): retreats to hideout instead of forcing petting.`;
    } else if (trust < 0.42) {
      resp = "cautious_sniff";
      nextFam += action === "offer_treat" ? 0.18 : 0.12;
      nextStress -= action === "offer_treat" ? 0.08 : 0.04;
      rationale = `Moderate trust (${trust.toFixed(2)}): cautiously approaches and sniffs.`;
    } else {
      resp = "accept_petting";
      nextFam += 0.1;
      nextStress -= 0.15;
      rationale = `High trust (${trust.toFixed(2)}): approaches willingly and relaxes for gentle petting.`;
    }
    nextFam = Math.max(0, Math.min(1, Number(nextFam.toFixed(3))));
    nextStress = Math.max(0, Math.min(1, Number(nextStress.toFixed(3))));

    const targetSkill = resp === "avoid_and_retreat" ? "retreat_to_hideout" : resp;
    const matched = clips.find((c) => c.skill_id === targetSkill) ?? null;

    setState({
      familiarity: nextFam,
      stress: nextStress,
      lastResponse: resp,
      lastRationale: rationale,
      activeClip: matched,
      sourceMode: "local_manifest",
    });
    setBusy(false);
  };

  return (
    <section
      aria-label="Parent Interaction and MuJoCo ONNX Physics Bridge"
      className="glass-card rounded-2xl p-4 space-y-3"
      data-testid="parent-interaction-panel"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Heart className="h-4 w-4 text-[#FF6B5B]" />
          <h3 className="font-display text-lg text-[#F4EDE0] tracking-wide">
            Parent Taming &amp; MuJoCo ONNX Physics
          </h3>
          <Badge variant="outline" className="text-[11px] border-emerald-400/40 text-emerald-300">
            <Cpu className="h-3 w-3 mr-1" />
            LEARNED ONNX (1M-step Mixed)
          </Badge>
          <Badge variant="outline" className="text-[11px] border-amber-400/40 text-amber-200">
            TAMING: RULE-BASED
          </Badge>
        </div>
        <span className="text-[11px] text-[#F4EDE0]/60 font-mono">
          {state.sourceMode === "backend" ? "Live FastAPI Bridge" : "Local MuJoCo Clip Manifest"} •{" "}
          {clips.length} physics clips
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 items-center">
        {/* Action buttons */}
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="coral"
            size="sm"
            disabled={busy}
            onClick={() => triggerInteraction("offer_treat")}
            className="gap-1.5"
          >
            <Cookie className="h-3.5 w-3.5" />
            Offer Treat
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => triggerInteraction("gentle_pet")}
            className="gap-1.5 border-[#F4EDE0]/25 text-[#F4EDE0] hover:bg-[#F4EDE0]/10"
          >
            <Hand className="h-3.5 w-3.5" />
            Gentle Pet
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => triggerInteraction("call_attention")}
            className="gap-1.5 border-[#F4EDE0]/25 text-[#F4EDE0] hover:bg-[#F4EDE0]/10"
          >
            <Bell className="h-3.5 w-3.5" />
            Call Attention
          </Button>
        </div>

        {/* Familiarity & Stress meters */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-[#F4EDE0]/80">
            <span>Familiarity (Taming)</span>
            <span className="font-mono text-emerald-300">{Math.round(state.familiarity * 100)}%</span>
          </div>
          <div className="h-2 rounded-full bg-[#0B1325]/70 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-teal-300 transition-all duration-300"
              style={{ width: `${Math.round(state.familiarity * 100)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-[#F4EDE0]/80">
            <span>Stress</span>
            <span className="font-mono text-[#FF6B5B]">{Math.round(state.stress * 100)}%</span>
          </div>
          <div className="h-2 rounded-full bg-[#0B1325]/70 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-amber-400 to-[#FF6B5B] transition-all duration-300"
              style={{ width: `${Math.round(state.stress * 100)}%` }}
            />
          </div>
        </div>

        {/* Non-forced response + active MuJoCo clip */}
        <div className="rounded-xl bg-[#0B1325]/60 border border-[#F4EDE0]/15 p-2.5 text-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[#F4EDE0]/65 flex items-center gap-1">
              <Activity className="h-3.5 w-3.5 text-[#FF6B5B]" />
              Hamster Response
            </span>
            {state.lastResponse && (
              <span className="font-mono px-2 py-0.5 rounded-full bg-[#FF6B5B]/20 text-[#FF6B5B] text-[11px]">
                {state.lastResponse}
              </span>
            )}
          </div>
          <p className="text-[#F4EDE0]/85 leading-snug">{state.lastRationale}</p>
          {state.activeClip && (
            <div className="pt-1 border-t border-[#F4EDE0]/10 flex items-center justify-between text-[11px] text-emerald-300 font-mono">
              <span className="inline-flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" />
                {state.activeClip.skill_id} ({state.activeClip.duration_s}s, {state.activeClip.displacement_m}m)
              </span>
              <span>{state.activeClip.origin}</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
