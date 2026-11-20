import * as THREE from "three";
import type { LoadedHamsterAsset, PhysicsPoseInput } from "../rig/types";

export interface AnatomicalLimbsController {
  update: (pose: PhysicsPoseInput) => void;
  dispose: () => void;
}

interface ArticulatedDigit {
  proximal: THREE.Group;
  distal: THREE.Group;
  basePitch: number;
  splayYaw: number;
}

interface ArticulatedHand {
  side: "L" | "R";
  fingers: ArticulatedDigit[];
}

interface ArticulatedHindFoot {
  side: "L" | "R";
  toes: ArticulatedDigit[];
}

/**
 * Creates a child group on `bone` whose local axes match Hamster Anatomical Space
 * (+X right, +Y up, +Z forward toward snout) when the rig is in rest pose.
 */
function attachAnatomicalMount(bone: THREE.Bone, name: string): THREE.Group {
  const worldQ = new THREE.Quaternion();
  bone.getWorldQuaternion(worldQ);
  const mount = new THREE.Group();
  mount.name = name;
  mount.quaternion.copy(worldQ).invert();
  bone.add(mount);
  return mount;
}

function buildDigit(
  proxLen: number,
  distLen: number,
  radius: number,
  skinMat: THREE.Material,
  clawMat: THREE.Material,
  disposables: Array<{ dispose: () => void }>,
  basePitch: number,
  splayYaw: number
): ArticulatedDigit {
  const proximal = new THREE.Group();
  proximal.rotation.set(basePitch, splayYaw, 0);

  // Proximal phalanx along +Z
  const proxGeo = new THREE.CapsuleGeometry(radius, Math.max(0.0008, proxLen - radius * 1.4), 6, 10);
  proxGeo.rotateX(Math.PI / 2);
  proxGeo.translate(0, 0, proxLen * 0.5);
  disposables.push(proxGeo);
  const proxMesh = new THREE.Mesh(proxGeo, skinMat);
  proxMesh.castShadow = true;
  proxMesh.receiveShadow = true;
  proxMesh.renderOrder = 2;
  proximal.add(proxMesh);

  // Distal phalanx pivoted at knuckle
  const distal = new THREE.Group();
  distal.position.set(0, 0, proxLen * 0.92);
  proximal.add(distal);

  const distR = radius * 0.82;
  const distGeo = new THREE.CapsuleGeometry(distR, Math.max(0.0006, distLen - distR * 1.4), 6, 10);
  distGeo.rotateX(Math.PI / 2);
  distGeo.translate(0, 0, distLen * 0.5);
  disposables.push(distGeo);
  const distMesh = new THREE.Mesh(distGeo, skinMat);
  distMesh.castShadow = true;
  distMesh.receiveShadow = true;
  distMesh.renderOrder = 2;
  distal.add(distMesh);

  // Delicate curved pale-ivory claw at fingertip (matching real Syrian hamster photos)
  const clawLen = radius * 1.55;
  const clawGeo = new THREE.ConeGeometry(distR * 0.52, clawLen, 6);
  clawGeo.rotateX(Math.PI / 2 + 0.35);
  clawGeo.translate(0, -distR * 0.25, distLen + clawLen * 0.35);
  disposables.push(clawGeo);
  const clawMesh = new THREE.Mesh(clawGeo, clawMat);
  clawMesh.renderOrder = 2;
  distal.add(clawMesh);

  return { proximal, distal, basePitch, splayYaw };
}

/**
 * Crafts reference-accurate Syrian hamster forelimbs (furred upper arm, tapered cream wrist,
 * fleshy rosy-pink palm with palmar pads, 4 articulated splayed fingers + thumb nub + ivory claws)
 * and hind legs (furred haunch/thigh, lower ankle, elongated rosy-pink hind foot with 5 splayed toes + claws).
 *
 * Mounted directly on existing HamsterRig bones so `hamster.glb` stays 100% intact and crash-free.
 */
export function buildAnatomicalLimbs(asset: LoadedHamsterAsset): AnatomicalLimbsController {
  const disposables: Array<{ dispose: () => void }> = [];
  const attachedGroups: THREE.Object3D[] = [];
  const hands: ArticulatedHand[] = [];
  const hindFeet: ArticulatedHindFoot[] = [];

  // Reference-matched Syrian hamster materials:
  // - Warm cream-ivory belly/limb fur blending seamlessly with coat
  // - Soft rosy-pink fleshy paws/fingers (`2EV8WK1MPMDC.jpg`, `1S65U6T8TWFB.jpg`)
  // - Translucent pale ivory claws
  const creamFurMat = new THREE.MeshPhysicalMaterial({
    color: "#ead7be",
    roughness: 0.9,
    metalness: 0.0,
    sheen: 0.95,
    sheenRoughness: 0.58,
    sheenColor: new THREE.Color("#fff5e4"),
  });
  const goldenHaunchMat = new THREE.MeshPhysicalMaterial({
    color: "#d49b63",
    roughness: 0.89,
    metalness: 0.0,
    sheen: 0.95,
    sheenRoughness: 0.6,
    sheenColor: new THREE.Color("#ffebd0"),
  });
  const pinkSkinMat = new THREE.MeshPhysicalMaterial({
    color: "#f2b0a6",
    roughness: 0.54,
    metalness: 0.0,
    sheen: 0.45,
    sheenRoughness: 0.45,
    sheenColor: new THREE.Color("#ffdcd4"),
    clearcoat: 0.14,
    clearcoatRoughness: 0.48,
  });
  const padPinkMat = new THREE.MeshPhysicalMaterial({
    color: "#e6968c",
    roughness: 0.46,
    metalness: 0.0,
    clearcoat: 0.2,
    clearcoatRoughness: 0.4,
  });
  const clawMat = new THREE.MeshPhysicalMaterial({
    color: "#f7efe4",
    roughness: 0.28,
    metalness: 0.0,
    clearcoat: 0.55,
  });
  disposables.push(creamFurMat, goldenHaunchMat, pinkSkinMat, padPinkMat, clawMat);

  // Temporarily zero root transform to compute exact rest-pose bone-to-anatomical frames
  const savedPos = asset.root.position.clone();
  const savedQuat = asset.root.quaternion.clone();
  asset.root.position.set(0, 0, 0);
  asset.root.quaternion.identity();
  asset.root.updateMatrixWorld(true);

  // 1. Hide the tiny featureless placeholder oval paw meshes (keep in graph so nothing breaks)
  asset.root.traverse((obj) => {
    if ((obj as THREE.Mesh).isMesh && obj.name.includes("ham_paw")) {
      obj.visible = false;
    }
  });

  // 2. Build Left & Right Forelimbs + 4-Fingered Rosy-Pink Hands
  for (const side of ["L", "R"] as const) {
    // In HamsterRig: L is -X, R is +X
    const signX = side === "L" ? -1 : 1;
    const pawBoneName = side === "L" ? "paw_fl" : "paw_fr";

    const upperArmBone = asset.bones.get(`upper_arm_${side}`);
    if (upperArmBone) {
      const mount = attachAnatomicalMount(upperArmBone, `ham_anat_upper_arm_${side}`);
      attachedGroups.push(mount);

      // Plump cream-furred upper arm sleeve emerging smoothly outside the lower chest fur
      const upperGeo = new THREE.CapsuleGeometry(0.0092, 0.012, 8, 14);
      upperGeo.scale(1.0, 1.0, 1.15);
      upperGeo.rotateX(0.32);
      upperGeo.translate(signX * 0.0145, -0.0035, 0.011);
      disposables.push(upperGeo);
      const upperMesh = new THREE.Mesh(upperGeo, creamFurMat);
      upperMesh.castShadow = true;
      upperMesh.receiveShadow = true;
      upperMesh.renderOrder = 2;
      mount.add(upperMesh);
    }

    const forearmBone = asset.bones.get(`forearm_${side}`);
    if (forearmBone) {
      const mount = attachAnatomicalMount(forearmBone, `ham_anat_forearm_${side}`);
      attachedGroups.push(mount);

      // Tapered furred forearm reaching forward-downward from elbow to wrist outside chest fur
      const armGeo = new THREE.CylinderGeometry(0.0072, 0.0049, 0.0195, 14);
      armGeo.rotateX(Math.PI / 2 - 0.30);
      armGeo.translate(signX * 0.0135, -0.0005, 0.016);
      disposables.push(armGeo);
      const armMesh = new THREE.Mesh(armGeo, creamFurMat);
      armMesh.castShadow = true;
      armMesh.receiveShadow = true;
      armMesh.renderOrder = 2;
      mount.add(armMesh);

      // Rounded elbow cap
      const elbowGeo = new THREE.SphereGeometry(0.0072, 12, 10);
      elbowGeo.translate(signX * 0.014, 0.002, 0.0075);
      disposables.push(elbowGeo);
      const elbowMesh = new THREE.Mesh(elbowGeo, creamFurMat);
      elbowMesh.renderOrder = 2;
      mount.add(elbowMesh);
    }

    const pawBone = asset.bones.get(pawBoneName);
    if (pawBone) {
      const mount = attachAnatomicalMount(pawBone, `ham_anat_hand_${side}`);
      // Seat hand cleanly at the tip of the crafted forearm, protruding clearly past chest fur
      mount.position.set(0, 0, 0);
      attachedGroups.push(mount);

      const handRoot = new THREE.Group();
      handRoot.name = `ham_hand_root_${side}`;
      // Local offset in Hamster Anatomical Space: outward & forward so all 4 pink fingers are unmistakably visible
      handRoot.position.set(signX * 0.013, 0.0018, 0.024);
      mount.add(handRoot);

      // Delicate cream-furred wrist cuff transitioning to pink skin
      const cuffGeo = new THREE.SphereGeometry(0.0052, 12, 10);
      cuffGeo.scale(1.05, 0.88, 1.15);
      cuffGeo.translate(0, 0.0005, -0.003);
      disposables.push(cuffGeo);
      const cuffMesh = new THREE.Mesh(cuffGeo, creamFurMat);
      cuffMesh.renderOrder = 2;
      handRoot.add(cuffMesh);

      // Sculpted fleshy rosy-pink palm
      const palmGeo = new THREE.SphereGeometry(0.0054, 14, 12);
      palmGeo.scale(1.06, 0.56, 1.18);
      palmGeo.translate(0, 0, 0.0022);
      disposables.push(palmGeo);
      const palmMesh = new THREE.Mesh(palmGeo, pinkSkinMat);
      palmMesh.castShadow = true;
      palmMesh.receiveShadow = true;
      palmMesh.renderOrder = 2;
      handRoot.add(palmMesh);

      // 3 soft palmar pads underneath
      const padGeo = new THREE.SphereGeometry(0.0017, 8, 8);
      disposables.push(padGeo);
      for (const [px, pz] of [
        [-0.0022, 0.0035],
        [0.0022, 0.0035],
        [0.0, 0.001],
      ]) {
        const pad = new THREE.Mesh(padGeo, padPinkMat);
        pad.position.set(px, -0.0023, pz);
        pad.scale.set(1.1, 0.65, 1.1);
        pad.renderOrder = 2;
        handRoot.add(pad);
      }

      // 4 distinct rosy-pink articulated splayed fingers (inner-to-outer mirrored by signX)
      const fingerSpecs = [
        { x: -signX * 0.0034, z: 0.0064, yaw: -signX * 0.36, prox: 0.0038, dist: 0.0032, r: 0.00125 }, // index
        { x: -signX * 0.0011, z: 0.0072, yaw: -signX * 0.11, prox: 0.0044, dist: 0.0036, r: 0.00130 }, // middle
        { x: signX * 0.0013, z: 0.0069, yaw: signX * 0.14, prox: 0.0042, dist: 0.0034, r: 0.00125 },  // ring
        { x: signX * 0.0035, z: 0.0056, yaw: signX * 0.42, prox: 0.0032, dist: 0.0028, r: 0.00112 },   // pinky
      ];
      const fingers: ArticulatedDigit[] = [];
      for (const fs of fingerSpecs) {
        const digit = buildDigit(fs.prox, fs.dist, fs.r, pinkSkinMat, clawMat, disposables, 0.08, fs.yaw);
        digit.proximal.position.set(fs.x, -0.0002, fs.z);
        handRoot.add(digit.proximal);
        fingers.push(digit);
      }

      // Cute tiny medial thumb nub on inner palm edge (real Syrian hamster pollex)
      const thumbGeo = new THREE.CapsuleGeometry(0.0011, 0.0016, 6, 8);
      thumbGeo.rotateZ(signX * 0.75);
      thumbGeo.rotateX(0.45);
      thumbGeo.translate(-signX * 0.0048, -0.0008, 0.0022);
      disposables.push(thumbGeo);
      const thumbMesh = new THREE.Mesh(thumbGeo, pinkSkinMat);
      thumbMesh.renderOrder = 2;
      handRoot.add(thumbMesh);

      hands.push({ side, fingers });
    }
  }

  // 3. Build Left & Right Hind Legs + Elongated 5-Toed Rosy-Pink Hind Feet
  for (const side of ["L", "R"] as const) {
    const signX = side === "L" ? -1 : 1;
    const pawBoneName = side === "L" ? "paw_bl" : "paw_br";

    const thighBone = asset.bones.get(`thigh_${side}`);
    if (thighBone) {
      const mount = attachAnatomicalMount(thighBone, `ham_anat_thigh_${side}`);
      attachedGroups.push(mount);

      // Plump golden-agouti/cream furred haunch emerging cleanly at rear flank
      const thighGeo = new THREE.SphereGeometry(0.0135, 14, 12);
      thighGeo.scale(0.88, 1.05, 1.25);
      thighGeo.translate(signX * 0.0155, -0.003, 0.003);
      disposables.push(thighGeo);
      const thighMesh = new THREE.Mesh(thighGeo, goldenHaunchMat);
      thighMesh.castShadow = true;
      thighMesh.receiveShadow = true;
      thighMesh.renderOrder = 2;
      mount.add(thighMesh);
    }

    const shinBone = asset.bones.get(`shin_${side}`);
    if (shinBone) {
      const mount = attachAnatomicalMount(shinBone, `ham_anat_shin_${side}`);
      attachedGroups.push(mount);

      // Furred lower leg / ankle tapering to pink heel outside flank fur
      const shinGeo = new THREE.CylinderGeometry(0.0080, 0.0054, 0.015, 14);
      shinGeo.rotateX(-0.22);
      shinGeo.translate(signX * 0.015, -0.003, 0.001);
      disposables.push(shinGeo);
      const shinMesh = new THREE.Mesh(shinGeo, creamFurMat);
      shinMesh.castShadow = true;
      shinMesh.receiveShadow = true;
      shinMesh.renderOrder = 2;
      mount.add(shinMesh);
    }

    const pawBone = asset.bones.get(pawBoneName);
    if (pawBone) {
      const mount = attachAnatomicalMount(pawBone, `ham_anat_hind_foot_${side}`);
      attachedGroups.push(mount);

      const footRoot = new THREE.Group();
      footRoot.name = `ham_hind_foot_root_${side}`;
      // Outward & forward so the elongated 5-toed pink hind feet are clearly visible when sitting & walking
      footRoot.position.set(signX * 0.0155, -0.0015, 0.011);
      mount.add(footRoot);

      // Elongated rosy-pink hind heel + metatarsus (Syrian hamsters have distinct long hind feet)
      const footGeo = new THREE.CapsuleGeometry(0.0046, 0.0105, 8, 14);
      footGeo.rotateX(Math.PI / 2);
      footGeo.scale(1.18, 0.56, 1.0);
      footGeo.translate(0, 0, 0.0045);
      disposables.push(footGeo);
      const footMesh = new THREE.Mesh(footGeo, pinkSkinMat);
      footMesh.castShadow = true;
      footMesh.receiveShadow = true;
      footMesh.renderOrder = 2;
      footRoot.add(footMesh);

      // Furred ankle collar over heel
      const ankleGeo = new THREE.SphereGeometry(0.0056, 12, 10);
      ankleGeo.scale(1.05, 0.85, 1.15);
      ankleGeo.translate(0, 0.0018, -0.0038);
      disposables.push(ankleGeo);
      const ankleMesh = new THREE.Mesh(ankleGeo, creamFurMat);
      ankleMesh.renderOrder = 2;
      footRoot.add(ankleMesh);

      // 5 distinct splayed rosy-pink hind toes with tiny ivory claws
      const toeSpecs = [
        { x: -signX * 0.0044, z: 0.0092, yaw: -signX * 0.48, prox: 0.0028, dist: 0.0024, r: 0.00105 }, // hallux
        { x: -signX * 0.0022, z: 0.0112, yaw: -signX * 0.21, prox: 0.0040, dist: 0.0032, r: 0.00118 }, // toe 2
        { x: 0.0, z: 0.0118, yaw: 0.0, prox: 0.0044, dist: 0.0034, r: 0.00122 },                        // toe 3
        { x: signX * 0.0023, z: 0.0112, yaw: signX * 0.22, prox: 0.0041, dist: 0.0032, r: 0.00118 },   // toe 4
        { x: signX * 0.0044, z: 0.0095, yaw: signX * 0.46, prox: 0.0031, dist: 0.0026, r: 0.00108 },   // toe 5
      ];
      const toes: ArticulatedDigit[] = [];
      for (const ts of toeSpecs) {
        const digit = buildDigit(ts.prox, ts.dist, ts.r, pinkSkinMat, clawMat, disposables, 0.05, ts.yaw);
        digit.proximal.position.set(ts.x, -0.0002, ts.z);
        footRoot.add(digit.proximal);
        toes.push(digit);
      }

      hindFeet.push({ side, toes });
    }
  }

  // Restore root transform cleanly
  asset.root.position.copy(savedPos);
  asset.root.quaternion.copy(savedQuat);
  asset.root.updateMatrixWorld(true);

  const update = (pose: PhysicsPoseInput) => {
    const p = pose.posture;
    const eatHold = THREE.MathUtils.clamp(p?.eatHoldAmount ?? 0, 0, 1);
    const groom = THREE.MathUtils.clamp(p?.groomAmount ?? 0, 0, 1);
    const dig = THREE.MathUtils.clamp(p?.digAmount ?? 0, 0, 1);
    const rear = THREE.MathUtils.clamp(p?.rearAmount ?? 0, 0, 1);
    const chewPhase = p?.chewPhase ?? 0;

    // 1. Animate 4 fingers on each front hand:
    //    - Curl gently inward around food while eating, with subtle alternating finger-twirling
    //    - Gentle curl during rearing/grooming
    //    - Splay open when planting on ground or scratching during digging
    for (const hand of hands) {
      const sidePhase = hand.side === "L" ? 0 : Math.PI;
      const inAir = hand.side === "L" ? !pose.footContacts.fl : !pose.footContacts.fr;
      for (let i = 0; i < hand.fingers.length; i++) {
        const d = hand.fingers[i];
        const twirl = eatHold > 0.05 ? Math.sin(chewPhase * 0.65 + sidePhase + i * 0.55) * 0.14 * eatHold : 0;
        const proxCurl =
          eatHold * (0.48 + twirl) +
          groom * 0.32 +
          rear * (1 - eatHold) * 0.24 +
          dig * 0.36 +
          (inAir ? 0.16 : 0.0);
        const distCurl =
          eatHold * (0.58 + twirl * 0.8) +
          groom * 0.38 +
          rear * (1 - eatHold) * 0.28 +
          dig * 0.42 +
          (inAir ? 0.18 : 0.0);

        d.proximal.rotation.x = d.basePitch + proxCurl;
        d.distal.rotation.x = distCurl;
        // Slight finger splay when gripping food or digging
        const splayBoost = 1.0 + eatHold * 0.16 + dig * 0.22;
        d.proximal.rotation.y = d.splayYaw * splayBoost;
      }
    }

    // 2. Animate 5 toes on each hind foot (gentle flex when stepping off ground, flat & splayed when supporting weight)
    for (const foot of hindFeet) {
      const inAir = foot.side === "L" ? !pose.footContacts.bl : !pose.footContacts.br;
      const flex = inAir ? 0.22 : 0.0;
      const braceSplay = 1.0 + Math.max(rear, eatHold) * 0.14;
      for (const t of foot.toes) {
        t.proximal.rotation.x = t.basePitch + flex;
        t.distal.rotation.x = flex * 1.1;
        t.proximal.rotation.y = t.splayYaw * braceSplay;
      }
    }
  };

  const dispose = () => {
    for (const g of attachedGroups) {
      g.parent?.remove(g);
    }
    for (const d of disposables) {
      d.dispose();
    }
  };

  return { update, dispose };
}
