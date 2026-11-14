import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  REQUIRED_BLEND_SHAPES,
  REQUIRED_BONES,
  REQUIRED_LODS,
  validateHamsterScene,
} from "../rig/hamsterAssetLoader";
import { applyLodVisibility, selectLodByDistance } from "../rig/lodAndQuality";
import { PoseApplicationLayer } from "../rig/poseApplication";
import { ProceduralRigLayer } from "../rig/proceduralRig";
import { DEFAULT_PROCEDURAL_CONFIG, type LoadedHamsterAsset } from "../rig/types";
import { BeddingDeformer } from "../habitat/beddingDeformer";
import { computeDayNightLighting } from "../habitat/environmentEffects";
import { HamsterBehaviorController, type HabitatPropAnchors } from "../habitat/hamsterBehavior";
import type { PetState } from "../../types";

function makeMockHamsterRoot(opts?: { omitBone?: string; omitMorph?: string; omitLod?: string }): THREE.Group {
  const root = new THREE.Group();
  for (const bname of REQUIRED_BONES) {
    if (bname === opts?.omitBone) continue;
    const bone = new THREE.Bone();
    bone.name = bname;
    root.add(bone);
  }
  // Add extra rig bones used by pose/procedural layers
  for (const extra of [
    "shoulder_L",
    "shoulder_R",
    "upper_arm_L",
    "upper_arm_R",
    "forearm_L",
    "forearm_R",
    "thigh_L",
    "thigh_R",
    "shin_L",
    "shin_R",
    "whisker_L",
    "whisker_R",
    "jiggle_cheek_L",
    "jiggle_flank_L",
    "jiggle_scruff",
  ]) {
    const bone = new THREE.Bone();
    bone.name = extra;
    root.add(bone);
  }

  const dict: Record<string, number> = {};
  const influences: number[] = [];
  let idx = 0;
  for (const sname of REQUIRED_BLEND_SHAPES) {
    if (sname === opts?.omitMorph) continue;
    dict[sname] = idx++;
    influences.push(0);
  }

  for (const lodName of REQUIRED_LODS) {
    if (lodName === opts?.omitLod) continue;
    const geo = new THREE.BoxGeometry(0.1, 0.1, 0.1);
    const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial());
    mesh.name = lodName;
    mesh.morphTargetDictionary = { ...dict };
    mesh.morphTargetInfluences = [...influences];
    root.add(mesh);
  }

  return root;
}

describe("P3.2 Hamster Asset Loader & Validation", () => {
  it("validates a complete hamster scene with all required bones, blend shapes, and LODs", () => {
    const root = makeMockHamsterRoot();
    const { report } = validateHamsterScene(root);
    expect(report.valid).toBe(true);
    expect(report.missingBones).toEqual([]);
    expect(report.missingBlendShapes).toEqual([]);
    expect(report.missingLods).toEqual([]);
  });

  it("reports missing bones, blend shapes, and LODs explicitly", () => {
    const root = makeMockHamsterRoot({
      omitBone: "jaw",
      omitMorph: "cheek_pouch_left",
      omitLod: "ham_body_LOD2",
    });
    const { report } = validateHamsterScene(root);
    expect(report.valid).toBe(false);
    expect(report.missingBones).toContain("jaw");
    expect(report.missingBlendShapes).toContain("cheek_pouch_left");
    expect(report.missingLods).toContain("ham_body_LOD2");
  });
});

describe("P3.2 Pose Application & Procedural Rig", () => {
  it("applies physics pose and toggles procedural layers cleanly", () => {
    const root = makeMockHamsterRoot();
    const { report, bones, morphMeshes, lodMeshes } = validateHamsterScene(root);
    const asset: LoadedHamsterAsset = { root, bones, morphMeshes, lodMeshes, validation: report };

    const poseLayer = new PoseApplicationLayer(asset);
    poseLayer.applyPhysicsPose({
      rootPosition: [0.1, 0.02, -0.05],
      rootQuaternion: [0, 0, 0, 1],
      velocity: [0, 0, 0.2],
      angularVelocity: [0, 0.1, 0],
      footContacts: { fl: true, fr: false, bl: false, br: true },
      gaitPhase: 1.2,
    });
    expect(root.position.x).toBeCloseTo(0.1);

    const procLayer = new ProceduralRigLayer(asset);
    const cfg = structuredClone(DEFAULT_PROCEDURAL_CONFIG);
    cfg.breathing.enabled = false;
    cfg.cheekPouch.leftFill = 0.85;
    cfg.cheekPouch.rightFill = 0.4;
    procLayer.update(0.016, cfg);

    const lod0 = lodMeshes.LOD0!;
    const idxBreath = lod0.morphTargetDictionary!["breath_in"];
    const idxLeft = lod0.morphTargetDictionary!["cheek_pouch_left"];
    const idxRight = lod0.morphTargetDictionary!["cheek_pouch_right"];
    expect(lod0.morphTargetInfluences![idxBreath]).toBe(0);
    expect(lod0.morphTargetInfluences![idxLeft]).toBeCloseTo(0.85);
    expect(lod0.morphTargetInfluences![idxRight]).toBeCloseTo(0.4);
  });

  it("selects LODs by camera distance and quality preset", () => {
    expect(selectLodByDistance(0.2, "high")).toBe("LOD0");
    expect(selectLodByDistance(0.7, "high")).toBe("LOD1");
    expect(selectLodByDistance(1.8, "high")).toBe("LOD2");
    // Low preset switches to LOD1 sooner
    expect(selectLodByDistance(0.35, "low")).toBe("LOD1");

    const m0 = { visible: true };
    const m1 = { visible: true };
    const m2 = { visible: true };
    applyLodVisibility({ LOD0: m0, LOD1: m1, LOD2: m2 }, "LOD1");
    expect(m0.visible).toBe(false);
    expect(m1.visible).toBe(true);
    expect(m2.visible).toBe(false);
  });
});

describe("P3.3 Habitat Environment & Bedding Deformation", () => {
  it("deforms bedding vertices near paw positions", () => {
    const plane = new THREE.PlaneGeometry(0.4, 0.4, 16, 16);
    plane.rotateX(-Math.PI / 2);
    const mesh = new THREE.Mesh(plane, new THREE.MeshStandardMaterial());
    const deformer = new BeddingDeformer(mesh);

    const posAttr = mesh.geometry.getAttribute("position") as THREE.BufferAttribute;
    const beforeCenterY = posAttr.getY(Math.floor(posAttr.count / 2));

    deformer.deformAtPaws([new THREE.Vector3(0, 0, 0)], 0.05, 0.01);
    const afterCenterY = posAttr.getY(Math.floor(posAttr.count / 2));
    expect(afterCenterY).toBeLessThan(beforeCenterY);
  });

  it("computes realistic day/night lighting from server hour", () => {
    const noon = computeDayNightLighting(13);
    const midnight = computeDayNightLighting(0);
    expect(noon.phaseLabel).toBe("day");
    expect(midnight.phaseLabel).toBe("night");
    expect(noon.keyIntensity).toBeGreaterThan(midnight.keyIntensity);
    expect(midnight.nightLampIntensity).toBeGreaterThan(noon.nightLampIntensity);
  });
});

function makeAnchors(): HabitatPropAnchors {
  return {
    beddingY: 0.165,
    bowlPos: new THREE.Vector3(0.28, 0.15, 0.11),
    spoutPos: new THREE.Vector3(0.433, 0.183, 0.02),
    wheelPos: new THREE.Vector3(-0.30, 0.315, -0.13),
    hideoutPos: new THREE.Vector3(0.28, 0.238, -0.11),
    tunnelPos: new THREE.Vector3(-0.04, 0.178, 0.05),
    chewPos: new THREE.Vector3(0.17, 0.172, 0.05),
  };
}

function makePetState(overrides: Partial<PetState> = {}): PetState {
  return {
    pet_id: "pet_hammy_01",
    version: 1,
    schema_version: "1.0.0",
    environment_version: "habitat_v1",
    sim_time_sec: 100,
    simulated_age_days: 30,
    real_time_scale: 1,
    last_simulated_at: null,
    is_paused: false,
    drives: {
      hunger: 0.3,
      thirst: 0.2,
      energy: 0.75,
      comfort: 0.7,
      stress: 0.15,
      curiosity: 0.7,
      circadian_phase: 0.2,
    },
    position_xyz: [0.145, 0.032, 0.165],
    yaw_rad: 0,
    velocity_xy: [0, 0],
    angular_velocity_z: 0,
    inside_hideout: false,
    inside_tunnel: false,
    on_wheel: false,
    cheek_pouch_fill: 0,
    active_skill: null,
    updated_at: null,
    ...overrides,
  };
}

describe("Real-Life Hamster Behavior & Articulation", () => {
  it("applies rearing, grooming, and chewing postures across spine, limbs, jaw, and morphs", () => {
    const root = makeMockHamsterRoot();
    const { report, bones, morphMeshes, lodMeshes } = validateHamsterScene(root);
    const asset: LoadedHamsterAsset = { root, bones, morphMeshes, lodMeshes, validation: report };

    const poseLayer = new PoseApplicationLayer(asset);
    poseLayer.applyPhysicsPose({
      rootPosition: [0, 0.165, 0],
      rootQuaternion: [0, 0, 0, 1],
      velocity: [0, 0, 0],
      angularVelocity: [0, 0, 0],
      footContacts: { fl: false, fr: false, bl: true, br: true },
      gaitPhase: 0,
      posture: {
        rearAmount: 0.9,
        crouchAmount: 0,
        curlAmount: 0,
        headPitch: -0.15,
        headYaw: 0.35,
        headRoll: 0.1,
        groomAmount: 0.85,
        groomPhase: 1.4,
        digAmount: 0,
        digPhase: 0,
        chewAmount: 0.8,
        chewPhase: Math.PI / 2,
      },
    });

    expect(bones.get("spine_1")!.rotation.x).not.toBe(0);
    expect(bones.get("forearm_L")!.rotation.x).not.toBe(0);
    expect(bones.get("jaw")!.rotation.x).not.toBe(0);

    const procLayer = new ProceduralRigLayer(asset);
    const cfg = structuredClone(DEFAULT_PROCEDURAL_CONFIG);
    cfg.mouth = { enabled: true, chewAmount: 0.85, chewPhase: Math.PI / 2, mouthOpen: 0.1 };
    procLayer.update(0.016, cfg);

    const lod0 = lodMeshes.LOD0!;
    expect(lod0.morphTargetInfluences![lod0.morphTargetDictionary!["chew"]]).toBeGreaterThan(0.5);
    expect(lod0.morphTargetInfluences![lod0.morphTargetDictionary!["mouth_open"]]).toBeGreaterThan(0.3);
  });

  it("exhibits diverse natural behaviors including foraging, wheel sprinting/coasting, and curled rest", () => {
    const anchors = makeAnchors();
    const controller = new HamsterBehaviorController();

    // 1. Hideout rest -> curled up posture
    const hideoutState = makePetState({
      inside_hideout: true,
      position_xyz: [anchors.hideoutPos.x, -anchors.hideoutPos.z, anchors.hideoutPos.y],
    });
    let step = controller.update(0.05, hideoutState, null, anchors);
    for (let i = 0; i < 40; i++) {
      step = controller.update(0.05, hideoutState, null, anchors);
    }
    expect(step.activityLabel).toBe("Curled Up in Hideout");
    expect(step.pose.posture!.curlAmount).toBeGreaterThan(0.6);

    // 2. Wheel sprint & coasting pause
    const wheelState = makePetState({
      on_wheel: true,
      position_xyz: [anchors.wheelPos.x, -anchors.wheelPos.z, anchors.wheelPos.y],
    });
    const wheelLabels = new Set<string>();
    for (let i = 0; i < 160; i++) {
      step = controller.update(0.05, wheelState, null, anchors);
      wheelLabels.add(step.activityLabel);
    }
    expect(wheelLabels.has("Sprinting on Wheel")).toBe(true);
    expect(wheelLabels.has("Catching Breath on Wheel")).toBe(true);

    // 3. Cheek pouch fill + exploration ethogram diversity
    const exploreState = makePetState({
      cheek_pouch_fill: 0.75,
      drives: {
        hunger: 0.2,
        thirst: 0.2,
        energy: 0.85,
        comfort: 0.7,
        stress: 0.15,
        curiosity: 0.85,
        circadian_phase: 0.1,
      },
    });
    const labels = new Set<string>();
    for (let i = 0; i < 400; i++) {
      step = controller.update(0.05, exploreState, null, anchors);
      labels.add(step.activityLabel);
    }
    expect(step.proceduralConfig.cheekPouch.leftFill).toBeGreaterThan(0.5);
    expect(labels.size).toBeGreaterThanOrEqual(3);
  });

  it("never overlaps tunnel pipes and autonomously visits wheel, water, and hideout when offline", () => {
    // Exact rotated world Box3 coordinates from cage.glb (with upright wheel drum)
    const tunnelBoxes = [
      new THREE.Box3(new THREE.Vector3(-0.071, 0.138, -0.097), new THREE.Vector3(0.076, 0.218, 0.05)),
      new THREE.Box3(new THREE.Vector3(-0.001, 0.139, 0.019), new THREE.Vector3(0.112, 0.219, 0.175)),
      new THREE.Box3(new THREE.Vector3(-0.187, 0.155, -0.066), new THREE.Vector3(-0.05, 0.235, 0.042)),
    ];
    const anchors: HabitatPropAnchors = {
      ...makeAnchors(),
      tunnelBoxes,
      tunnelBox: tunnelBoxes[0],
      hideoutBox: new THREE.Box3(new THREE.Vector3(0.185, 0.186, -0.195), new THREE.Vector3(0.375, 0.291, -0.025)),
      wheelBox: new THREE.Box3(new THREE.Vector3(-0.44, 0.175, -0.175), new THREE.Vector3(-0.16, 0.455, -0.085)),
      wheelTrackY: 0.187,
    };

    const controller = new HamsterBehaviorController();
    const visited = new Set<string>();
    let minX = Infinity;
    let maxX = -Infinity;
    let minZ = Infinity;
    let maxZ = -Infinity;

    for (let i = 0; i < 2400; i++) {
      const step = controller.update(0.05, null, null, anchors);
      visited.add(step.activityLabel);
      const [x, , z] = step.pose.rootPosition;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minZ = Math.min(minZ, z);
      maxZ = Math.max(maxZ, z);
      for (let bIdx = 0; bIdx < tunnelBoxes.length; bIdx++) {
        const box = tunnelBoxes[bIdx];
        const insideX = x > box.min.x - 0.032 && x < box.max.x + 0.032;
        const insideZ = z > box.min.z - 0.032 && z < box.max.z + 0.032;
        expect(insideX && insideZ, `step=${i} label=${step.activityLabel} x=${x.toFixed(4)} z=${z.toFixed(4)} box=${bIdx}`).toBe(false);
      }
    }

    expect(minX).toBeLessThan(-0.25);
    expect(maxX).toBeGreaterThan(0.30);
    expect(minZ).toBeLessThan(-0.10);
    expect(maxZ).toBeGreaterThan(0.10);
    expect(visited.has("Sprinting on Wheel"), `visited: ${[...visited].join(", ")}`).toBe(true);
    expect(visited.has("Drinking Water"), `visited: ${[...visited].join(", ")}`).toBe(true);
    expect(visited.has("Curled Up in Hideout"), `visited: ${[...visited].join(", ")}`).toBe(true);
  });
});

