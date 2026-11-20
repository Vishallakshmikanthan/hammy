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
  wristGroup: THREE.Group;
  fingers: ArticulatedDigit[];
}

interface ArticulatedHindFoot {
  side: "L" | "R";
  ankleGroup: THREE.Group;
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

function buildCompactDigit(
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

  // Plump, short proximal digit segment matching real Syrian hamster toe proportions
  const proxGeo = new THREE.CapsuleGeometry(radius, Math.max(0.0004, proxLen - radius * 1.1), 6, 10);
  proxGeo.rotateX(Math.PI / 2);
  proxGeo.translate(0, 0, proxLen * 0.45);
  disposables.push(proxGeo);
  const proxMesh = new THREE.Mesh(proxGeo, skinMat);
  proxMesh.castShadow = true;
  proxMesh.receiveShadow = true;
  proxMesh.renderOrder = 2;
  proximal.add(proxMesh);

  // Rounded distal fingertip pivoted at knuckle
  const distal = new THREE.Group();
  distal.position.set(0, 0, proxLen * 0.78);
  proximal.add(distal);

  const distR = radius * 0.86;
  const distGeo = new THREE.CapsuleGeometry(distR, Math.max(0.0003, distLen - distR * 1.1), 6, 10);
  distGeo.rotateX(Math.PI / 2);
  distGeo.translate(0, 0, distLen * 0.45);
  disposables.push(distGeo);
  const distMesh = new THREE.Mesh(distGeo, skinMat);
  distMesh.castShadow = true;
  distMesh.receiveShadow = true;
  distMesh.renderOrder = 2;
  distal.add(distMesh);

  // Tiny subtle ivory nail tip
  const clawLen = radius * 1.15;
  const clawGeo = new THREE.ConeGeometry(distR * 0.44, clawLen, 6);
  clawGeo.rotateX(Math.PI / 2 + 0.28);
  clawGeo.translate(0, -distR * 0.18, distLen * 0.82 + clawLen * 0.25);
  disposables.push(clawGeo);
  const clawMesh = new THREE.Mesh(clawGeo, clawMat);
  clawMesh.renderOrder = 2;
  distal.add(clawMesh);

  return { proximal, distal, basePitch, splayYaw };
}

/**
 * Crafts natural, original-looking Syrian hamster hands (4 cute chubby pink digits + palm)
 * and hind feet (5 cute pink toes + plantar sole) centered directly on the `paw_fl/fr/bl/br`
 * bone pivots — zero artificial sleeve extensions or floating lumps.
 */
export function buildAnatomicalLimbs(asset: LoadedHamsterAsset): AnatomicalLimbsController {
  const disposables: Array<{ dispose: () => void }> = [];
  const attachedGroups: THREE.Object3D[] = [];
  const hands: ArticulatedHand[] = [];
  const hindFeet: ArticulatedHindFoot[] = [];

  // Soft velvety rosy-pink skin matching living Syrian hamster paws & nose
  const pinkSkinMat = new THREE.MeshPhysicalMaterial({
    color: "#e8b0a4",
    roughness: 0.52,
    metalness: 0.0,
    sheen: 0.72,
    sheenRoughness: 0.45,
    sheenColor: new THREE.Color("#ffd6ce"),
  });
  const padPinkMat = new THREE.MeshPhysicalMaterial({
    color: "#d8968b",
    roughness: 0.58,
    metalness: 0.0,
  });
  const clawMat = new THREE.MeshPhysicalMaterial({
    color: "#f8f2e9",
    roughness: 0.28,
    metalness: 0.0,
    clearcoat: 0.5,
  });
  disposables.push(pinkSkinMat, padPinkMat, clawMat);

  // Temporarily zero root transform to compute exact rest-pose bone-to-anatomical frames
  const savedPos = asset.root.position.clone();
  const savedQuat = asset.root.quaternion.clone();
  asset.root.position.set(0, 0, 0);
  asset.root.quaternion.identity();
  asset.root.updateMatrixWorld(true);

  // 1. Hide the featureless placeholder oval paw meshes (keep in graph so nothing breaks)
  asset.root.traverse((obj) => {
    if ((obj as THREE.Mesh).isMesh && obj.name.includes("ham_paw")) {
      obj.visible = false;
    }
  });

  // 2. Build Left & Right Compact, Organic Syrian Hamster Hands on `paw_fl` / `paw_fr`
  for (const side of ["L", "R"] as const) {
    const signX = side === "L" ? -1 : 1;
    const pawBoneName = side === "L" ? "paw_fl" : "paw_fr";

    const pawBone = asset.bones.get(pawBoneName);
    if (pawBone) {
      const mount = attachAnatomicalMount(pawBone, `ham_anat_hand_${side}`);
      attachedGroups.push(mount);

      // Centered directly on the true `paw_fl/fr` bone pivot (zero artificial lever arm or bulky sleeve)
      const handRoot = new THREE.Group();
      handRoot.name = `ham_hand_root_${side}`;
      handRoot.position.set(0, -0.0004, 0.0008);
      mount.add(handRoot);

      // Petite, organic rosy-pink hamster palm (~7.5mm wide, matching reference photos 2EV8WK1MPMDC.jpg)
      const palmGeo = new THREE.SphereGeometry(0.0038, 14, 12);
      palmGeo.scale(0.98, 0.46, 1.05);
      palmGeo.translate(0, -0.0002, 0.0016);
      disposables.push(palmGeo);
      const palmMesh = new THREE.Mesh(palmGeo, pinkSkinMat);
      palmMesh.castShadow = true;
      palmMesh.receiveShadow = true;
      palmMesh.renderOrder = 2;
      handRoot.add(palmMesh);

      // Soft palmar cushion pads underneath
      const padGeo = new THREE.SphereGeometry(0.0012, 8, 8);
      disposables.push(padGeo);
      for (const [px, pz] of [
        [-0.0014, 0.0022],
        [0.0014, 0.0022],
        [0.0, 0.0004],
      ]) {
        const pad = new THREE.Mesh(padGeo, padPinkMat);
        pad.position.set(px, -0.0016, pz);
        pad.scale.set(1.05, 0.55, 1.05);
        pad.renderOrder = 2;
        handRoot.add(pad);
      }

      // 4 short, cute, organic rosy-pink fingers nestled in a natural Syrian hamster row
      const fingerSpecs = [
        { x: -signX * 0.0023, z: 0.0042, yaw: -signX * 0.20, prox: 0.0020, dist: 0.0016, r: 0.00092 }, // index
        { x: -signX * 0.0008, z: 0.0048, yaw: -signX * 0.06, prox: 0.0023, dist: 0.0018, r: 0.00096 }, // middle
        { x: signX * 0.0008, z: 0.0047, yaw: signX * 0.07, prox: 0.0022, dist: 0.0017, r: 0.00094 },  // ring
        { x: signX * 0.0023, z: 0.0040, yaw: signX * 0.22, prox: 0.0018, dist: 0.0014, r: 0.00086 },   // pinky
      ];
      const fingers: ArticulatedDigit[] = [];
      for (const fs of fingerSpecs) {
        const digit = buildCompactDigit(fs.prox, fs.dist, fs.r, pinkSkinMat, clawMat, disposables, 0.08, fs.yaw);
        digit.proximal.position.set(fs.x, -0.0002, fs.z);
        handRoot.add(digit.proximal);
        fingers.push(digit);
      }

      // Tiny inner thumb pad (pollex nub)
      const thumbGeo = new THREE.SphereGeometry(0.0009, 8, 8);
      thumbGeo.scale(0.85, 0.70, 1.20);
      thumbGeo.translate(-signX * 0.0031, -0.0005, 0.0019);
      disposables.push(thumbGeo);
      const thumbMesh = new THREE.Mesh(thumbGeo, pinkSkinMat);
      thumbMesh.renderOrder = 2;
      handRoot.add(thumbMesh);

      hands.push({ side, wristGroup: handRoot, fingers });
    }
  }

  // 3. Build Left & Right Natural Syrian Hamster Hind Feet on `paw_bl` / `paw_br`
  for (const side of ["L", "R"] as const) {
    const signX = side === "L" ? -1 : 1;
    const pawBoneName = side === "L" ? "paw_bl" : "paw_br";

    const pawBone = asset.bones.get(pawBoneName);
    if (pawBone) {
      const mount = attachAnatomicalMount(pawBone, `ham_anat_hind_foot_${side}`);
      attachedGroups.push(mount);

      // Centered directly on `paw_bl/br` pivot so hind foot steps, pushes, and pivots naturally
      const footRoot = new THREE.Group();
      footRoot.name = `ham_hind_foot_root_${side}`;
      footRoot.position.set(0, -0.0008, 0.0008);
      mount.add(footRoot);

      // Rosy-pink plantar sole & metatarsus (plantigrade contact surface)
      const footGeo = new THREE.CapsuleGeometry(0.0035, 0.0070, 8, 12);
      footGeo.rotateX(Math.PI / 2);
      footGeo.scale(1.08, 0.46, 1.0);
      footGeo.translate(0, -0.0002, 0.0028);
      disposables.push(footGeo);
      const footMesh = new THREE.Mesh(footGeo, pinkSkinMat);
      footMesh.castShadow = true;
      footMesh.receiveShadow = true;
      footMesh.renderOrder = 2;
      footRoot.add(footMesh);

      // 5 short, neat rosy-pink hind toes in natural Syrian hamster fan
      const toeSpecs = [
        { x: -signX * 0.0030, z: 0.0064, yaw: -signX * 0.28, prox: 0.0017, dist: 0.0014, r: 0.00082 }, // hallux
        { x: -signX * 0.0015, z: 0.0075, yaw: -signX * 0.12, prox: 0.0022, dist: 0.0017, r: 0.00090 }, // toe 2
        { x: 0.0, z: 0.0080, yaw: 0.0, prox: 0.0024, dist: 0.0018, r: 0.00094 },                        // toe 3 (longest)
        { x: signX * 0.0015, z: 0.0075, yaw: signX * 0.12, prox: 0.0022, dist: 0.0017, r: 0.00090 },   // toe 4
        { x: signX * 0.0030, z: 0.0066, yaw: signX * 0.26, prox: 0.0018, dist: 0.0014, r: 0.00083 },   // toe 5
      ];
      const toes: ArticulatedDigit[] = [];
      for (const ts of toeSpecs) {
        const digit = buildCompactDigit(ts.prox, ts.dist, ts.r, pinkSkinMat, clawMat, disposables, 0.05, ts.yaw);
        digit.proximal.position.set(ts.x, -0.0002, ts.z);
        footRoot.add(digit.proximal);
        toes.push(digit);
      }

      hindFeet.push({ side, ankleGroup: footRoot, toes });
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
    //    - Cup gently inward around food while eating, with subtle alternating nibbling motion
    //    - Flex during grooming/digging and stepping
    for (const hand of hands) {
      const sidePhase = hand.side === "L" ? 0 : Math.PI;
      const inAir = hand.side === "L" ? !pose.footContacts.fl : !pose.footContacts.fr;
      for (let i = 0; i < hand.fingers.length; i++) {
        const d = hand.fingers[i];
        const twirl = eatHold > 0.05 ? Math.sin(chewPhase * 0.65 + sidePhase + i * 0.5) * 0.12 * eatHold : 0;
        const proxCurl =
          eatHold * (0.42 + twirl) +
          groom * 0.28 +
          rear * (1 - eatHold) * 0.22 +
          dig * 0.34 +
          (inAir ? 0.18 : 0.0);
        const distCurl =
          eatHold * (0.50 + twirl * 0.8) +
          groom * 0.34 +
          rear * (1 - eatHold) * 0.25 +
          dig * 0.38 +
          (inAir ? 0.20 : 0.0);

        d.proximal.rotation.x = d.basePitch + proxCurl;
        d.distal.rotation.x = distCurl;
        const splayBoost = 1.0 + eatHold * 0.12 + dig * 0.18;
        d.proximal.rotation.y = d.splayYaw * splayBoost;
      }
    }

    // 2. Animate 5 toes on each hind foot (curl on step lift, splay flat on stance / sitting tripod)
    for (const foot of hindFeet) {
      const inAir = foot.side === "L" ? !pose.footContacts.bl : !pose.footContacts.br;
      const flex = inAir ? 0.26 : 0.0;
      const braceSplay = 1.0 + Math.max(rear, eatHold) * 0.12;
      for (const t of foot.toes) {
        t.proximal.rotation.x = t.basePitch + flex;
        t.distal.rotation.x = flex * 1.15;
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
