import React from "react";
import { HeartPulse, Moon, Sun } from "lucide-react";
import { DriveVector } from "../types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface DrivesPanelProps {
  drives: DriveVector | null;
}

interface DriveBarConfig {
  key: keyof Omit<DriveVector, "circadian_phase">;
  label: string;
  icon: string;
  invertedWarning?: boolean;
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
      <Card data-testid="drives-panel">
        <CardHeader>
          <CardTitle className="font-display text-2xl font-normal">Homeostatic Drives &amp; Needs</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-[#F4EDE0]/65">No drive data available.</p>
        </CardContent>
      </Card>
    );
  }

  const phaseRad = drives.circadian_phase ?? 0;
  const phaseHours = ((phaseRad / (2 * Math.PI)) * 24) % 24;
  const isHamsterNight = phaseHours >= 18 || phaseHours < 6;

  const getBarColorClass = (value: number, inverted?: boolean) => {
    if (inverted) {
      if (value < 0.2) return "from-[#FF6B5B] to-rose-600";
      if (value < 0.4) return "from-amber-400 to-[#FF6B5B]";
      return "from-emerald-400 to-teal-300";
    } else {
      if (value >= 0.8) return "from-[#FF6B5B] to-rose-600";
      if (value >= 0.6) return "from-amber-400 to-[#FF6B5B]";
      return "from-[#F4EDE0] to-[#FF6B5B]";
    }
  };

  return (
    <Card className="relative overflow-hidden" data-testid="drives-panel">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-12 -bottom-12 h-40 w-40 rounded-full bg-[#FF6B5B]/15 blur-2xl"
      />
      <CardHeader className="pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#FF6B5B] mb-1">
            <HeartPulse className="h-3.5 w-3.5" />
            Internal Physiology
          </div>
          <CardTitle className="font-display text-2xl font-normal tracking-wide text-[#F4EDE0]">
            Homeostatic Drives &amp; Needs
          </CardTitle>
          <CardDescription>6-axis internal drive vector governing utility selection</CardDescription>
        </div>

        <Badge variant="cream" className="px-3 py-1 text-xs" data-testid="circadian-badge">
          {isHamsterNight ? (
            <Moon className="h-3.5 w-3.5 text-[#FF6B5B]" />
          ) : (
            <Sun className="h-3.5 w-3.5 text-[#FF6B5B]" />
          )}
          Circadian: {isHamsterNight ? "🌙 Active (Night)" : "☀️ Rest (Day)"} ({phaseHours.toFixed(1)}h)
        </Badge>
      </CardHeader>

      <CardContent className="space-y-5">
        <div className="space-y-3.5">
          {DRIVE_CONFIGS.map(({ key, label, icon, invertedWarning }) => {
            const val = drives[key] ?? 0;
            const percentage = Math.min(Math.max(val * 100, 0), 100);
            const gradientClass = getBarColorClass(val, invertedWarning);

            return (
              <div key={key} className="space-y-1.5" data-testid={`drive-${key}`}>
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-2 font-medium text-[#F4EDE0]">
                    <span>{icon}</span> {label}
                  </span>
                  <span
                    className="font-mono text-xs font-semibold text-[#F4EDE0]/85"
                    data-testid={`drive-${key}-val`}
                  >
                    {percentage.toFixed(1)}%
                  </span>
                </div>

                <div
                  className="relative h-2.5 w-full overflow-hidden rounded-full bg-[#0B1325]/80 border border-[#F4EDE0]/15"
                  role="progressbar"
                  aria-valuenow={percentage}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className={`h-full rounded-full bg-gradient-to-r ${gradientClass} transition-all duration-300`}
                    style={{ width: `${percentage}%` }}
                  />
                  <div
                    className="absolute top-0 bottom-0 w-[1px] bg-[#F4EDE0]/35"
                    style={{ left: "60%" }}
                    title="Homeostatic Threshold"
                  />
                </div>
              </div>
            );
          })}
        </div>

        <div
          className="rounded-2xl border border-[#F4EDE0]/15 bg-[#0B1325]/60 p-3.5 backdrop-blur-md"
          data-testid="circadian-meter"
        >
          <div className="flex items-center justify-between text-xs text-[#F4EDE0]/75 mb-2">
            <span className="font-medium">Circadian Phase Angle</span>
            <span className="font-mono text-[#FF6B5B]">
              {phaseRad.toFixed(3)} rad ({phaseHours.toFixed(1)} h)
            </span>
          </div>
          <div className="relative h-7 rounded-xl overflow-hidden border border-[#F4EDE0]/15 bg-gradient-to-r from-[#0B1325] via-[#FF6B5B]/65 to-[#0B1325]">
            <div
              className="absolute top-0 bottom-0 w-1 bg-[#F4EDE0] shadow-[0_0_10px_#F4EDE0] -translate-x-1/2"
              style={{ left: `${(phaseHours / 24) * 100}%` }}
              title={`Phase: ${phaseHours.toFixed(1)}h`}
            />
            <div className="relative z-10 flex h-full items-center justify-between px-3 text-[10px] font-bold uppercase tracking-widest text-[#F4EDE0]/90">
              <span>Night (Active)</span>
              <span>Day (Sleeping)</span>
              <span>Night</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
