export type FurTechnique = "shells" | "shells-fins" | "webgpu-strands";

export interface FurParams {
  technique: FurTechnique;
  shellCount: number;
  hairLength: number; // meters, e.g. 0.012
  density: number; // strand grid density factor
  clumping: number; // 0..1
  gravityDroop: number; // 0..1
  windStrength: number; // 0..1 (off by default = 0)
  rimLightStrength: number; // 0..2
}

export const DEFAULT_FUR_PARAMS: FurParams = {
  technique: "shells-fins",
  shellCount: 24,
  hairLength: 0.012,
  density: 180,
  clumping: 0.65,
  gravityDroop: 0.35,
  windStrength: 0.0,
  rimLightStrength: 0.85,
};

export interface FurBenchmarkResult {
  technique: FurTechnique;
  supported: boolean;
  avgFps: number;
  avgFrameTimeMs: number;
  p95FrameTimeMs: number;
  drawCalls: number;
  triangles: number;
  shellCount: number;
  notes?: string;
}

