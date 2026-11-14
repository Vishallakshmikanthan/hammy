import type { QualityPreset, QualitySettings } from "./types";

export const QUALITY_PRESETS: Record<QualityPreset, QualitySettings> = {
  low: {
    preset: "low",
    pixelRatioMax: 1.0,
    shadowMapSize: 512,
    furShellCount: 6,
    enableFins: false,
    enableAO: false,
    enableDoF: false,
    dustMoteCount: 30,
    lodBias: 0.6,
  },
  medium: {
    preset: "medium",
    pixelRatioMax: 1.5,
    shadowMapSize: 1024,
    furShellCount: 12,
    enableFins: true,
    enableAO: false,
    enableDoF: false,
    dustMoteCount: 80,
    lodBias: 0.85,
  },
  high: {
    preset: "high",
    pixelRatioMax: 2.0,
    shadowMapSize: 2048,
    furShellCount: 20,
    enableFins: true,
    enableAO: true,
    enableDoF: true,
    dustMoteCount: 160,
    lodBias: 1.0,
  },
  ultra: {
    preset: "ultra",
    pixelRatioMax: 2.0,
    shadowMapSize: 4096,
    furShellCount: 32,
    enableFins: true,
    enableAO: true,
    enableDoF: true,
    dustMoteCount: 280,
    lodBias: 1.35,
  },
};

export type LodLevel = "LOD0" | "LOD1" | "LOD2";

export function selectLodByDistance(cameraDistanceMeters: number, preset: QualityPreset): LodLevel {
  const bias = QUALITY_PRESETS[preset].lodBias;
  if (cameraDistanceMeters < 0.45 * bias) return "LOD0";
  if (cameraDistanceMeters < 1.15 * bias) return "LOD1";
  return "LOD2";
}

export function applyLodVisibility(
  lodMeshes: { LOD0: { visible: boolean } | null; LOD1: { visible: boolean } | null; LOD2: { visible: boolean } | null },
  activeLod: LodLevel
): void {
  if (lodMeshes.LOD0) lodMeshes.LOD0.visible = activeLod === "LOD0";
  if (lodMeshes.LOD1) lodMeshes.LOD1.visible = activeLod === "LOD1";
  if (lodMeshes.LOD2) lodMeshes.LOD2.visible = activeLod === "LOD2";
}

