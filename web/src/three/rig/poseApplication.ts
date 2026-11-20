import * as THREE from "three";
import type { LoadedHamsterAsset, PhysicsPoseInput } from "./types";

interface BoneAxes {
  pitch: THREE.Vector3; // Hamster +X (sagittal: + = nose down / curl / leg back, - = rear up / leg forward)
  yaw: THREE.Vector3;   // Hamster +Y (horizontal: + = turn left, - = turn right)
  roll: THREE.Vector3;  // Hamster +Z (axial roll: + = tilt right, - = tilt left)
}

export class PoseApplicationLayer {
  private readonly restRotations = new Map<string, THREE.Euler>();
  private readonly restPositions = new Map<string, THREE.Vector3>();
  private readonly boneAxes = new Map<string, BoneAxes>();
  private readonly parentInvQuats = new Map<string, THREE.Quaternion>();

  constructor(private readonly asset: LoadedHamsterAsset) {
    // Capture rest transforms
    for (const [name, bone] of asset.bones.entries()) {
      this.restRotations.set(name, bone.rotation.clone());
      this.restPositions.set(name, bone.position.clone());
    }

    // Compute root-relative anatomical axes for every bone in rest pose
    const savedPos = asset.root.position.clone();
    const savedQuat = asset.root.quaternion.clone();
    asset.root.position.set(0, 0, 0);
    asset.root.quaternion.identity();
    asset.root.updateMatrixWorld(true);

    const worldQ = new THREE.Quaternion();
    const parentWorldQ = new THREE.Quaternion();
    for (const [name, bone] of asset.bones.entries()) {
      bone.getWorldQuaternion(worldQ);
      const invQ = worldQ.clone().invert();
      this.boneAxes.set(name, {
        pitch: new THREE.Vector3(1, 0, 0).applyQuaternion(invQ).normalize(),
        yaw: new THREE.Vector3(0, 1, 0).applyQuaternion(invQ).normalize(),
        roll: new THREE.Vector3(0, 0, 1).applyQuaternion(invQ).normalize(),
      });
      if (bone.parent) {
        bone.parent.getWorldQuaternion(parentWorldQ);
        this.parentInvQuats.set(name, parentWorldQ.clone().invert());
      } else {
        this.parentInvQuats.set(name, new THREE.Quaternion());
      }
    }

    asset.root.position.copy(savedPos);
    asset.root.quaternion.copy(savedQuat);
    asset.root.updateMatrixWorld(true);
  }

  public resetToRest(): void {
    for (const [name, bone] of this.asset.bones.entries()) {
      const rot = this.restRotations.get(name);
      const pos = this.restPositions.get(name);
      if (rot) bone.rotation.copy(rot);
      if (pos) bone.position.copy(pos);
    }
  }

  private translateAnatomical(name: string, dx: number, dy: number, dz: number): void {
    const bone = this.asset.bones.get(name);
    const invParentQ = this.parentInvQuats.get(name);
    if (!bone || !invParentQ) return;
    const delta = new THREE.Vector3(dx, dy, dz).applyQuaternion(invParentQ);
    bone.position.add(delta);
  }

  private rotateAnatomical(name: string, pitch: number, yaw = 0, roll = 0): void {
    const bone = this.asset.bones.get(name);
    const axes = this.boneAxes.get(name);
    if (!bone || !axes) return;
    if (Math.abs(yaw) > 1e-5) bone.rotateOnAxis(axes.yaw, yaw);
    if (Math.abs(pitch) > 1e-5) bone.rotateOnAxis(axes.pitch, pitch);
    if (Math.abs(roll) > 1e-5) bone.rotateOnAxis(axes.roll, roll);
  }

  public applyPhysicsPose(pose: PhysicsPoseInput): void {
    this.resetToRest();

    this.asset.root.position.set(pose.rootPosition[0], pose.rootPosition[1], pose.rootPosition[2]);
    this.asset.root.quaternion.set(
      pose.rootQuaternion[0],
      pose.rootQuaternion[1],
      pose.rootQuaternion[2],
      pose.rootQuaternion[3]
    );

    const speed = Math.hypot(pose.velocity[0], pose.velocity[1], pose.velocity[2]);
    // Calibrated to real-video hamster walking speed (~0.10–0.13 m/s)
    const speedFactor = THREE.MathUtils.clamp(speed / 0.12, 0, 1);
    const yawRate = pose.angularVelocity[1];
    const p = pose.posture;

    const rear = THREE.MathUtils.clamp(p?.rearAmount ?? 0, 0, 1);
    const crouch = THREE.MathUtils.clamp(p?.crouchAmount ?? 0, 0, 1);
    const curl = THREE.MathUtils.clamp(p?.curlAmount ?? 0, 0, 1);
    const groom = THREE.MathUtils.clamp(p?.groomAmount ?? 0, 0, 1);
    const eatHold = THREE.MathUtils.clamp(p?.eatHoldAmount ?? 0, 0, 1);
    const dig = THREE.MathUtils.clamp(p?.digAmount ?? 0, 0, 1);
    const chew = THREE.MathUtils.clamp(p?.chewAmount ?? 0, 0, 1);

    // Subtle vertical body bob while scurrying + crouch/curl/rear pelvis height
    const pelvis = this.asset.bones.get("pelvis");
    if (pelvis) {
      const strideBob = Math.abs(Math.sin(pose.gaitPhase)) * 0.0022 * speedFactor * (1 - rear);
      const postureDrop = -0.0045 * crouch - 0.0055 * curl + 0.0015 * rear;
      pelvis.position.y += strideBob + postureDrop;
    }

    // Pelvis pitch: tilt back when rearing up, curl forward when sleeping
    this.rotateAnatomical(
      "pelvis",
      -0.36 * rear + 0.22 * crouch + 0.32 * curl + Math.sin(pose.gaitPhase * 2) * 0.04 * speedFactor,
      Math.sin(pose.gaitPhase) * 0.05 * speedFactor,
      Math.cos(pose.gaitPhase) * 0.04 * speedFactor
    );

    // Spine waddle + pitch arch + rearing / curling
    const spineNames = ["spine_1", "spine_2", "spine_3", "spine_4"];
    for (let i = 0; i < spineNames.length; i++) {
      const wave = Math.sin(pose.gaitPhase - i * 0.5) * 0.075 * speedFactor * (1 - rear * 0.7);
      const arch = Math.cos(pose.gaitPhase * 2 - i * 0.35) * 0.045 * speedFactor;
      const rearPitch = -0.17 * rear; // bends spine upright
      const curlPitch = 0.22 * curl + 0.06 * crouch + 0.08 * dig;
      this.rotateAnatomical(spineNames[i], arch + rearPitch + curlPitch, wave + yawRate * 0.045, 0);
    }

    // Neck & head: counter-level when rearing, duck when grooming/digging/curling, plus natural look
    const neckPitch =
      0.34 * rear +
      0.38 * curl +
      0.24 * groom +
      0.32 * dig +
      0.16 * crouch +
      (p?.headPitch ?? 0) * 0.42 -
      Math.sin(pose.gaitPhase * 2) * 0.03 * speedFactor;
    const neckYaw = (p?.headYaw ?? 0) * 0.42 + yawRate * 0.08;
    const neckRoll = (p?.headRoll ?? 0) * 0.35;
    this.rotateAnatomical("neck", neckPitch, neckYaw, neckRoll);

    const headGroomBob = groom > 0.01 ? Math.sin(p?.groomPhase ?? 0) * 0.09 * groom : 0;
    const headDigBob = dig > 0.01 ? Math.sin((p?.digPhase ?? 0) * 0.5) * 0.06 * dig : 0;
    const headPitch =
      0.18 * rear +
      0.32 * curl +
      0.20 * groom +
      0.15 * dig +
      headGroomBob +
      headDigBob +
      (p?.headPitch ?? 0) * 0.58;
    const headYaw = (p?.headYaw ?? 0) * 0.58 + yawRate * 0.06;
    const headRoll = (p?.headRoll ?? 0) * 0.65;
    this.rotateAnatomical("head", headPitch, headYaw, headRoll);

    // Jaw chewing / nibbling / yawning
    if (chew > 0.01) {
      const jawOpen = Math.max(0, Math.sin(p?.chewPhase ?? 0)) * 0.34 * chew;
      this.rotateAnatomical("jaw", jawOpen, 0, 0);
    }

    // Locomotion gait blended down when rearing, eating, grooming, digging, or curled
    const locoWeight = speedFactor * (1 - Math.max(rear * 0.85, eatHold * 0.98, groom * 0.95, dig * 0.95, curl));

    // Front limbs: locomotion + two-hand food holding + rearing tuck + face-washing grooming + bedding digging
    const frontSpecs: Array<{
      side: "L" | "R";
      phaseOffset: number;
      contact: boolean;
      sign: number;
    }> = [
      { side: "L", phaseOffset: 0, contact: pose.footContacts.fl, sign: 1 },
      { side: "R", phaseOffset: Math.PI, contact: pose.footContacts.fr, sign: -1 },
    ];

    for (const f of frontSpecs) {
      const s = f.phaseOffset;
      const sideX = f.side === "L" ? -1 : 1;
      const swing = Math.sin(pose.gaitPhase + s) * 0.56 * locoWeight;
      const lift = (f.contact ? 0 : Math.max(0, Math.cos(pose.gaitPhase + s)) * 0.42) * locoWeight;

      // Project shoulders gently forward during eating/grooming/rearing so rosy-pink hands clear the chest fur
      const shoulderOutX = sideX * (0.003 * locoWeight + 0.005 * eatHold + 0.004 * groom);
      const shoulderLiftY = 0.005 * eatHold + 0.004 * groom + 0.002 * rear;
      const shoulderFwdZ = 0.014 * eatHold + 0.011 * groom + 0.007 * rear + 0.006 * dig;
      if (Math.abs(shoulderOutX) + Math.abs(shoulderLiftY) + Math.abs(shoulderFwdZ) > 1e-5) {
        this.translateAnatomical(`shoulder_${f.side}`, shoulderOutX, shoulderLiftY, shoulderFwdZ);
      }

      // Dedicated two-hand food cradling pose: bring both forearms forward & inward to cradle food under snout
      const cPhase = (p?.chewPhase ?? 0) + (f.side === "R" ? Math.PI * 0.5 : 0);
      const nibbleShift = Math.sin(cPhase * 0.5) * 0.08 * eatHold;
      const biteLift = Math.sin(cPhase) * 0.05 * eatHold;

      // Face-washing grooming strokes
      const gPhase = (p?.groomPhase ?? 0) + (f.side === "R" ? 0.85 : 0);
      const groomScrub = Math.sin(gPhase) * 0.22 * groom;
      const groomCircle = Math.cos(gPhase) * 0.14 * groom;

      // Cleanly blend rearing-tuck, face-washing grooming, and two-hand food-holding (never double-added!)
      const activeUpperMode = Math.max(rear, groom, eatHold);
      const eatShare = eatHold;
      const groomShare = groom * (1 - eatHold);
      const rearShare = Math.max(0, activeUpperMode - Math.max(eatShare, groomShare));
      const modeDenom = Math.max(1e-4, eatShare + groomShare + rearShare);

      const blendedShoulderRoll =
        (f.sign * 0.14 * rearShare + f.sign * 0.24 * groomShare + f.sign * 0.16 * eatShare) /
        modeDenom *
        activeUpperMode;
      const blendedUpper =
        (-0.46 * rearShare + (-0.78 + groomScrub) * groomShare + (-0.64 + biteLift) * eatShare) /
        modeDenom *
        activeUpperMode;
      const blendedForearm =
        (-0.68 * rearShare + (-0.90 - groomCircle * 0.45) * groomShare + (-0.54 + nibbleShift) * eatShare) /
        modeDenom *
        activeUpperMode;
      const blendedForearmYaw =
        (f.sign * 0.14 * rearShare +
          (f.sign * 0.22 + groomCircle * f.sign * 0.32) * groomShare +
          (f.sign * 0.34 + nibbleShift * f.sign * 0.3) * eatShare) /
        modeDenom *
        activeUpperMode;
      const blendedPawPitch =
        (0.28 * rearShare + (0.28 + groomScrub * 0.4) * groomShare + (-0.28 + biteLift * 0.6) * eatShare) /
        modeDenom *
        activeUpperMode;
      // Rotate palms inward toward each other when holding food or washing face
      const blendedPawRoll =
        (f.sign * 0.35 * rearShare + f.sign * 0.55 * groomShare + f.sign * 0.82 * eatShare) /
        modeDenom *
        activeUpperMode;
      const blendedPawYaw = (-f.sign * 0.28 * eatShare) / modeDenom * activeUpperMode;

      // Bedding digging: fast alternating front-paw scratching
      const dPhase = (p?.digPhase ?? 0) + (f.side === "R" ? Math.PI : 0);
      const digSwing = Math.sin(dPhase) * 0.58 * dig;
      const digFlex = -Math.max(0, Math.cos(dPhase)) * 0.50 * dig;

      // Curl tuck
      const curlUpper = -0.32 * curl;
      const curlForearm = -0.58 * curl;

      const finalUpperPitch = THREE.MathUtils.clamp(
        swing - lift * 0.5 + blendedUpper + digSwing + curlUpper,
        -0.98,
        0.72
      );
      const finalForearmPitch = THREE.MathUtils.clamp(
        -lift * 1.15 + blendedForearm + digFlex + curlForearm,
        -1.08,
        0.42
      );

      this.rotateAnatomical(
        `shoulder_${f.side}`,
        0,
        f.sign * 0.12 * eatHold,
        THREE.MathUtils.clamp(blendedShoulderRoll, -0.34, 0.34)
      );
      this.rotateAnatomical(
        `upper_arm_${f.side}`,
        finalUpperPitch,
        f.sign * 0.16 * eatHold,
        f.sign * 0.12 * crouch
      );
      this.rotateAnatomical(
        `forearm_${f.side}`,
        finalForearmPitch,
        blendedForearmYaw,
        0
      );
      this.rotateAnatomical(
        `paw_${f.side === "L" ? "fl" : "fr"}`,
        THREE.MathUtils.clamp(lift * 0.45 + blendedPawPitch, -0.55, 0.65),
        blendedPawYaw,
        blendedPawRoll
      );
    }

    // Hind limbs: crisp locomotion + visible forward tripod brace when sitting/eating/rearing
    const hindSpecs: Array<{
      side: "L" | "R";
      phaseOffset: number;
      contact: boolean;
      sign: number;
    }> = [
      { side: "L", phaseOffset: Math.PI, contact: pose.footContacts.bl, sign: 1 },
      { side: "R", phaseOffset: 0, contact: pose.footContacts.br, sign: -1 },
    ];

    for (const h of hindSpecs) {
      const s = h.phaseOffset;
      const swing = Math.sin(pose.gaitPhase + s) * 0.50 * locoWeight;
      const lift = (h.contact ? 0 : Math.max(0, Math.cos(pose.gaitPhase + s)) * 0.36) * locoWeight;

      const sitSupport = Math.max(rear, eatHold);
      const rearThigh = -0.34 * sitSupport - 0.18 * curl;
      const rearShin = 0.28 * sitSupport + 0.35 * curl + 0.22 * crouch;

      this.rotateAnatomical(
        `thigh_${h.side}`,
        swing - lift * 0.4 + rearThigh,
        h.sign * 0.12 * sitSupport,
        h.sign * (0.14 * sitSupport + 0.14 * crouch)
      );
      this.rotateAnatomical(
        `shin_${h.side}`,
        -lift * 0.95 + rearShin,
        0,
        0
      );
      this.rotateAnatomical(
        `paw_${h.side === "L" ? "bl" : "br"}`,
        lift * 0.42 - 0.22 * sitSupport,
        h.sign * 0.14 * sitSupport,
        0
      );
    }
  }
}

