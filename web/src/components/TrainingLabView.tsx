import React, { useEffect, useState } from "react";
import { FlaskConical, Sparkles } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface MetricSummary {
  mean: number;
  ci95: number;
}

interface ConditionResult {
  memory_on: boolean;
  curiosity_on: boolean;
  summary: {
    homeostasis_time_in_range: MetricSummary;
    behavioural_diversity: MetricSummary;
    routine_formation: MetricSummary;
    adaptation_hours: MetricSummary;
  };
}

interface AblationReportData {
  seeds: number[];
  conditions: Record<string, ConditionResult>;
}

const BEHAVIOURS_TABLE = [
  { name: "cheek_stuffing", label: "scripted-with-learned-selection", drives: "hunger -, comfort +", visual: "cheek_pouch_left/right, mouth_open" },
  { name: "hind_leg_standing", label: "scripted-with-learned-selection", drives: "curiosity -, stress -", visual: "whisker_forward, nose_wrinkle, earOrientation" },
  { name: "grooming", label: "scripted-with-learned-selection", drives: "stress -, comfort +", visual: "squint, blink, springJiggle" },
  { name: "digging", label: "scripted-with-learned-selection", drives: "curiosity -, comfort +", visual: "BeddingDeformer 4-paw scoops, nose_wrinkle" },
  { name: "nesting", label: "scripted-with-learned-selection", drives: "comfort +, energy +", visual: "ear_fold, squint, breath_in" },
];

export const TrainingLabView: React.FC = () => {
  const [data, setData] = useState<AblationReportData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/p7_1_ablation.json")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: AblationReportData) => setData(json))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  return (
    <div className="max-w-[1600px] mx-auto w-full px-4 sm:px-6 py-6 space-y-6" data-testid="training-lab-view">
      <Card>
        <CardHeader>
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#FF6B5B] mb-1">
              <FlaskConical className="h-3.5 w-3.5" />
              Empirical Evaluation Suite
            </div>
            <CardTitle className="font-display text-3xl font-normal text-[#F4EDE0]">
              P7.1 Training Lab — 30-Day Autonomy &amp; RND Curiosity Ablation
            </CardTitle>
            {data && (
              <CardDescription className="mt-1">
                Seeds: [{data.seeds.join(", ")}] • 30 simulated days per run • Habitat rearrangement at Day 15
              </CardDescription>
            )}
          </div>
          <Badge variant="coralSolid">Stored Experiment Data Only</Badge>
        </CardHeader>
        <CardContent>
          {error && <div className="error-banner relative bottom-0 left-0 right-0">Failed to load ablation data: {error}</div>}
          {!data && !error && <p className="text-xs text-[#F4EDE0]/65">Loading stored ablation results...</p>}
          {data && (
            <div className="rounded-2xl border border-[#F4EDE0]/15 bg-[#0B1325]/50 overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Condition</TableHead>
                    <TableHead>Homeostasis Time-in-Range</TableHead>
                    <TableHead>Behavioural Diversity</TableHead>
                    <TableHead>Routine Formation</TableHead>
                    <TableHead>Adaptation (h)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(data.conditions).map(([label, c]) => (
                    <TableRow key={label}>
                      <TableCell>
                        <code className="text-[#FF6B5B] font-semibold">{label}</code>
                      </TableCell>
                      <TableCell className="font-mono">
                        {c.summary.homeostasis_time_in_range.mean.toFixed(4)} ± {c.summary.homeostasis_time_in_range.ci95.toFixed(4)}
                      </TableCell>
                      <TableCell className="font-mono">
                        {c.summary.behavioural_diversity.mean.toFixed(4)} ± {c.summary.behavioural_diversity.ci95.toFixed(4)}
                      </TableCell>
                      <TableCell className="font-mono">
                        {c.summary.routine_formation.mean.toFixed(4)} ± {c.summary.routine_formation.ci95.toFixed(4)}
                      </TableCell>
                      <TableCell className="font-mono">
                        {c.summary.adaptation_hours.mean.toFixed(2)} ± {c.summary.adaptation_hours.ci95.toFixed(2)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#FF6B5B] mb-1">
              <Sparkles className="h-3.5 w-3.5" />
              Ethogram Mapping
            </div>
            <CardTitle className="font-display text-3xl font-normal text-[#F4EDE0]">
              P6.1 Signature Behaviours &amp; Realism Review
            </CardTitle>
          </div>
          <Badge variant="cream">Honest Labels</Badge>
        </CardHeader>
        <CardContent>
          <div className="rounded-2xl border border-[#F4EDE0]/15 bg-[#0B1325]/50 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Behaviour</TableHead>
                  <TableHead>Implementation Label</TableHead>
                  <TableHead>Drive Effects</TableHead>
                  <TableHead>Visual Rig / Morphs</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {BEHAVIOURS_TABLE.map((b) => (
                  <TableRow key={b.name}>
                    <TableCell>
                      <code className="text-[#F4EDE0] font-semibold">{b.name}</code>
                    </TableCell>
                    <TableCell>
                      <Badge variant="default">{b.label}</Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-[#F4EDE0]/85">{b.drives}</TableCell>
                    <TableCell className="font-mono text-xs text-[#F4EDE0]/70">{b.visual}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
