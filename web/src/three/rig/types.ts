import type * as THREE from "three";

export type QualityPreset = "low" | "medium" | "high" | "ultra";

export interface QualitySettings {
  preset: QualityPreset;
  pixelRatioMax: number;
  shadowMapSize: number;
  furShellCount: number;
  enableFins: boolean;
  enableAO: boolean;
  enableDoF: boolean;
  dustMoteCount: number;
  lodBias: number; // multiplier on LOD switch distances
}

export interface HamsterValidationReport {
  valid: boolean;
  foundBones: string[];
  missingBones: string[];
  foundBlendShapes: string[];
  missingBlendShapes: string[];
  foundLods: string[];
  missingLods: string[];
}

export interface LoadedHamsterAsset {
  root: THREE.Group;
  bones: Map<string, THREE.Bone>;
  morphMeshes: THREE.Mesh[];
  lodMeshes: {
    LOD0: THREE.Mesh | null;
    LOD1: THREE.Mesh | null;
    LOD2: THREE.Mesh | null;
  };
  validation: HamsterValidationReport;
}

export interface FootContacts {
  fl: boolean;
  fr: boolean;
  bl: boolean;
  br: boolean;
}

export interface HamsterPostureState {
  /** 0..1 bipedal rearing up on hind legs ("periscope") */
  rearAmount: number;
  /** 0..1 crouching low (eating, sniffing floor, startled freeze) */
  crouchAmount: number;
  /** 0..1 curled-up sleeping/resting posture */
  curlAmount: number;
  /** Head & neck look pitch (radians, negative = look up, positive = look down) */
  headPitch: number;
  /** Head & neck look yaw (radians, positive = look left, negative = look right) */
  headYaw: number;
  /** Head tilt roll (radians, curious head-tilt) */
  headRoll: number;
  /** 0..1 face-washing grooming blend */
  groomAmount: number;
  /** Continuous phase (radians) for rapid paw-scrubbing during grooming */
  groomPhase: number;
  /** 0..1 bedding digging/scratching blend */
  digAmount: number;
  /** Continuous phase (radians) for rapid alternating front-paw digging */
  digPhase: number;
  /** 0..1 jaw/mouth chewing/nibbling intensity */
  chewAmount: number;
  /** Continuous phase (radians) for rapid jaw/chew cycles */
  chewPhase: number;
}

export interface PhysicsPoseInput {
  rootPosition: [number, number, number];
  rootQuaternion: [number, number, number, number];
  velocity: [number, number, number];
  angularVelocity: [number, number, number];
  footContacts: FootContacts;
  gaitPhase: number; // radians
  posture?: HamsterPostureState;
}

export interface ProceduralLayerConfig {
  breathing: { enabled: boolean; rateHz: number; amplitude: number };
  whiskerTwitch: { enabled: boolean; sniffHz: number; amplitude: number };
  earOrientation: { enabled: boolean; alertLevel: number; flickRate: number };
  blinkAndGaze: { enabled: boolean; blinkIntervalSec: number; sleepiness: number; gazeAmplitude: number };
  tail: { enabled: boolean; wagAmplitude: number };
  springJiggle: { enabled: boolean; stiffness: number; damping: number; amplitude: number };
  cheekPouch: { enabled: boolean; leftFill: number; rightFill: number };
  mouth?: { enabled: boolean; chewAmount: number; chewPhase: number; mouthOpen: number };
}

export const DEFAULT_PROCEDURAL_CONFIG: ProceduralLayerConfig = {
  breathing: { enabled: true, rateHz: 1.4, amplitude: 0.75 },
  whiskerTwitch: { enabled: true, sniffHz: 6.5, amplitude: 0.7 },
  earOrientation: { enabled: true, alertLevel: 0.65, flickRate: 0.4 },
  blinkAndGaze: { enabled: true, blinkIntervalSec: 3.4, sleepiness: 0.1, gazeAmplitude: 0.5 },
  tail: { enabled: true, wagAmplitude: 0.45 },
  springJiggle: { enabled: true, stiffness: 120, damping: 14, amplitude: 0.8 },
  cheekPouch: { enabled: true, leftFill: 0.0, rightFill: 0.0 },
  mouth: { enabled: true, chewAmount: 0.0, chewPhase: 0.0, mouthOpen: 0.0 },
};

