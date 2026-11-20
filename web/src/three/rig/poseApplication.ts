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
    const pelvisPitch =
      -0.36 * rear + 0.22 * crouch + 0.32 * curl + Math.sin(pose.gaitPhase * 2) * 0.04 * speedFactor;
    this.rotateAnatomical(
      "pelvis",
      pelvisPitch,
      Math.sin(pose.gaitPhase) * 0.05 * speedFactor,
      Math.cos(pose.gaitPhase) * 0.04 * speedFactor
    );

    // Spine waddle + pitch arch + rearing / curling
    const spineNames = ["spine_1", "spine_2", "spine_3", "spine_4"];
    let totalSpinePitch = pelvisPitch;
    for (let i = 0; i < spineNames.length; i++) {
      const wave = Math.sin(pose.gaitPhase - i * 0.5) * 0.075 * speedFactor * (1 - rear * 0.7);
      const arch = Math.cos(pose.gaitPhase * 2 - i * 0.35) * 0.045 * speedFactor;
      const rearPitch = -0.17 * rear; // bends spine upright
      const curlPitch = 0.22 * curl + 0.06 * crouch + 0.08 * dig;
      const segPitch = arch + rearPitch + curlPitch;
      totalSpinePitch += segPitch;
      this.rotateAnatomical(spineNames[i], segPitch, wave + yawRate * 0.045, 0);
    }

    // Neck & head: counter-level when rearing, duck when grooming/digging/curling/eating, plus natural look
    const neckPitch =
      0.34 * rear +
      0.38 * curl +
      0.24 * groom +
      0.32 * dig +
      0.16 * crouch +
      0.26 * eatHold +
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
      0.20 * eatHold +
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
      const phase = pose.gaitPhase + s;
      const swing = Math.sin(phase) * 0.48 * locoWeight;
      const liftWave = f.contact ? 0 : Math.max(0, Math.cos(phase));
      const lift = liftWave * 0.32 * locoWeight;

      // Subtle eating & grooming rhythmic hand motion
      const cPhase = (p?.chewPhase ?? 0) + (f.side === "R" ? Math.PI * 0.5 : 0);
      const nibbleShift = Math.sin(cPhase * 0.5) * 0.05 * eatHold;
      const biteLift = Math.sin(cPhase) * 0.002 * eatHold;

      const gPhase = (p?.groomPhase ?? 0) + (f.side === "R" ? 0.85 : 0);
      const groomScrubZ = Math.sin(gPhase) * 0.005 * groom;
      const groomScrubY = Math.cos(gPhase) * 0.004 * groom;

      const dPhase = (p?.digPhase ?? 0) + (f.side === "R" ? Math.PI : 0);
      const digReachZ = Math.sin(dPhase) * 0.010 * dig;
      const digLiftY = Math.max(0, Math.cos(dPhase)) * 0.005 * dig;

      // Scapular clavicular micro-glides during locomotion / digging (anchored firmly to torso, zero detached dislocations)
      const activeUpper = Math.max(rear, eatHold, groom);
      const standOrWalk = 1 - activeUpper;
      const strideZ = Math.sin(phase) * 0.015 * locoWeight;
      const strideLiftY = liftWave * 0.0085 * locoWeight;

      const shoulderDx = sideX * (0.0006 * standOrWalk - 0.0008 * eatHold);
      const shoulderDy = strideLiftY * 0.12 + biteLift * 0.15 + groomScrubY * 0.15 + digLiftY * 0.15;
      const shoulderDz = strideZ * 0.15 + digReachZ * 0.15 + groomScrubZ * 0.15 + 0.0005 * eatHold;

      this.translateAnatomical(`shoulder_${f.side}`, shoulderDx, shoulderDy, shoulderDz);

      // Arm kinematics:
      // 1. Eating with both paws: elbows tucked against flanks, forearms draw inward, paws cup food under chin
      // 2. Rearing upright: hands fold cutely against chest sternum (never sticking straight forward into midair)
      // 3. Grooming: paws scrub over muzzle / face
      // 4. Locomotion / standing: arms articulate with walking stride, planting flat on bedding
      let upperPitch = 0;
      let forearmPitch = 0;
      let forearmYaw = 0;
      let pawRelPitch = 0;
      let pawRoll = 0;
      let pawYaw = 0;

      if (eatHold > 0.02) {
        // Two-paw food holding: hands positioned right at mouth / chin level
        const relEatingPitch = -0.72 - totalSpinePitch * 0.45 + nibbleShift;
        upperPitch = relEatingPitch * 0.52 * eatHold;
        forearmPitch = relEatingPitch * 0.48 * eatHold;
        forearmYaw = f.sign * 0.38 * eatHold;
        pawRelPitch = -0.18 * eatHold + Math.sin(cPhase * 0.5) * 0.05 * eatHold;
        pawRoll = f.sign * 0.62 * eatHold;
        pawYaw = f.sign * 0.34 * eatHold;
      } else if (rear > 0.05) {
        // Adorable real Syrian hamster rearing stance: hands neatly folded against chest
        upperPitch = 0.24 * rear;
        forearmPitch = -0.38 * rear;
        forearmYaw = f.sign * 0.24 * rear;
        pawRelPitch = 0.06 * rear;
        pawRoll = f.sign * 0.18 * rear;
        pawYaw = f.sign * 0.16 * rear;
      } else if (groom > 0.02) {
        // Face-washing circular paw motion over whiskers and snout
        const gRot = Math.sin(gPhase) * 0.18;
        upperPitch = (-0.78 + gRot) * groom;
        forearmPitch = (-0.42 + gRot * 0.5) * groom;
        forearmYaw = f.sign * 0.32 * groom;
        pawRelPitch = (-0.35 + gRot * 0.6) * groom;
        pawRoll = f.sign * 0.45 * groom;
        pawYaw = f.sign * 0.22 * groom;
      } else {
        // Locomotion & standing: functional stepping and planting
        const desiredWorldArmPitch = (swing - lift * 0.65) + Math.sin(dPhase) * 0.48 * dig - 0.35 * curl;
        const relArmPitch = THREE.MathUtils.clamp(desiredWorldArmPitch - totalSpinePitch, -1.05, 1.05);
        upperPitch = relArmPitch * 0.52;
        forearmPitch = relArmPitch * 0.48;
        forearmYaw = f.sign * 0.04;
        pawRelPitch = THREE.MathUtils.clamp(-desiredWorldArmPitch + lift * 0.42, -0.85, 0.85);
        pawRoll = 0;
        pawYaw = f.sign * 0.06;
      }

      this.rotateAnatomical(
        `shoulder_${f.side}`,
        0,
        f.sign * (0.06 * eatHold + 0.04 * rear),
        f.sign * (0.08 * eatHold + 0.06 * rear)
      );
      this.rotateAnatomical(
        `upper_arm_${f.side}`,
        upperPitch,
        f.sign * (0.12 * eatHold + 0.06 * rear),
        f.sign * 0.08 * crouch
      );
      this.rotateAnatomical(
        `forearm_${f.side}`,
        forearmPitch,
        forearmYaw,
        0
      );
      this.rotateAnatomical(
        `paw_${f.side === "L" ? "fl" : "fr"}`,
        pawRelPitch,
        pawYaw,
        pawRoll
      );
    }

    // Hind limbs: functional stepping stride during walking/running + flat grounded tripod support when sitting/eating/rearing
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
      const sideX = h.side === "L" ? -1 : 1;
      const phase = pose.gaitPhase + s;
      const swing = Math.sin(phase) * 0.46 * locoWeight;
      const liftWave = h.contact ? 0 : Math.max(0, Math.cos(phase));
      const lift = liftWave * 0.28 * locoWeight;

      const sitSupport = Math.max(rear, eatHold, groom * 0.7);
      const strideZ = Math.sin(phase) * 0.016 * locoWeight;
      const strideLiftY = liftWave * 0.008 * locoWeight;

      // Ankle extension during push-off phase of stride
      const pushPhase = Math.sin(phase + 0.25) * 0.22 * locoWeight * (h.contact ? 1 : 0);

      // Micro-glides of hip joint within pelvic socket (zero detached dislocations)
      const hipDx = sideX * (0.0006 * sitSupport);
      const hipDy = strideLiftY * 0.12 - 0.0015 * rear - 0.001 * crouch;
      const hipDz = strideZ * 0.12;
      this.translateAnatomical(`hip_${h.side}`, hipDx, hipDy, hipDz);

      // Counter-rotate `pelvisPitch` so hind legs stay upright and hind feet stay level with the ground
      const desiredWorldLegPitch = swing - lift * 0.55 - 0.15 * curl;
      const relLegPitch = THREE.MathUtils.clamp(desiredWorldLegPitch - pelvisPitch, -0.95, 0.95);

      this.rotateAnatomical(
        `thigh_${h.side}`,
        relLegPitch * 0.55,
        h.sign * 0.18 * sitSupport,
        h.sign * (0.12 * sitSupport + 0.10 * crouch)
      );
      this.rotateAnatomical(
        `shin_${h.side}`,
        relLegPitch * 0.45,
        0,
        0
      );
      this.rotateAnatomical(
        `paw_${h.side === "L" ? "bl" : "br"}`,
        -desiredWorldLegPitch + lift * 0.42 - pushPhase,
        h.sign * (0.22 * sitSupport + 0.06),
        h.sign * (0.05 * sitSupport)
      );
    }
  }
}

