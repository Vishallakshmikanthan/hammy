import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { HamsterValidationReport, LoadedHamsterAsset } from "./types";

export const REQUIRED_BONES = [
  "root",
  "pelvis",
  "spine_1",
  "spine_2",
  "spine_3",
  "spine_4",
  "neck",
  "head",
  "jaw",
  "ear_L_1",
  "ear_R_1",
  "eye_L",
  "eye_R",
  "paw_fl",
  "paw_fr",
  "paw_bl",
  "paw_br",
  "tail_1",
] as const;

export const REQUIRED_BLEND_SHAPES = [
  "cheek_pouch_left",
  "cheek_pouch_right",
  "blink",
  "squint",
  "mouth_open",
  "chew",
  "nose_wrinkle",
  "ear_fold",
  "whisker_forward",
  "breath_in",
] as const;

export const REQUIRED_LODS = ["ham_body_LOD0", "ham_body_LOD1", "ham_body_LOD2"] as const;

export class HamsterAssetError extends Error {
  public readonly report?: HamsterValidationReport;

  constructor(message: string, report?: HamsterValidationReport) {
    super(message);
    this.name = "HamsterAssetError";
    this.report = report;
  }
}

export function validateHamsterScene(root: THREE.Object3D): {
  report: HamsterValidationReport;
  bones: Map<string, THREE.Bone>;
  morphMeshes: THREE.Mesh[];
  lodMeshes: { LOD0: THREE.Mesh | null; LOD1: THREE.Mesh | null; LOD2: THREE.Mesh | null };
} {
  const bones = new Map<string, THREE.Bone>();
  const morphNames = new Set<string>();
  const morphMeshes: THREE.Mesh[] = [];
  const meshNames = new Set<string>();
  const lodMeshes: { LOD0: THREE.Mesh | null; LOD1: THREE.Mesh | null; LOD2: THREE.Mesh | null } = {
    LOD0: null,
    LOD1: null,
    LOD2: null,
  };

  root.traverse((obj) => {
    if ((obj as THREE.Bone).isBone) {
      bones.set(obj.name, obj as THREE.Bone);
    }
    if ((obj as THREE.Mesh).isMesh) {
      const mesh = obj as THREE.Mesh;
      meshNames.add(mesh.name);
      if (mesh.name.includes("ham_body_LOD0")) lodMeshes.LOD0 = mesh;
      if (mesh.name.includes("ham_body_LOD1")) lodMeshes.LOD1 = mesh;
      if (mesh.name.includes("ham_body_LOD2")) lodMeshes.LOD2 = mesh;

      if (mesh.morphTargetDictionary) {
        morphMeshes.push(mesh);
        for (const key of Object.keys(mesh.morphTargetDictionary)) {
          morphNames.add(key);
        }
      }
    }
  });

  const foundBones = REQUIRED_BONES.filter((b) => bones.has(b));
  const missingBones = REQUIRED_BONES.filter((b) => !bones.has(b));
  const foundBlendShapes = REQUIRED_BLEND_SHAPES.filter((s) => morphNames.has(s));
  const missingBlendShapes = REQUIRED_BLEND_SHAPES.filter((s) => !morphNames.has(s));
  const foundLods = REQUIRED_LODS.filter((l) => Array.from(meshNames).some((n) => n.includes(l)));
  const missingLods = REQUIRED_LODS.filter((l) => !Array.from(meshNames).some((n) => n.includes(l)));

  const valid = missingBones.length === 0 && missingBlendShapes.length === 0 && missingLods.length === 0;

  return {
    report: {
      valid,
      foundBones: [...foundBones],
      missingBones: [...missingBones],
      foundBlendShapes: [...foundBlendShapes],
      missingBlendShapes: [...missingBlendShapes],
      foundLods: [...foundLods],
      missingLods: [...missingLods],
    },
    bones,
    morphMeshes,
    lodMeshes,
  };
}

export async function loadHamsterAsset(
  url = "/assets/hamster.glb",
  options: { strict?: boolean } = { strict: true }
): Promise<LoadedHamsterAsset> {
  const loader = new GLTFLoader();
  let gltf;
  try {
    gltf = await loader.loadAsync(url);
  } catch (err) {
    throw new HamsterAssetError(
      `Failed to load hamster asset from "${url}": ${err instanceof Error ? err.message : String(err)}`
    );
  }

  const root = gltf.scene;
  root.traverse((obj) => {
    if ((obj as THREE.Mesh).isMesh) {
      obj.castShadow = true;
      obj.receiveShadow = true;
    }
  });

  const { report, bones, morphMeshes, lodMeshes } = validateHamsterScene(root);
  if (options.strict && !report.valid) {
    const parts: string[] = [];
    if (report.missingBones.length) parts.push(`missing bones: [${report.missingBones.join(", ")}]`);
    if (report.missingBlendShapes.length) parts.push(`missing blend shapes: [${report.missingBlendShapes.join(", ")}]`);
    if (report.missingLods.length) parts.push(`missing LODs: [${report.missingLods.join(", ")}]`);
    throw new HamsterAssetError(`Invalid hamster asset "${url}" — ${parts.join("; ")}`, report);
  }

  return {
    root,
    bones,
    morphMeshes,
    lodMeshes,
    validation: report,
  };
}

