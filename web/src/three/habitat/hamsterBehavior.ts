import * as THREE from "three";
import type { PetState, WorldEvent } from "../../types";
import {
  DEFAULT_PROCEDURAL_CONFIG,
  type HamsterPostureState,
  type PhysicsPoseInput,
  type ProceduralLayerConfig,
} from "../rig/types";

export interface TunnelSegment {
  a: THREE.Vector3;
  b: THREE.Vector3;
  radius: number;
  topY: number;
  isOpenA?: boolean;
  isOpenB?: boolean;
}

export interface TunnelSpineConfig {
  /** Ordered interior centerline points from Mouth A -> Elbow -> Mouth B */
  centerline: THREE.Vector3[];
  /** Outside approach waypoint aligned with Mouth A */
  mouthAApproach: THREE.Vector3;
  /** Outside approach waypoint aligned with Mouth B */
  mouthBApproach: THREE.Vector3;
  /** Cylinder segments for precise 2D capsule obstacle clearance & top-climb surface */
  segments: TunnelSegment[];
  /** Ordered ridge points along top surface of the log for climbing & perching */
  topPath: THREE.Vector3[];
  /** Approach waypoint at low slope to climb onto the log */
  climbEntryPos: THREE.Vector3;
  /** Exit waypoint after climbing down from the log */
  climbExitPos: THREE.Vector3;
}

export interface PlacedPropAnchor {
  objectId: string;
  itemId: string;
  name: string;
  category: "prop" | "decor" | "water";
  pos: THREE.Vector3;
  radius: number;
  rotationY: number;
}

export interface HabitatPropAnchors {
  beddingY: number;
  bowlPos: THREE.Vector3;
  spoutPos: THREE.Vector3;
  wheelPos: THREE.Vector3;
  hideoutPos: THREE.Vector3;
  tunnelPos: THREE.Vector3;
  chewPos: THREE.Vector3;
  tunnelBox?: THREE.Box3;
  tunnelBoxes?: THREE.Box3[];
  tunnelSpine?: TunnelSpineConfig;
  hideoutBox?: THREE.Box3;
  hideoutYaw?: number;
  hideoutHalfExtents?: { hx: number; hz: number };
  wheelBox?: THREE.Box3;
  wheelTrackY?: number;
  bottlePos?: THREE.Vector3;
  sampleBeddingY?: (x: number, z: number) => number;
  /** Optional opt-in flags & dynamic obstacles from the Shelf Layout (defaults to true when undefined so legacy unit tests pass unchanged) */
  hasBowl?: boolean;
  hasWheel?: boolean;
  hasHideout?: boolean;
  hasTunnel?: boolean;
  hasChew?: boolean;
  foodLevel?: number;
  waterLevel?: number;
  dynamicObstacles?: Array<{ id: string; pos: THREE.Vector3; radius: number }>;
  placedProps?: PlacedPropAnchor[];
  offeredFoodTarget?: { objectId: string; itemId: string; pos: THREE.Vector3 } | null;
  onFoodConsumed?: (objectId: string, itemId: string) => void;
  onWaterConsumed?: () => void;
}

export interface HamsterBehaviorStep {
  pose: PhysicsPoseInput;
  proceduralConfig: ProceduralLayerConfig;
  wheelSpinDelta: number;
  activityLabel: string;
}

type MicroPhase =
  | "scurry"
  | "sniff"
  | "rear_up"
  | "groom"
  | "forage_eat"
  | "drink"
  | "gnaw"
  | "dig"
  | "wheel_run"
  | "wheel_pause"
  | "rest"
  | "log_perch"
  | "inspect_prop";

type HabitatGoal =
  | "wander"
  | "corner_sit"
  | "wheel"
  | "water"
  | "hideout"
  | "bowl"
  | "chew"
  | "tunnel_through"
  | "log_climb"
  | "inspect_prop";

function shortestAngleDiff(from: number, to: number): number {
  let diff = ((to - from + Math.PI) % (Math.PI * 2)) - Math.PI;
  if (diff < -Math.PI) diff += Math.PI * 2;
  return diff;
}

function damp(current: number, target: number, lambda: number, dt: number): number {
  return THREE.MathUtils.lerp(current, target, 1 - Math.exp(-lambda * dt));
}

/**
 * Naturalistic real-life hamster locomotion and ethogram controller.
 * Models stop-and-go darting bursts, saccadic head-snaps, bipedal rearing ("periscoping"),
 * face-washing grooming, bedding digging, cheek-pouch stuffing, wheel sprints with coasting,
 * and curled-up resting.
 */
export class HamsterBehaviorController {
  private pos = new THREE.Vector3(-0.08, 0.165, 0.12);
  private yaw = 0;
  private gaitPhase = 0;
  private currentSpeed = 0;
  private targetPos = new THREE.Vector3(-0.08, 0.165, 0.12);
  private lastServerPosKey = "";
  private hasSyncedServerOnce = false;
  private serverSkillConsumed = false;
  private exitingHideout = false;
  private exitingWheel = false;
  private recentGoals: HabitatGoal[] = [];

  private phase: MicroPhase = "sniff";
  private prevPhase: MicroPhase = "sniff";
  private phaseTimer = 0.8;
  private microFreezeTimer = 0;
  private wheelBurstSpeed = 0.34;
  private wheelCoastVel = 0;
  private wheelPauseElapsed = 0;
  private seed = 1337;

  // Autonomous habitat goal state (used both offline and between server commands)
  private goal: HabitatGoal = "wander";
  private goalStage: "approach" | "active" | "exit" = "approach";
  private goalCyclesLeft = 0;
  private faceTargetPos: THREE.Vector3 | null = null;
  private waypointQueue: THREE.Vector3[] = [];
  private stuckCheckPos = new THREE.Vector3(-0.08, 0.165, 0.12);
  private stuckTimer = 0;

  // Functional middle-log state (entering/exiting hollow tunnel & climbing on top)
  private tunnelDirectionForward = true;
  private logActivePath: THREE.Vector3[] = [];
  private logPathIndex = 0;
  private logHasPerched = false;

  // Curious prop-sensing state (detects newly dropped or moved props and inspects them)
  private hasInitializedProps = false;
  private knownPropSignatures = new Map<string, string>();
  private pendingInspectQueue: string[] = [];
  private activeInspectProp: PlacedPropAnchor | null = null;
  private activeInspectIsNew = false;

  // Saccadic head look targets (hamsters snap their heads quickly between holds)
  private headSaccadeTimer = 0.3;
  private targetHeadYaw = 0;
  private targetHeadPitch = 0;
  private targetHeadRoll = 0;

  // Smoothly blended posture state
  private posture: HamsterPostureState = {
    rearAmount: 0,
    crouchAmount: 0,
    curlAmount: 0,
    headPitch: 0,
    headYaw: 0,
    headRoll: 0,
    groomAmount: 0,
    groomPhase: 0,
    digAmount: 0,
    digPhase: 0,
    chewAmount: 0,
    chewPhase: 0,
    eatHoldAmount: 0,
  };

  private smoothCheekL = 0;
  private smoothCheekR = 0;
  public isHoldingFood = false;
  public heldFoodItemId: string | null = null;
  private activeFoodObjectId: string | null = null;
  private lastTrackedFoodObjectId: string | null = null;
  private hasTriggeredEatCallback = false;
  private hasTriggeredDrinkCallback = false;

  private nextRand(): number {
    this.seed = (this.seed * 1664525 + 1013904223) >>> 0;
    return this.seed / 4294967296;
  }

  private sampleGroundY(x: number, z: number, anchors: HabitatPropAnchors): number {
    return anchors.sampleBeddingY ? anchors.sampleBeddingY(x, z) : anchors.beddingY;
  }

  private pushOutOfBox2D(v: THREE.Vector3, box: THREE.Box3, margin: number): void {
    const minX = box.min.x - margin;
    const maxX = box.max.x + margin;
    const minZ = box.min.z - margin;
    const maxZ = box.max.z + margin;
    if (v.x > minX && v.x < maxX && v.z > minZ && v.z < maxZ) {
      const dLeft = v.x - minX;
      const dRight = maxX - v.x;
      const dFront = v.z - minZ;
      const dBack = maxZ - v.z;
      const m = Math.min(dLeft, dRight, dFront, dBack);
      if (m === dLeft) v.x = minX;
      else if (m === dRight) v.x = maxX;
      else if (m === dFront) v.z = minZ;
      else v.z = maxZ;
    }
  }

  private pushOutOfOBB2D(
    v: THREE.Vector3,
    cx: number,
    cz: number,
    hx: number,
    hz: number,
    yaw: number,
    margin: number
  ): void {
    const dx = v.x - cx;
    const dz = v.z - cz;
    const c = Math.cos(yaw);
    const s = Math.sin(yaw);
    // Inverse of Three.js Y-up rotation (wx = lx*c + lz*s, wz = -lx*s + lz*c)
    let lx = dx * c - dz * s;
    let lz = dx * s + dz * c;
    const ex = hx + margin;
    const ez = hz + margin;
    if (Math.abs(lx) < ex && Math.abs(lz) < ez) {
      const penX = ex - Math.abs(lx);
      const penZ = ez - Math.abs(lz);
      if (penX < penZ) {
        lx = lx >= 0 ? ex : -ex;
      } else {
        lz = lz >= 0 ? ez : -ez;
      }
      v.x = cx + lx * c + lz * s;
      v.z = cz - lx * s + lz * c;
    }
  }

  private isPhysicallyInsideHideout(anchors: HabitatPropAnchors): boolean {
    if (!(anchors.hasHideout ?? true)) return false;
    if (anchors.hideoutHalfExtents) {
      const yaw = anchors.hideoutYaw ?? -0.27925;
      const dx = this.pos.x - anchors.hideoutPos.x;
      const dz = this.pos.z - anchors.hideoutPos.z;
      const c = Math.cos(yaw);
      const s = Math.sin(yaw);
      const lx = dx * c - dz * s;
      const lz = dx * s + dz * c;
      return Math.abs(lx) < anchors.hideoutHalfExtents.hx + 0.045 && Math.abs(lz) < anchors.hideoutHalfExtents.hz + 0.045;
    }
    if (anchors.hideoutBox) {
      return (
        this.pos.x > anchors.hideoutBox.min.x - 0.04 &&
        this.pos.x < anchors.hideoutBox.max.x + 0.04 &&
        this.pos.z > anchors.hideoutBox.min.z - 0.04 &&
        this.pos.z < anchors.hideoutBox.max.z + 0.04
      );
    }
    return Math.hypot(this.pos.x - anchors.hideoutPos.x, this.pos.z - anchors.hideoutPos.z) < 0.13;
  }

  private isPhysicallyOnWheel(anchors: HabitatPropAnchors): boolean {
    if (!(anchors.hasWheel ?? true)) return false;
    if (anchors.wheelBox) {
      return (
        this.pos.x > anchors.wheelBox.min.x - 0.04 &&
        this.pos.x < anchors.wheelBox.max.x + 0.04 &&
        this.pos.z > anchors.wheelBox.min.z - 0.04 &&
        this.pos.z < anchors.wheelBox.max.z + 0.04
      );
    }
    return Math.hypot(this.pos.x - anchors.wheelPos.x, this.pos.z - anchors.wheelPos.z) < 0.13;
  }

  private pushOutOfTunnelBoxes(v: THREE.Vector3, boxes: THREE.Box3[], margin: number): void {
    for (let pass = 0; pass < 3; pass++) {
      for (const box of boxes) {
        this.pushOutOfBox2D(v, box, margin);
      }
    }
    // If still wedged in an L-junction between two adjacent tunnel boxes, eject to nearest union boundary
    const stillInside = boxes.some(
      (b) =>
        v.x > b.min.x - margin &&
        v.x < b.max.x + margin &&
        v.z > b.min.z - margin &&
        v.z < b.max.z + margin
    );
    if (stillInside) {
      let minX = Infinity;
      let maxX = -Infinity;
      let minZ = Infinity;
      let maxZ = -Infinity;
      for (const b of boxes) {
        minX = Math.min(minX, b.min.x - margin);
        maxX = Math.max(maxX, b.max.x + margin);
        minZ = Math.min(minZ, b.min.z - margin);
        maxZ = Math.max(maxZ, b.max.z + margin);
      }
      const dLeft = v.x - minX;
      const dRight = maxX - v.x;
      const dFront = v.z - minZ;
      const dBack = maxZ - v.z;
      const m = Math.min(dLeft, dRight, dFront, dBack);
      if (m === dLeft) v.x = minX;
      else if (m === dRight) v.x = maxX;
      else if (m === dFront) v.z = minZ;
      else v.z = maxZ;
    }
  }

  private pushOutOfCapsule2D(
    v: THREE.Vector3,
    a: THREE.Vector3,
    b: THREE.Vector3,
    totalRadius: number,
    isOpenA = false,
    isOpenB = false
  ): void {
    const abx = b.x - a.x;
    const abz = b.z - a.z;
    const lenSq = abx * abx + abz * abz;
    if (lenSq < 1e-8) return;
    const rawT = ((v.x - a.x) * abx + (v.z - a.z) * abz) / lenSq;

    // Open mouth openings do not have solid blocking hemisphere endcaps
    if (isOpenB && rawT > 1.0) return;
    if (isOpenA && rawT < 0.0) return;

    const t = THREE.MathUtils.clamp(rawT, 0, 1);
    const cx = a.x + abx * t;
    const cz = a.z + abz * t;
    const dx = v.x - cx;
    const dz = v.z - cz;
    const d = Math.hypot(dx, dz);
    if (d < totalRadius) {
      const nx = d > 1e-4 ? dx / d : 0;
      const nz = d > 1e-4 ? dz / d : 1;
      v.x = cx + nx * totalRadius;
      v.z = cz + nz * totalRadius;
    }
  }

  private pushOutOfProps(
    v: THREE.Vector3,
    anchors: HabitatPropAnchors,
    _petState?: PetState | null
  ): THREE.Vector3 {
    const bodyRadius = 0.048;
    const obstacles: Array<{ pos: THREE.Vector3; radius: number }> = [];
    if (anchors.hasBowl ?? true) {
      // Ceramic bowl radius 0.042m + 0.030m side clearance keeps hamster outside rim while leaving an open aisle to water/hideout
      obstacles.push({ pos: anchors.bowlPos, radius: 0.072 });
    }
    if (anchors.hasChew ?? true) {
      obstacles.push({ pos: anchors.chewPos, radius: 0.040 });
    }
    // Keep hamster cleanly clear of the right-wall water bottle cylinder & spout stem
    const bottleCenter =
      anchors.bottlePos ??
      new THREE.Vector3(anchors.spoutPos.x + 0.022, anchors.beddingY, anchors.spoutPos.z);
    obstacles.push({ pos: bottleCenter, radius: 0.066 });

    if (anchors.dynamicObstacles) {
      for (const dyn of anchors.dynamicObstacles) {
        obstacles.push({ pos: dyn.pos, radius: dyn.radius + bodyRadius });
      }
    }

    // NEVER disable prop collision just because server booleans flipped across the cage!
    // Only allow entry/exit when physically walking through the doorway or wheel opening.
    const allowHideout =
      (this.goal === "hideout" && this.goalStage !== "approach") || this.exitingHideout;
    if ((anchors.hasHideout ?? true) && !allowHideout && !anchors.hideoutBox && !anchors.hideoutHalfExtents) {
      obstacles.push({ pos: anchors.hideoutPos, radius: 0.125 });
    }

    const allowWheel =
      (this.goal === "wheel" && this.goalStage !== "approach") || this.exitingWheel;
    if ((anchors.hasWheel ?? true) && !allowWheel && !anchors.wheelBox) {
      obstacles.push({ pos: anchors.wheelPos, radius: 0.148 });
    }

    const allowTunnelTraversal =
      (this.goal === "tunnel_through" || this.goal === "log_climb") &&
      (this.goalStage === "active" || this.goalStage === "exit");

    if (
      (anchors.hasTunnel ?? true) &&
      !allowTunnelTraversal &&
      !anchors.tunnelSpine?.segments?.length &&
      !anchors.tunnelBoxes?.length &&
      !anchors.tunnelBox
    ) {
      obstacles.push({ pos: anchors.tunnelPos, radius: 0.12 });
    }

    for (let pass = 0; pass < 3; pass++) {
      for (const obs of obstacles) {
        const dx = v.x - obs.pos.x;
        const dz = v.z - obs.pos.z;
        const d = Math.hypot(dx, dz);
        if (d < obs.radius) {
          const nx = d > 1e-4 ? dx / d : 1;
          const nz = d > 1e-4 ? dz / d : 0;
          v.x = obs.pos.x + nx * obs.radius;
          v.z = obs.pos.z + nz * obs.radius;
        }
      }

      if (!allowHideout && (anchors.hasHideout ?? true)) {
        if (anchors.hideoutHalfExtents) {
          this.pushOutOfOBB2D(
            v,
            anchors.hideoutPos.x,
            anchors.hideoutPos.z,
            anchors.hideoutHalfExtents.hx,
            anchors.hideoutHalfExtents.hz,
            anchors.hideoutYaw ?? -0.27925,
            0.042
          );
        } else if (anchors.hideoutBox) {
          this.pushOutOfBox2D(v, anchors.hideoutBox, 0.038);
        }
      }
      if (!allowWheel && (anchors.hasWheel ?? true) && anchors.wheelBox) {
        this.pushOutOfBox2D(v, anchors.wheelBox, 0.040);
      }
      if (!allowTunnelTraversal) {
        if (anchors.tunnelSpine && anchors.tunnelSpine.segments.length > 0) {
          const tunnelMargin = 0.050;
          for (const seg of anchors.tunnelSpine.segments) {
            const isOpenA = Boolean(
              seg.isOpenA ||
              (anchors.tunnelSpine.centerline.length > 0 &&
                (seg.a.distanceTo(anchors.tunnelSpine.centerline[0]) < 0.045 ||
                  seg.a.distanceTo(anchors.tunnelSpine.centerline[anchors.tunnelSpine.centerline.length - 1]) < 0.045))
            );
            const isOpenB = Boolean(
              seg.isOpenB ||
              (anchors.tunnelSpine.centerline.length > 0 &&
                (seg.b.distanceTo(anchors.tunnelSpine.centerline[0]) < 0.045 ||
                  seg.b.distanceTo(anchors.tunnelSpine.centerline[anchors.tunnelSpine.centerline.length - 1]) < 0.045))
            );
            this.pushOutOfCapsule2D(v, seg.a, seg.b, seg.radius + tunnelMargin, isOpenA, isOpenB);
          }
        } else if (anchors.tunnelBoxes && anchors.tunnelBoxes.length > 0) {
          this.pushOutOfTunnelBoxes(v, anchors.tunnelBoxes, 0.036);
        } else if (anchors.tunnelBox) {
          this.pushOutOfBox2D(v, anchors.tunnelBox, 0.036);
        }
      }
    }
    return v;
  }

  private clampFloor(
    v: THREE.Vector3,
    anchors: HabitatPropAnchors,
    petState?: PetState | null
  ): THREE.Vector3 {
    this.pushOutOfProps(v, anchors, petState);
    v.x = THREE.MathUtils.clamp(v.x, -0.415, 0.415);
    v.z = THREE.MathUtils.clamp(v.z, -0.195, 0.216);
    v.y = this.sampleGroundY(v.x, v.z, anchors);
    return v;
  }

  private mapServerPos(petState: PetState, anchors: HabitatPropAnchors): THREE.Vector3 {
    // Backend uses Blender Z-up [x, y, z]; Three.js uses Y-up [x, z, -y]
    const bx = petState.position_xyz[0] ?? 0.145;
    const by = petState.position_xyz[1] ?? 0.032;
    return this.clampFloor(new THREE.Vector3(bx, anchors.beddingY, -by), anchors, petState);
  }

  private getWheelEntryPos(anchors: HabitatPropAnchors): THREE.Vector3 {
    // Upright wheel is open on its +Z front face (z = -0.085); stand cleanly outside wheelBox + margin
    const zEntry = anchors.wheelBox ? anchors.wheelBox.max.z + 0.055 : anchors.wheelPos.z + 0.11;
    return this.clampFloor(
      new THREE.Vector3(anchors.wheelPos.x, anchors.beddingY, Math.min(0.15, zEntry)),
      anchors
    );
  }

  private getHideoutDoorPos(anchors: HabitatPropAnchors): THREE.Vector3 {
    // Follow the exact rotated +Z arched doorway normal of prop_hideout (-16 deg in cage.glb)
    if (anchors.hideoutHalfExtents) {
      const yaw = anchors.hideoutYaw ?? -0.27925;
      const distOut = anchors.hideoutHalfExtents.hz + 0.058;
      const dx = Math.sin(yaw) * distOut;
      const dz = Math.cos(yaw) * distOut;
      const tx = anchors.hideoutPos.x + dx;
      const tz = anchors.hideoutPos.z + dz;
      return new THREE.Vector3(tx, this.sampleGroundY(tx, tz, anchors), tz);
    }
    const zDoor = anchors.hideoutBox ? anchors.hideoutBox.max.z + 0.048 : anchors.hideoutPos.z + 0.132;
    return this.clampFloor(
      new THREE.Vector3(anchors.hideoutPos.x - 0.025, anchors.beddingY, zDoor),
      anchors
    );
  }

  private getBowlApproachPos(anchors: HabitatPropAnchors): THREE.Vector3 {
    return this.clampFloor(
      new THREE.Vector3(anchors.bowlPos.x - 0.088, anchors.beddingY, anchors.bowlPos.z + 0.005),
      anchors
    );
  }

  private getWaterApproachPos(anchors: HabitatPropAnchors): THREE.Vector3 {
    return this.clampFloor(
      new THREE.Vector3(anchors.spoutPos.x - 0.068, anchors.beddingY, anchors.spoutPos.z + 0.012),
      anchors
    );
  }

  private getCozyCornerPos(anchors: HabitatPropAnchors): THREE.Vector3 {
    const corners: Array<[number, number]> = [
      [-0.36, 0.145],  // Front-left cozy corner (in front of wheel)
      [-0.04, -0.172], // Back-middle cozy nook (behind the bigger bark log, between wheel & house)
      [-0.16, 0.148],  // Front-center viewing nook
      [0.37, 0.160],   // Front-right corner beside food bowl
    ];
    // Prefer a corner distinct from current position
    const shuffled = corners.slice().sort(() => this.nextRand() - 0.5);
    for (const [cx, cz] of shuffled) {
      if (Math.hypot(cx - this.pos.x, cz - this.pos.z) > 0.10 && !this.isInsideAnyObstacle(cx, cz, anchors)) {
        return new THREE.Vector3(cx, this.sampleGroundY(cx, cz, anchors), cz);
      }
    }
    return this.clampFloor(new THREE.Vector3(-0.36, anchors.beddingY, 0.135), anchors);
  }

  private getWheelTrackPos(anchors: HabitatPropAnchors): THREE.Vector3 {
    const trackY = anchors.wheelTrackY ?? anchors.beddingY + 0.018;
    return new THREE.Vector3(anchors.wheelPos.x, trackY, anchors.wheelPos.z + 0.006);
  }

  private isInsideAnyObstacle(x: number, z: number, anchors: HabitatPropAnchors): boolean {
    const prevExitH = this.exitingHideout;
    const prevExitW = this.exitingWheel;
    const prevGoal = this.goal;
    const prevStage = this.goalStage;
    this.exitingHideout = false;
    this.exitingWheel = false;
    this.goal = "wander";
    this.goalStage = "approach";
    const probe = new THREE.Vector3(x, anchors.beddingY, z);
    const beforeX = probe.x;
    const beforeZ = probe.z;
    this.pushOutOfProps(probe, anchors, null);
    this.exitingHideout = prevExitH;
    this.exitingWheel = prevExitW;
    this.goal = prevGoal;
    this.goalStage = prevStage;
    return Math.hypot(probe.x - beforeX, probe.z - beforeZ) > 0.005;
  }

  private segmentIsClear(ax: number, az: number, bx: number, bz: number, anchors: HabitatPropAnchors): boolean {
    const dist = Math.hypot(bx - ax, bz - az);
    const steps = Math.max(2, Math.ceil(dist / 0.025));
    for (let i = 1; i < steps; i++) {
      const t = i / steps;
      const x = ax + (bx - ax) * t;
      const z = az + (bz - az) * t;
      if (this.isInsideAnyObstacle(x, z, anchors)) return false;
    }
    return true;
  }

  private computeDijkstraPath(
    startX: number,
    startZ: number,
    dest: THREE.Vector3,
    anchors: HabitatPropAnchors
  ): THREE.Vector3[] {
    if (this.segmentIsClear(startX, startZ, dest.x, dest.z, anchors)) {
      return [dest.clone()];
    }

    // Distance-weighted Dijkstra over a cage-wide open lattice + key back/front/side corridors
    // so the middle log, hideout, wheel, bowl, or dropped props NEVER block or clip movement.
    const candidates: Array<{ x: number; z: number }> = [
      { x: -0.36, z: 0.150 },
      { x: -0.26, z: 0.150 },
      { x: -0.15, z: 0.150 },
      { x: -0.055, z: 0.195 },
      { x: -0.050, z: 0.215 },
      { x: 0.050, z: 0.215 },
      { x: 0.162, z: 0.215 },
      { x: 0.168, z: 0.155 },
      { x: 0.18, z: 0.095 },
      { x: 0.16, z: 0.022 },
      { x: 0.135, z: -0.055 },
      { x: 0.125, z: -0.154 },
      { x: 0.120, z: -0.178 },
      { x: 0.04, z: -0.178 },
      { x: -0.04, z: -0.178 },
      { x: -0.105, z: -0.178 },
      { x: 0.04, z: -0.154 },
      { x: -0.04, z: -0.154 },
      { x: -0.105, z: -0.154 },
      { x: -0.115, z: -0.115 },
      { x: -0.24, z: -0.025 },
      { x: -0.26, z: 0.055 },
      { x: -0.26, z: 0.110 },
      { x: 0.24, z: 0.022 },
      { x: 0.27, z: 0.022 },
      { x: 0.31, z: 0.028 },
      { x: 0.355, z: 0.032 },
      { x: 0.37, z: 0.155 },
    ];
    for (let gx = -0.36; gx <= 0.37; gx += 0.11) {
      for (let gz = -0.156; gz <= 0.156; gz += 0.075) {
        candidates.push({ x: Number(gx.toFixed(3)), z: Number(gz.toFixed(3)) });
      }
    }
    if (anchors.tunnelSpine) {
      candidates.push(
        { x: anchors.tunnelSpine.mouthAApproach.x, z: anchors.tunnelSpine.mouthAApproach.z },
        { x: anchors.tunnelSpine.mouthBApproach.x, z: anchors.tunnelSpine.mouthBApproach.z },
        { x: anchors.tunnelSpine.climbEntryPos.x, z: anchors.tunnelSpine.climbEntryPos.z },
        { x: anchors.tunnelSpine.climbExitPos.x, z: anchors.tunnelSpine.climbExitPos.z }
      );
    }

    const nodes: Array<{ x: number; z: number }> = [{ x: startX, z: startZ }];
    for (const c of candidates) {
      if (!this.isInsideAnyObstacle(c.x, c.z, anchors)) {
        nodes.push(c);
      }
    }
    nodes.push({ x: dest.x, z: dest.z });

    const n = nodes.length;
    const startIdx = 0;
    const goalIdx = n - 1;
    const distArr = new Array<number>(n).fill(Infinity);
    const parent = new Array<number>(n).fill(-1);
    const settled = new Array<boolean>(n).fill(false);
    distArr[startIdx] = 0;

    for (let iter = 0; iter < n; iter++) {
      let u = -1;
      let bestD = Infinity;
      for (let i = 0; i < n; i++) {
        if (!settled[i] && distArr[i] < bestD) {
          bestD = distArr[i];
          u = i;
        }
      }
      if (u === -1 || u === goalIdx) break;
      settled[u] = true;

      for (let v = 1; v < n; v++) {
        if (settled[v]) continue;
        const stepLen = Math.hypot(nodes[v].x - nodes[u].x, nodes[v].z - nodes[u].z);
        if (distArr[u] + stepLen >= distArr[v]) continue;
        if (this.segmentIsClear(nodes[u].x, nodes[u].z, nodes[v].x, nodes[v].z, anchors)) {
          distArr[v] = distArr[u] + stepLen;
          parent[v] = u;
        }
      }
    }

    if (parent[goalIdx] !== -1) {
      const path: THREE.Vector3[] = [];
      let cur = goalIdx;
      while (cur !== startIdx && cur !== -1) {
        const pt = nodes[cur];
        path.push(new THREE.Vector3(pt.x, this.sampleGroundY(pt.x, pt.z, anchors), pt.z));
        cur = parent[cur];
      }
      path.reverse();
      if (path.length > 0) return path;
    }

    return [dest.clone()];
  }

  private setGoalTargetWithTunnelCorridor(dest: THREE.Vector3, anchors: HabitatPropAnchors): void {
    this.waypointQueue = [];
    this.exitingHideout = false;
    this.exitingWheel = false;

    // If currently inside hideout and heading elsewhere, ALWAYS step straight out the open +Z doorway FIRST!
    if (this.goal !== "hideout" && this.isPhysicallyInsideHideout(anchors)) {
      const doorPos = this.getHideoutDoorPos(anchors);
      const restPath = this.computeDijkstraPath(doorPos.x, doorPos.z, dest, anchors);
      this.exitingHideout = true;
      this.targetPos.copy(doorPos);
      this.waypointQueue = restPath;
      return;
    }

    // If currently on the wheel and heading elsewhere, ALWAYS hop straight out the open +Z face FIRST!
    if (this.goal !== "wheel" && this.isPhysicallyOnWheel(anchors)) {
      const entryPos = this.getWheelEntryPos(anchors);
      const restPath = this.computeDijkstraPath(entryPos.x, entryPos.z, dest, anchors);
      this.exitingWheel = true;
      this.targetPos.copy(entryPos);
      this.waypointQueue = restPath;
      return;
    }

    const path = this.computeDijkstraPath(this.pos.x, this.pos.z, dest, anchors);
    this.targetPos.copy(path[0]);
    this.waypointQueue = path.slice(1);
  }

  public startTunnelTraversal(anchors: HabitatPropAnchors, preferredForward?: boolean | null): void {
    if (!anchors.tunnelSpine) return;
    this.goal = "tunnel_through";
    this.waypointQueue = [];

    if (preferredForward === undefined || preferredForward === null) {
      const dA = Math.hypot(
        this.pos.x - anchors.tunnelSpine.mouthAApproach.x,
        this.pos.z - anchors.tunnelSpine.mouthAApproach.z
      );
      const dB = Math.hypot(
        this.pos.x - anchors.tunnelSpine.mouthBApproach.x,
        this.pos.z - anchors.tunnelSpine.mouthBApproach.z
      );
      this.tunnelDirectionForward = dA <= dB;
    } else {
      this.tunnelDirectionForward = preferredForward;
    }

    const entryApproach = this.tunnelDirectionForward
      ? anchors.tunnelSpine.mouthAApproach
      : anchors.tunnelSpine.mouthBApproach;

    const distToEntry = Math.hypot(this.pos.x - entryApproach.x, this.pos.z - entryApproach.z);
    if (distToEntry < 0.08) {
      this.goalStage = "active";
      const spinePts = this.tunnelDirectionForward
        ? [...anchors.tunnelSpine.centerline, anchors.tunnelSpine.mouthBApproach]
        : [...anchors.tunnelSpine.centerline.slice().reverse(), anchors.tunnelSpine.mouthAApproach];
      this.logActivePath = spinePts.map((pt) => pt.clone());
      this.logPathIndex = 0;
      this.targetPos.copy(this.logActivePath[0]);
      this.enterPhase("scurry", 12.0);
    } else {
      this.goalStage = "approach";
      this.setGoalTargetWithTunnelCorridor(entryApproach, anchors);
      this.enterPhase("scurry", 14.0);
    }
  }

  private findPropApproachPoint(prop: PlacedPropAnchor, anchors: HabitatPropAnchors): THREE.Vector3 {
    const standoff = Math.max(0.068, prop.radius + 0.048);
    let best: THREE.Vector3 | null = null;
    let bestDist = Infinity;
    for (let i = 0; i < 12; i++) {
      const ang = (i / 12) * Math.PI * 2;
      const cx = prop.pos.x + Math.cos(ang) * standoff;
      const cz = prop.pos.z + Math.sin(ang) * standoff;
      if (cx < -0.41 || cx > 0.41 || cz < -0.195 || cz > 0.195) continue;
      if (this.isInsideAnyObstacle(cx, cz, anchors)) continue;
      const d = Math.hypot(cx - this.pos.x, cz - this.pos.z);
      if (d < bestDist) {
        bestDist = d;
        best = new THREE.Vector3(cx, this.sampleGroundY(cx, cz, anchors), cz);
      }
    }
    if (best) return best;
    const dx = this.pos.x - prop.pos.x;
    const dz = this.pos.z - prop.pos.z;
    const len = Math.hypot(dx, dz) || 1;
    return this.clampFloor(
      new THREE.Vector3(prop.pos.x + (dx / len) * standoff, anchors.beddingY, prop.pos.z + (dz / len) * standoff),
      anchors
    );
  }

  private syncPlacedPropSensing(anchors: HabitatPropAnchors): void {
    const props = anchors.placedProps ?? [];
    const currentIds = new Set<string>();
    for (const p of props) {
      currentIds.add(p.objectId);
      const sig = `${p.pos.x.toFixed(2)},${p.pos.z.toFixed(2)},${p.rotationY.toFixed(2)}`;
      const prevSig = this.knownPropSignatures.get(p.objectId);
      if (this.hasInitializedProps && prevSig !== sig) {
        if (!this.pendingInspectQueue.includes(p.objectId)) {
          this.pendingInspectQueue.push(p.objectId);
        }
      }
      this.knownPropSignatures.set(p.objectId, sig);
    }
    for (const id of Array.from(this.knownPropSignatures.keys())) {
      if (!currentIds.has(id)) {
        this.knownPropSignatures.delete(id);
      }
    }
    this.pendingInspectQueue = this.pendingInspectQueue.filter((id) => currentIds.has(id));
    if (this.activeInspectProp && !currentIds.has(this.activeInspectProp.objectId)) {
      this.activeInspectProp = null;
    }
    this.hasInitializedProps = true;
  }

  private startInspectPropGoal(prop: PlacedPropAnchor, isNew: boolean, anchors: HabitatPropAnchors): void {
    this.goal = "inspect_prop";
    this.goalStage = "approach";
    this.activeInspectProp = prop;
    this.activeInspectIsNew = isNew;
    this.faceTargetPos = prop.pos.clone();
    const approach = this.findPropApproachPoint(prop, anchors);
    this.setGoalTargetWithTunnelCorridor(approach, anchors);
  }

  private chooseNextGoalAndTarget(
    anchors: HabitatPropAnchors,
    latestSkill: string | null,
    petState?: PetState | null
  ): void {
    this.faceTargetPos = null;
    this.waypointQueue = [];

    if (anchors.offeredFoodTarget) {
      this.goal = "bowl";
      this.goalStage = "approach";
      this.activeFoodObjectId = anchors.offeredFoodTarget.objectId;
      this.heldFoodItemId = anchors.offeredFoodTarget.itemId;
      this.faceTargetPos = anchors.offeredFoodTarget.pos.clone();
      this.setGoalTargetWithTunnelCorridor(this.getBowlApproachPos(anchors), anchors);
      return;
    }

    if (this.pendingInspectQueue.length > 0 && anchors.placedProps?.length) {
      const nextId = this.pendingInspectQueue.shift()!;
      const prop = anchors.placedProps.find((p) => p.objectId === nextId);
      if (prop) {
        this.startInspectPropGoal(prop, true, anchors);
        return;
      }
    }

    const activeSkill = this.serverSkillConsumed ? null : latestSkill;

    if (
      (anchors.hasBowl ?? true) &&
      (activeSkill === "eat" ||
        activeSkill === "approach_food" ||
        activeSkill === "cheek_stuffing" ||
        activeSkill === "hoard")
    ) {
      this.goal = "bowl";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.bowlPos.clone();
      this.setGoalTargetWithTunnelCorridor(this.getBowlApproachPos(anchors), anchors);
      return;
    }
    if (activeSkill === "drink") {
      this.goal = "water";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.spoutPos.clone();
      this.setGoalTargetWithTunnelCorridor(this.getWaterApproachPos(anchors), anchors);
      return;
    }
    if (
      (anchors.hasHideout ?? true) &&
      (activeSkill === "nesting" ||
        activeSkill === "hide" ||
        activeSkill === "unload_hoard" ||
        activeSkill === "avoid_and_retreat" ||
        (activeSkill === "rest" && (petState?.inside_hideout ?? true)))
    ) {
      this.goal = "hideout";
      this.goalStage = "approach";
      this.setGoalTargetWithTunnelCorridor(this.getHideoutDoorPos(anchors), anchors);
      return;
    }
    if (activeSkill === "rest" && petState && !petState.inside_hideout) {
      this.goal = "corner_sit";
      this.goalStage = "approach";
      this.setGoalTargetWithTunnelCorridor(this.mapServerPos(petState, anchors), anchors);
      return;
    }
    if (
      (anchors.hasWheel ?? true) &&
      (activeSkill === "run_on_wheel" || activeSkill === "wheel_run") &&
      this.goal !== "wheel"
    ) {
      this.goal = "wheel";
      this.goalStage = "approach";
      this.goalCyclesLeft = 2;
      this.setGoalTargetWithTunnelCorridor(this.getWheelEntryPos(anchors), anchors);
      return;
    }
    if (activeSkill === "cautious_sniff" || activeSkill === "accept_petting") {
      this.goal = "wander";
      this.goalStage = "approach";
      const frontTarget = this.clampFloor(new THREE.Vector3(0.0, anchors.beddingY, 0.145), anchors, petState);
      this.faceTargetPos = new THREE.Vector3(0.0, anchors.beddingY + 0.04, 0.24);
      this.setGoalTargetWithTunnelCorridor(frontTarget, anchors);
      return;
    }
    if ((anchors.hasChew ?? true) && activeSkill === "gnaw") {
      this.goal = "chew";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.chewPos.clone();
      this.setGoalTargetWithTunnelCorridor(
        this.clampFloor(new THREE.Vector3(anchors.chewPos.x - 0.058, anchors.beddingY, anchors.chewPos.z + 0.015), anchors, petState),
        anchors
      );
      return;
    }
    if (activeSkill === "digging" || activeSkill === "hind_leg_standing" || activeSkill === "grooming") {
      this.goal = "corner_sit";
      this.goalStage = "approach";
      const targetPt = petState ? this.mapServerPos(petState, anchors) : this.getCozyCornerPos(anchors);
      this.setGoalTargetWithTunnelCorridor(targetPt, anchors);
      return;
    }

    // Autonomous habitat goal selection (works offline / between server updates)
    // Uses biological novelty/satiation weighting so Hammy naturally cycles across ALL cage enrichments!
    const energy = petState?.drives.energy ?? 0.7;
    const hunger = petState?.drives.hunger ?? 0.35;
    const thirst = petState?.drives.thirst ?? 0.3;
    const hasFunctionalLog = Boolean((anchors.hasTunnel ?? true) && anchors.tunnelSpine);

    if (hasFunctionalLog && anchors.tunnelSpine && activeSkill === "enter_tunnel") {
      this.startTunnelTraversal(anchors, null);
      return;
    }

    const candidates: Array<{ goal: HabitatGoal; weight: number }> = [
      { goal: "water", weight: 0.48 + thirst * 0.28 },
      { goal: "corner_sit", weight: 0.46 },
      { goal: "wander", weight: 0.34 },
    ];
    if (anchors.hasHideout ?? true) {
      candidates.push({ goal: "hideout", weight: energy < 0.35 ? 1.25 : 0.45 });
    }
    if (anchors.hasWheel ?? true) {
      candidates.push({ goal: "wheel", weight: 0.62 });
    }
    if (anchors.hasBowl ?? true) {
      candidates.push({ goal: "bowl", weight: 0.50 + hunger * 0.28 });
    }
    if (hasFunctionalLog) {
      candidates.push({ goal: "tunnel_through", weight: 0.56 });
      candidates.push({ goal: "log_climb", weight: 0.52 });
    }
    if (anchors.hasChew ?? true) {
      candidates.push({ goal: "chew", weight: 0.30 });
    }
    if (anchors.placedProps && anchors.placedProps.length > 0) {
      candidates.push({ goal: "inspect_prop", weight: 0.42 });
    }

    let pickedGoal: HabitatGoal = "wander";
    let bestScore = -Infinity;
    for (const c of candidates) {
      if (c.goal === this.goal) continue;
      const lastIdx = this.recentGoals.lastIndexOf(c.goal);
      // Unvisited goals get strong natural curiosity/novelty pull; recently visited ones cool down
      const recencyPenalty = lastIdx === -1 ? 0.58 : (this.recentGoals.length - 1 - lastIdx) * 0.09;
      const score = c.weight + recencyPenalty + this.nextRand() * 0.42;
      if (score > bestScore) {
        bestScore = score;
        pickedGoal = c.goal;
      }
    }
    this.recentGoals.push(pickedGoal);
    if (this.recentGoals.length > 7) this.recentGoals.shift();

    if (pickedGoal === "hideout") {
      this.goal = "hideout";
      this.goalStage = "approach";
      this.setGoalTargetWithTunnelCorridor(this.getHideoutDoorPos(anchors), anchors);
      return;
    }
    if (pickedGoal === "wheel") {
      this.goal = "wheel";
      this.goalStage = "approach";
      this.goalCyclesLeft = 2 + Math.floor(this.nextRand() * 2);
      this.setGoalTargetWithTunnelCorridor(this.getWheelEntryPos(anchors), anchors);
      return;
    }
    if (pickedGoal === "tunnel_through" && anchors.tunnelSpine) {
      this.startTunnelTraversal(anchors, null);
      return;
    }
    if (pickedGoal === "log_climb" && anchors.tunnelSpine) {
      this.goal = "log_climb";
      this.goalStage = "approach";
      this.setGoalTargetWithTunnelCorridor(anchors.tunnelSpine.climbEntryPos, anchors);
      return;
    }
    if (pickedGoal === "bowl") {
      this.goal = "bowl";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.bowlPos.clone();
      this.setGoalTargetWithTunnelCorridor(this.getBowlApproachPos(anchors), anchors);
      return;
    }
    if (pickedGoal === "water") {
      this.goal = "water";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.spoutPos.clone();
      this.setGoalTargetWithTunnelCorridor(this.getWaterApproachPos(anchors), anchors);
      return;
    }
    if (pickedGoal === "corner_sit") {
      this.goal = "corner_sit";
      this.goalStage = "approach";
      this.setGoalTargetWithTunnelCorridor(this.getCozyCornerPos(anchors), anchors);
      return;
    }
    if (pickedGoal === "chew") {
      this.goal = "chew";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.chewPos.clone();
      this.setGoalTargetWithTunnelCorridor(
        this.clampFloor(new THREE.Vector3(anchors.chewPos.x - 0.058, anchors.beddingY, anchors.chewPos.z + 0.015), anchors, petState),
        anchors
      );
      return;
    }
    if (pickedGoal === "inspect_prop" && anchors.placedProps && anchors.placedProps.length > 0) {
      const pick = anchors.placedProps[Math.floor(this.nextRand() * anchors.placedProps.length)];
      if (pick) {
        this.startInspectPropGoal(pick, false, anchors);
        return;
      }
    }

    // Open-bedding exploration (avoiding all tunnel pipes & props)
    this.goal = "wander";
    this.goalStage = "approach";
    const base = petState ? this.mapServerPos(petState, anchors) : this.pos;
    for (let attempt = 0; attempt < 10; attempt++) {
      const rx = attempt < 5 ? base.x + (this.nextRand() * 2 - 1) * 0.22 : (this.nextRand() * 2 - 1) * 0.36;
      const rz = attempt < 5 ? base.z + (this.nextRand() * 2 - 1) * 0.14 : (this.nextRand() * 2 - 1) * 0.15;
      const cx = THREE.MathUtils.clamp(rx, -0.38, 0.38);
      const cz = THREE.MathUtils.clamp(rz, -0.155, 0.155);
      if (!this.isInsideAnyObstacle(cx, cz, anchors)) {
        this.setGoalTargetWithTunnelCorridor(new THREE.Vector3(cx, this.sampleGroundY(cx, cz, anchors), cz), anchors);
        return;
      }
    }
    this.targetPos.copy(this.clampFloor(new THREE.Vector3(-0.08, anchors.beddingY, 0.12), anchors, petState));
  }

  private enterPhase(next: MicroPhase, duration: number): void {
    this.prevPhase = this.phase;
    this.phase = next;
    this.phaseTimer = duration;
    this.headSaccadeTimer = 0.05;
    if (next !== "forage_eat") {
      this.isHoldingFood = false;
    }
    if (next === "wheel_pause") {
      this.wheelPauseElapsed = 0;
    }
  }

  private choosePauseBehavior(
    latestSkill: string | null,
    petState: PetState | null | undefined,
    anchors: HabitatPropAnchors
  ): void {
    const energy = petState?.drives.energy ?? 0.7;
    const curiosity = petState?.drives.curiosity ?? 0.5;
    const stress = petState?.drives.stress ?? 0.2;

    if (anchors.offeredFoodTarget) {
      const fPos = anchors.offeredFoodTarget.pos;
      const distToFood = Math.hypot(this.pos.x - fPos.x, this.pos.z - fPos.z);
      const distToBowl = Math.hypot(this.pos.x - anchors.bowlPos.x, this.pos.z - anchors.bowlPos.z);
      if (distToFood < 0.22 || distToBowl < 0.19) {
        this.goalStage = "active";
        this.faceTargetPos = fPos.clone();
        this.activeFoodObjectId = anchors.offeredFoodTarget.objectId;
        this.heldFoodItemId = anchors.offeredFoodTarget.itemId;
        this.hasTriggeredEatCallback = false;
        this.enterPhase("forage_eat", 4.2);
        return;
      }
    }

    const distToBowl2D = Math.hypot(this.pos.x - anchors.bowlPos.x, this.pos.z - anchors.bowlPos.z);
    if ((anchors.hasBowl ?? true) && (this.goal === "bowl" || latestSkill === "eat" || latestSkill === "cheek_stuffing" || latestSkill === "hoard") && distToBowl2D < 0.16) {
      this.goalStage = "active";
      this.faceTargetPos = anchors.bowlPos.clone();
      const bowlFoodLevel = anchors.foodLevel ?? 1.0;
      if (bowlFoodLevel > 0.01) {
        this.activeFoodObjectId = null;
        this.heldFoodItemId = "food_seed_mix";
        this.hasTriggeredEatCallback = false;
        this.enterPhase("forage_eat", 3.8 + this.nextRand() * 2.4);
      } else {
        this.isHoldingFood = false;
        this.enterPhase("sniff", 2.0);
      }
      return;
    }
    if (
      (this.goal === "water" || latestSkill === "drink") &&
      Math.hypot(this.pos.x - anchors.spoutPos.x, this.pos.z - anchors.spoutPos.z) < 0.15
    ) {
      this.goalStage = "active";
      this.faceTargetPos = anchors.spoutPos.clone();
      const bottleWaterLevel = anchors.waterLevel ?? 0.75;
      if (bottleWaterLevel > 0.01) {
        this.hasTriggeredDrinkCallback = false;
        this.enterPhase("drink", 3.2 + this.nextRand() * 2.2);
      } else {
        this.enterPhase("sniff", 1.8);
      }
      return;
    }
    if (this.goal === "inspect_prop" && this.activeInspectProp) {
      const distToProp = Math.hypot(
        this.pos.x - this.activeInspectProp.pos.x,
        this.pos.z - this.activeInspectProp.pos.z
      );
      if (distToProp < this.activeInspectProp.radius + 0.16) {
        this.goalStage = "active";
        this.faceTargetPos = this.activeInspectProp.pos.clone();
        this.enterPhase("inspect_prop", 3.6 + this.nextRand() * 1.8);
        return;
      }
    }

    if ((this.goal === "chew" || latestSkill === "gnaw") && this.pos.distanceTo(anchors.chewPos) < 0.13) {
      this.goalStage = "active";
      this.faceTargetPos = anchors.chewPos.clone();
      this.enterPhase("gnaw", 3.2 + this.nextRand() * 2.6);
      return;
    }

    // Direct mapping for learned cognitive skills arriving at target pause phase
    if (this.goal === "corner_sit") {
      // Face comfortably into the open cage while sitting in a cozy corner
      this.faceTargetPos = new THREE.Vector3(0.0, anchors.beddingY, 0.02);
      if (latestSkill === "rest") {
        this.enterPhase("rest", 4.5 + this.nextRand() * 2.5);
        return;
      }
      if (latestSkill === "hind_leg_standing") {
        this.enterPhase("rear_up", 2.8 + this.nextRand() * 1.8);
        return;
      }
      if (latestSkill === "grooming") {
        this.enterPhase("groom", 3.6 + this.nextRand() * 2.2);
        return;
      }
      if (latestSkill === "digging") {
        this.enterPhase("dig", 2.8 + this.nextRand() * 1.8);
        return;
      }
      const rc = this.nextRand();
      if (rc < 0.38) this.enterPhase("rest", 3.6 + this.nextRand() * 2.4);
      else if (rc < 0.70) this.enterPhase("groom", 3.2 + this.nextRand() * 2.0);
      else this.enterPhase("rear_up", 2.4 + this.nextRand() * 1.6);
      return;
    }
    if (latestSkill === "hind_leg_standing") {
      this.enterPhase("rear_up", 2.8 + this.nextRand() * 1.8);
      return;
    }
    if (latestSkill === "grooming") {
      this.enterPhase("groom", 3.6 + this.nextRand() * 2.4);
      return;
    }
    if (latestSkill === "digging") {
      this.enterPhase("dig", 2.8 + this.nextRand() * 2.0);
      return;
    }
    if (latestSkill === "cautious_sniff" || latestSkill === "accept_petting") {
      this.enterPhase("sniff", 3.2 + this.nextRand() * 2.0);
      return;
    }

    // Naturalistic ethogram transitions calibrated to real video stop-start timing
    const r = this.nextRand();
    if (energy < 0.25 && r < 0.45) {
      this.enterPhase("rest", 5.0 + this.nextRand() * 4.0);
      return;
    }
    if ((this.prevPhase === "forage_eat" || this.prevPhase === "dig") && r < 0.55) {
      this.enterPhase("groom", 3.5 + this.nextRand() * 2.8);
      return;
    }

    const rearProb = 0.24 + curiosity * 0.16 + stress * 0.15;
    const groomProb = rearProb + 0.18;
    const digProb = groomProb + (petState?.inside_tunnel ? 0.05 : 0.16 + curiosity * 0.08);

    if (r < rearProb) {
      this.enterPhase("rear_up", 2.4 + this.nextRand() * 2.2);
    } else if (r < groomProb) {
      this.enterPhase("groom", 3.4 + this.nextRand() * 2.8);
    } else if (r < digProb) {
      this.enterPhase("dig", 2.2 + this.nextRand() * 1.8);
    } else {
      this.enterPhase("sniff", 2.0 + this.nextRand() * 2.2);
    }
  }

  private updateHeadSaccade(dt: number, yawRange: number, pitchBase: number, pitchRange: number, rollRange: number): void {
    this.headSaccadeTimer -= dt;
    if (this.headSaccadeTimer <= 0) {
      this.headSaccadeTimer = 0.70 + this.nextRand() * 1.15;
      this.targetHeadYaw = (this.nextRand() * 2 - 1) * yawRange;
      this.targetHeadPitch = pitchBase + (this.nextRand() * 2 - 1) * pitchRange;
      this.targetHeadRoll = (this.nextRand() * 2 - 1) * rollRange;
    }
  }

  public update(
    dt: number,
    petState: PetState | null | undefined,
    latestEvent: WorldEvent | null | undefined,
    anchors: HabitatPropAnchors
  ): HamsterBehaviorStep {
    const clampedDt = Math.min(0.05, Math.max(0.001, dt));
    const latestSkill = petState?.active_skill || latestEvent?.skill_name || null;

    if (petState?.is_paused) {
      const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), this.yaw);
      return {
        pose: {
          rootPosition: [this.pos.x, this.pos.y, this.pos.z],
          rootQuaternion: [q.x, q.y, q.z, q.w],
          velocity: [0, 0, 0],
          angularVelocity: [0, 0, 0],
          footContacts: { fl: true, fr: true, bl: true, br: true },
          gaitPhase: this.gaitPhase,
          posture: { ...this.posture },
        },
        proceduralConfig: DEFAULT_PROCEDURAL_CONFIG,
        wheelSpinDelta: 0,
        activityLabel: "Paused",
      };
    }

    // Sense newly dropped or moved physical props in the cage and queue curious inspection
    this.syncPlacedPropSensing(anchors);
    const busyWithPriorityAction =
      Boolean(anchors.offeredFoodTarget) ||
      this.phase === "forage_eat" ||
      this.phase === "drink" ||
      ((this.goal === "tunnel_through" || this.goal === "log_climb" || this.goal === "wheel") &&
        this.goalStage === "active");
    if (this.pendingInspectQueue.length > 0 && !busyWithPriorityAction && anchors.placedProps?.length) {
      const nextId = this.pendingInspectQueue.shift()!;
      const prop = anchors.placedProps.find((p) => p.objectId === nextId);
      if (prop) {
        this.startInspectPropGoal(prop, true, anchors);
        this.enterPhase("scurry", 16.0);
      }
    }

    // Immediately redirect when new offeredFoodTarget appears in the cage
    if (anchors.offeredFoodTarget && anchors.offeredFoodTarget.objectId !== this.lastTrackedFoodObjectId) {
      this.lastTrackedFoodObjectId = anchors.offeredFoodTarget.objectId;
      this.activeFoodObjectId = anchors.offeredFoodTarget.objectId;
      this.heldFoodItemId = anchors.offeredFoodTarget.itemId;
      this.goal = "bowl";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.offeredFoodTarget.pos.clone();
      this.setGoalTargetWithTunnelCorridor(this.getBowlApproachPos(anchors), anchors);
      this.enterPhase("scurry", 14.0);
    } else if (!anchors.offeredFoodTarget) {
      this.lastTrackedFoodObjectId = null;
    }
    if (petState) {
      const posKey = `${petState.position_xyz[0]?.toFixed(2)},${petState.position_xyz[1]?.toFixed(2)},${petState.on_wheel},${petState.inside_hideout},${petState.inside_tunnel},${petState.active_skill ?? ""}`;
      if (posKey !== this.lastServerPosKey) {
        const isFirstSync = !this.hasSyncedServerOnce;
        this.hasSyncedServerOnce = true;
        this.lastServerPosKey = posKey;
        this.serverSkillConsumed = false;

        // Never abruptly interrupt an active crawl inside the hollow bark log!
        const currentlyMidLog =
          (this.goal === "tunnel_through" || this.goal === "log_climb") && this.goalStage === "active";
        if (!currentlyMidLog) {
          this.faceTargetPos = null;
          if (petState.on_wheel || petState.active_skill === "run_on_wheel") {
            this.goal = "wheel";
            this.goalCyclesLeft = 2;
            if (isFirstSync && petState.on_wheel) {
              // Already on the wheel at initial load
              this.pos.copy(this.getWheelTrackPos(anchors));
              this.goalStage = "active";
              this.targetPos.copy(this.getWheelTrackPos(anchors));
            } else if (this.isPhysicallyOnWheel(anchors)) {
              this.goalStage = "active";
              this.targetPos.copy(this.getWheelTrackPos(anchors));
            } else {
              // ALWAYS walk cleanly to the open +Z wheel front via Dijkstra before hopping on!
              this.goalStage = "approach";
              this.setGoalTargetWithTunnelCorridor(this.getWheelEntryPos(anchors), anchors);
            }
          } else if (
            petState.inside_hideout ||
            petState.active_skill === "hide" ||
            petState.active_skill === "nesting" ||
            petState.active_skill === "unload_hoard"
          ) {
            this.goal = "hideout";
            const hideoutFloorY = this.sampleGroundY(anchors.hideoutPos.x, anchors.hideoutPos.z, anchors) - 0.004;
            if (isFirstSync && petState.inside_hideout) {
              // Already curled inside hideout at initial page load (no wall clipping!)
              this.pos.set(anchors.hideoutPos.x, hideoutFloorY, anchors.hideoutPos.z);
              this.yaw = Math.PI * 0.5 + (anchors.hideoutYaw ?? -0.27925);
              this.goalStage = "active";
              this.targetPos.set(anchors.hideoutPos.x, hideoutFloorY, anchors.hideoutPos.z);
            } else if (this.isPhysicallyInsideHideout(anchors)) {
              this.goalStage = "active";
              this.targetPos.set(anchors.hideoutPos.x, hideoutFloorY, anchors.hideoutPos.z);
            } else {
              // ALWAYS route via Dijkstra to the arched +Z doorway FIRST before walking inside!
              this.goalStage = "approach";
              this.setGoalTargetWithTunnelCorridor(this.getHideoutDoorPos(anchors), anchors);
            }
          } else if (petState.inside_tunnel || petState.active_skill === "enter_tunnel") {
            if (anchors.tunnelSpine) {
              this.startTunnelTraversal(anchors, null);
            } else {
              this.goal = "wander";
              this.goalStage = "approach";
              this.setGoalTargetWithTunnelCorridor(this.mapServerPos(petState, anchors), anchors);
            }
          } else if (
            petState.active_skill === "eat" ||
            petState.active_skill === "approach_food" ||
            petState.active_skill === "cheek_stuffing"
          ) {
            this.goal = "bowl";
            this.goalStage = "approach";
            this.faceTargetPos = anchors.bowlPos.clone();
            this.setGoalTargetWithTunnelCorridor(this.getBowlApproachPos(anchors), anchors);
          } else if (petState.active_skill === "drink") {
            this.goal = "water";
            this.goalStage = "approach";
            this.faceTargetPos = anchors.spoutPos.clone();
            this.setGoalTargetWithTunnelCorridor(this.getWaterApproachPos(anchors), anchors);
          } else if (
            petState.active_skill === "rest" ||
            petState.active_skill === "hind_leg_standing" ||
            petState.active_skill === "grooming" ||
            petState.active_skill === "digging"
          ) {
            this.goal = "corner_sit";
            this.goalStage = "approach";
            this.setGoalTargetWithTunnelCorridor(this.mapServerPos(petState, anchors), anchors);
          } else if (petState.active_skill === "cautious_sniff" || petState.active_skill === "accept_petting") {
            this.goal = "wander";
            this.goalStage = "approach";
            const frontTarget = this.clampFloor(new THREE.Vector3(0.0, anchors.beddingY, 0.145), anchors, petState);
            this.faceTargetPos = new THREE.Vector3(0.0, anchors.beddingY + 0.04, 0.24);
            this.setGoalTargetWithTunnelCorridor(frontTarget, anchors);
          } else if (
            petState.active_skill === "explore_area" &&
            anchors.tunnelSpine &&
            this.nextRand() < 0.22
          ) {
            // Occasionally climb & periscope on top of the bark log when exploring!
            this.goal = "log_climb";
            this.goalStage = "approach";
            this.setGoalTargetWithTunnelCorridor(anchors.tunnelSpine.climbEntryPos, anchors);
          } else {
            this.goal = "wander";
            this.goalStage = "approach";
            this.setGoalTargetWithTunnelCorridor(this.mapServerPos(petState, anchors), anchors);
          }

          if (this.pos.distanceTo(this.targetPos) > 0.025 || this.waypointQueue.length > 0) {
            this.enterPhase("scurry", 16.0);
          } else if (petState.active_skill) {
            this.choosePauseBehavior(petState.active_skill, petState, anchors);
          }
        }
      }
    }

    const energy = petState?.drives.energy ?? 0.7;
    const stress = petState?.drives.stress ?? 0.2;
    const curiosity = petState?.drives.curiosity ?? 0.5;

    const distToTarget = Math.hypot(this.targetPos.x - this.pos.x, this.targetPos.z - this.pos.z);
    let targetSpeed = 0;
    let yawRate = 0;
    let wheelSpinDelta = 0;
    let activityLabel = "Sniffing";

    // Target posture values for this frame
    let targetRear = 0;
    let targetCrouch = 0;
    let targetCurl = 0;
    let targetGroom = 0;
    let targetEatHold = 0;
    let targetDig = 0;
    let targetChew = 0;

    const wheelTrackPos = this.getWheelTrackPos(anchors);
    const distToWheelTrack = Math.hypot(this.pos.x - wheelTrackPos.x, this.pos.z - wheelTrackPos.z);
    const distToHideout = Math.hypot(this.pos.x - anchors.hideoutPos.x, this.pos.z - anchors.hideoutPos.z);

    // STRICTLY require physically arriving at the wheel track / hideout interior (NEVER lerp through walls!)
    const onWheelActive =
      this.goal === "wheel" && this.goalStage === "active" && distToWheelTrack < 0.068;

    const insideHideoutActive =
      this.goal === "hideout" && this.goalStage === "active" && distToHideout < 0.055;

    if (onWheelActive) {
      // On wheel: fast bounding sprints + sudden pauses where wheel coasts/rocks
      const wheelTrack = this.getWheelTrackPos(anchors);
      this.pos.lerp(wheelTrack, Math.min(1, clampedDt * 8));
      const targetYaw = Math.PI * 0.5;
      const dYaw = shortestAngleDiff(this.yaw, targetYaw);
      this.yaw += dYaw * Math.min(1, clampedDt * 10);

      this.phaseTimer -= clampedDt;
      if (this.phase !== "wheel_run" && this.phase !== "wheel_pause") {
        this.wheelBurstSpeed = 0.30 + this.nextRand() * 0.14;
        this.enterPhase("wheel_run", 1.45 + this.nextRand() * 1.0);
      } else if (this.phaseTimer <= 0) {
        if (this.phase === "wheel_run") {
          this.wheelCoastVel = 5.4;
          this.enterPhase("wheel_pause", 0.9 + this.nextRand() * 1.1);
        } else if (!petState?.on_wheel && this.goal === "wheel") {
          if (this.goalCyclesLeft > 0) {
            this.goalCyclesLeft--;
            this.wheelBurstSpeed = 0.30 + this.nextRand() * 0.14;
            this.enterPhase("wheel_run", 1.6 + this.nextRand() * 1.3);
          } else {
            // Hop off wheel back to entry point
            this.goalStage = "exit";
            this.targetPos.copy(this.getWheelEntryPos(anchors));
            this.enterPhase("scurry", 2.5);
          }
        } else {
          this.wheelBurstSpeed = 0.30 + this.nextRand() * 0.14;
          this.enterPhase("wheel_run", 1.6 + this.nextRand() * 1.5);
        }
      }

      if (this.phase === "wheel_run") {
        // Calibrated to real hamster-video6.mp4 wheel running (2.09 Hz stride, ~0.13 m/s scaled)
        targetSpeed = 0.13 + this.wheelBurstSpeed * 0.15;
        this.gaitPhase += clampedDt * 13.1;
        wheelSpinDelta = clampedDt * 2.6;
        targetCrouch = 0.25;
        this.targetHeadYaw = 0;
        this.targetHeadPitch = -0.06;
        this.targetHeadRoll = 0;
        activityLabel = "Sprinting on Wheel";
      } else if (this.phase === "wheel_pause") {
        targetSpeed = 0;
        this.wheelPauseElapsed += clampedDt;
        // Damped wheel coasting + gentle pendulum rock
        this.wheelCoastVel *= Math.exp(-3.2 * clampedDt);
        const rock =
          this.wheelPauseElapsed < 1.3
            ? Math.sin(this.wheelPauseElapsed * 5.2) * Math.exp(-this.wheelPauseElapsed * 2.2) * 0.45
            : 0;
        wheelSpinDelta = (this.wheelCoastVel * 0.45 + rock) * clampedDt;
        this.updateHeadSaccade(clampedDt, 0.35, -0.05, 0.12, 0.08);
        activityLabel = "Catching Breath on Wheel";
      }
    } else if (insideHideoutActive) {
      this.pos.lerp(
        new THREE.Vector3(
          anchors.hideoutPos.x,
          this.sampleGroundY(anchors.hideoutPos.x, anchors.hideoutPos.z, anchors) - 0.004,
          anchors.hideoutPos.z
        ),
        Math.min(1, clampedDt * 5)
      );
      // Align curled body lengthwise along the hideout's wide 16cm X-axis so nose & rump never poke through wood walls!
      const hideoutSleepYaw = Math.PI * 0.5 + (anchors.hideoutYaw ?? -0.27925);
      const dSleepYaw = shortestAngleDiff(this.yaw, hideoutSleepYaw);
      this.yaw += dSleepYaw * Math.min(1, clampedDt * 5);
      this.phase = "rest";
      targetSpeed = 0;
      targetCurl = 0.96;
      this.targetHeadYaw = 0.14;
      this.targetHeadPitch = 0.28;
      this.targetHeadRoll = 0.08;
      activityLabel = "Curled Up in Hideout";

      if (!petState?.inside_hideout && this.goal === "hideout") {
        this.phaseTimer -= clampedDt;
        if (this.phaseTimer <= 0) {
          this.goalStage = "exit";
          this.targetPos.copy(this.getHideoutDoorPos(anchors));
          this.enterPhase("scurry", 3.5);
        }
      }
    } else {
      // Floor / Tunnel exploration & ethogram
      this.phaseTimer -= clampedDt;

      if (this.phase === "scurry") {
        // Occasional micro-freeze mid-scurry when alert/curious
        const distToSpout2D = Math.hypot(this.pos.x - anchors.spoutPos.x, this.pos.z - anchors.spoutPos.z);
        if (this.microFreezeTimer > 0) {
          this.microFreezeTimer -= clampedDt;
          targetSpeed = 0;
          targetCrouch = 0.3;
          this.updateHeadSaccade(clampedDt, 0.45, -0.08, 0.12, 0.1);
          activityLabel = "Alert Freeze";
        } else if (
          distToTarget <
          (((this.goal === "tunnel_through" || this.goal === "log_climb") &&
            (this.goalStage === "active" || this.goalStage === "exit"))
            ? 0.045
            : this.waypointQueue.length > 0
              ? 0.015
              : 0.025) ||
          (this.goal === "water" && distToSpout2D < 0.085 && this.waypointQueue.length === 0) ||
          this.phaseTimer <= 0
        ) {
          if (this.waypointQueue.length > 0 && distToTarget < 0.018) {
            // Once we have stepped cleanly out through the hideout door or wheel front, re-enable solid collision!
            if (this.exitingHideout) this.exitingHideout = false;
            if (this.exitingWheel) this.exitingWheel = false;
            this.targetPos.copy(this.waypointQueue.shift()!);
            this.stuckTimer = 0;
            this.stuckCheckPos.copy(this.pos);
            this.enterPhase("scurry", 14.0);
          } else {
            if (this.exitingHideout && distToTarget < 0.055) this.exitingHideout = false;
            if (this.exitingWheel && distToTarget < 0.055) this.exitingWheel = false;
            const arrived = distToTarget < 0.058;
            // Handle multi-stage prop transitions (wheel, hideout, hollow middle log, & log top climb)
            if (this.goal === "wheel" && this.goalStage === "approach") {
              if (arrived) {
                this.goalStage = "active";
                this.targetPos.copy(this.getWheelTrackPos(anchors));
                this.enterPhase("scurry", 4.5);
                activityLabel = "Hopping onto Wheel";
              } else {
                this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
                this.enterPhase("scurry", 16.0);
              }
            } else if (this.goal === "hideout" && this.goalStage === "approach") {
              if (arrived) {
                this.goalStage = "active";
                this.targetPos.set(
                  anchors.hideoutPos.x,
                  this.sampleGroundY(anchors.hideoutPos.x, anchors.hideoutPos.z, anchors) - 0.004,
                  anchors.hideoutPos.z
                );
                this.enterPhase("scurry", 4.5);
                this.phaseTimer = 4.5 + this.nextRand() * 3.0;
                activityLabel = "Entering Hideout";
              } else {
                this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
                this.enterPhase("scurry", 16.0);
              }
            } else if (this.goal === "tunnel_through" && anchors.tunnelSpine) {
              if (this.goalStage === "approach") {
                if (arrived) {
                  this.goalStage = "active";
                  const spinePts = this.tunnelDirectionForward
                    ? [...anchors.tunnelSpine.centerline, anchors.tunnelSpine.mouthBApproach]
                    : [...anchors.tunnelSpine.centerline.slice().reverse(), anchors.tunnelSpine.mouthAApproach];
                  this.logActivePath = spinePts.map((pt) => pt.clone());
                  this.logPathIndex = 0;
                  this.targetPos.copy(this.logActivePath[0]);
                  this.enterPhase("scurry", 12.0);
                  activityLabel = "Entering Hollow Log";
                } else {
                  this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
                  this.enterPhase("scurry", 16.0);
                }
              } else if (this.goalStage === "active") {
                if (this.logPathIndex + 1 < this.logActivePath.length) {
                  this.logPathIndex++;
                  this.targetPos.copy(this.logActivePath[this.logPathIndex]);
                  this.enterPhase("scurry", 8.0);
                  activityLabel =
                    this.logPathIndex === this.logActivePath.length - 1
                      ? "Exiting Hollow Log"
                      : "Crawling Through Hollow Log";
                } else {
                  this.goalStage = "exit";
                  this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
                  this.enterPhase("scurry", 14.0);
                }
              } else {
                this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
                this.enterPhase("scurry", 14.0);
              }
            } else if (this.goal === "log_climb" && anchors.tunnelSpine) {
              if (this.goalStage === "approach") {
                if (arrived) {
                  this.goalStage = "active";
                  this.logHasPerched = false;
                  this.logActivePath = [
                    ...anchors.tunnelSpine.topPath.map((pt) => pt.clone()),
                    anchors.tunnelSpine.climbExitPos.clone(),
                  ];
                  this.logPathIndex = 0;
                  this.targetPos.copy(this.logActivePath[0]);
                  this.enterPhase("scurry", 8.0);
                  activityLabel = "Climbing onto Log";
                } else {
                  this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
                  this.enterPhase("scurry", 16.0);
                }
              } else if (this.goalStage === "active") {
                const perchIdx = Math.floor(anchors.tunnelSpine.topPath.length / 2);
                if (!this.logHasPerched && this.logPathIndex === perchIdx) {
                  this.logHasPerched = true;
                  this.enterPhase("log_perch", 2.4 + this.nextRand() * 1.4);
                  activityLabel = "Periscoping on Top of Log";
                } else if (this.logPathIndex + 1 < this.logActivePath.length) {
                  this.logPathIndex++;
                  this.targetPos.copy(this.logActivePath[this.logPathIndex]);
                  this.enterPhase("scurry", 8.0);
                  activityLabel =
                    this.logPathIndex === this.logActivePath.length - 1
                      ? "Climbing Down from Log"
                      : "Walking on Top of Log";
                } else {
                  this.goalStage = "exit";
                  this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
                  this.enterPhase("scurry", 14.0);
                }
              } else {
                this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
                this.enterPhase("scurry", 14.0);
              }
            } else if (this.goalStage === "exit") {
              this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
              this.enterPhase("scurry", 14.0);
            } else {
              this.choosePauseBehavior(latestSkill, petState, anchors);
            }
          }
          targetSpeed = 0;
        } else {
          // Trigger occasional micro-freeze on open floor
          if (
            !petState?.inside_tunnel &&
            this.goalStage === "approach" &&
            distToTarget > 0.08 &&
            this.nextRand() < (0.005 + stress * 0.01)
          ) {
            this.microFreezeTimer = 0.22 + this.nextRand() * 0.26;
          }

          const dx = this.targetPos.x - this.pos.x;
          const dz = this.targetPos.z - this.pos.z;
          const desiredYaw = Math.atan2(dx, dz);
          const dYaw = shortestAngleDiff(this.yaw, desiredYaw);
          // Natural turning rate (~130 deg/s instead of robotic 487 deg/s)
          const turnStep = THREE.MathUtils.clamp(dYaw, -2.3 * clampedDt, 2.3 * clampedDt);
          this.yaw += turnStep;
          yawRate = turnStep / clampedDt;

          // Head leads the turn slightly, nose slightly down sniffing path
          this.targetHeadYaw = THREE.MathUtils.clamp(dYaw * 0.55, -0.48, 0.48);
          this.targetHeadPitch = 0.12;
          this.targetHeadRoll = THREE.MathUtils.clamp(-dYaw * 0.14, -0.12, 0.12);

          const isTraversingLog =
            (this.goal === "tunnel_through" || this.goal === "log_climb") &&
            (this.goalStage === "active" || this.goalStage === "exit");

          // Natural lively Syrian hamster scurry speed (0.14–0.18 m/s on open bedding)
          const alignScale = Math.max(0.35, Math.cos(Math.min(Math.abs(dYaw), Math.PI * 0.5)));
          const maxMoveSpeed =
            (petState?.inside_tunnel || isTraversingLog ? 0.12 : 0.145 + curiosity * 0.035) * alignScale;
          if (this.goal === "tunnel_through" && this.goalStage === "active") {
            targetCrouch = 0.85;
          }
          targetSpeed = maxMoveSpeed;
          const stepDist = Math.min(distToTarget, this.currentSpeed * clampedDt);
          const prevX = this.pos.x;
          const prevZ = this.pos.z;
          if (distToTarget > 1e-4) {
            this.pos.x += (dx / distToTarget) * stepDist;
            this.pos.z += (dz / distToTarget) * stepDist;
          }
          if (!isTraversingLog) {
            this.pushOutOfProps(this.pos, anchors, petState);
            // Smooth gentle tangential slide if grazing an obstacle: pick whichever tangent side gets closer to target!
            const moved = Math.hypot(this.pos.x - prevX, this.pos.z - prevZ);
            if (stepDist > 1e-4 && moved < stepDist * 0.35 && distToTarget > 1e-4) {
              const perpX = -dz / distToTarget;
              const perpZ = dx / distToTarget;
              const candA = this.pos.clone();
              candA.x += perpX * stepDist * 0.55;
              candA.z += perpZ * stepDist * 0.55;
              this.pushOutOfProps(candA, anchors, petState);
              const candB = this.pos.clone();
              candB.x -= perpX * stepDist * 0.55;
              candB.z -= perpZ * stepDist * 0.55;
              this.pushOutOfProps(candB, anchors, petState);
              const dA = Math.hypot(this.targetPos.x - candA.x, this.targetPos.z - candA.z);
              const dB = Math.hypot(this.targetPos.x - candB.x, this.targetPos.z - candB.z);
              this.pos.copy(dA <= dB ? candA : candB);
            }
            this.pos.x = THREE.MathUtils.clamp(this.pos.x, -0.415, 0.415);
            this.pos.z = THREE.MathUtils.clamp(this.pos.z, -0.195, 0.216);
          }

          // Calm stuck recovery: re-route cleanly around obstacles if blocked > 1.0s
          if (!isTraversingLog) {
            this.stuckTimer += clampedDt;
            if (this.stuckTimer >= 1.0) {
              const netMoved = Math.hypot(this.pos.x - this.stuckCheckPos.x, this.pos.z - this.stuckCheckPos.z);
              this.stuckCheckPos.copy(this.pos);
              this.stuckTimer = 0;
              if (netMoved < 0.015 && this.goalStage === "approach") {
                this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
                this.enterPhase("scurry", 16.0);
              }
            }
          } else {
            this.stuckTimer = 0;
          }

          // Smoothly track Y: elevated on wheel / top of log / inside hollow log, otherwise bedding height
          const groundY =
            this.goal === "wheel" && this.goalStage === "active"
              ? this.getWheelTrackPos(anchors).y
              : isTraversingLog
                ? this.targetPos.y
                : this.sampleGroundY(this.pos.x, this.pos.z, anchors);
          this.pos.y = THREE.MathUtils.lerp(this.pos.y, groundY, Math.min(1, clampedDt * 12));

          // Lock gait cadence to physical ground speed (real stride length ~0.055 m -> ~1.6-2.0 Hz)
          const strideLenM = 0.055;
          this.gaitPhase += clampedDt * (this.currentSpeed / strideLenM) * Math.PI * 2;
          activityLabel = petState?.inside_tunnel
            ? "Exploring Tunnel"
            : this.goal === "tunnel_through"
              ? this.goalStage === "active"
                ? this.logPathIndex === this.logActivePath.length - 1
                  ? "Exiting Hollow Log"
                  : "Crawling Through Hollow Log"
                : "Heading to Hollow Log"
              : this.goal === "log_climb"
                ? this.goalStage === "active"
                  ? this.logPathIndex === this.logActivePath.length - 1
                    ? "Climbing Down from Log"
                    : "Climbing on Top of Log"
                  : "Heading to Climb Log"
                : this.goal === "inspect_prop" && this.activeInspectProp
                  ? this.activeInspectIsNew
                    ? `Approaching New ${this.activeInspectProp.name}`
                    : `Heading to ${this.activeInspectProp.name}`
                  : this.goal === "wheel"
                    ? "Heading to Wheel"
                    : this.goal === "water"
                      ? "Heading to Water"
                      : this.goal === "hideout"
                        ? "Heading to Hideout"
                        : this.goal === "bowl"
                          ? "Heading to Food Bowl"
                          : this.goal === "corner_sit"
                            ? "Heading to Cozy Corner"
                            : this.goal === "chew"
                              ? "Heading to Chew Block"
                              : latestSkill
                                ? `Scurrying (${latestSkill.replace(/_/g, " ")})`
                                : "Scurrying";
        }
      } else {
        // Stationary / micro-behavior phases — stay flush with log top when perched, else local bedding
        const isTraversingLog =
          (this.goal === "tunnel_through" || this.goal === "log_climb") &&
          (this.goalStage === "active" || this.goalStage === "exit");
        if (!isTraversingLog && this.phase !== "log_perch") {
          this.pushOutOfProps(this.pos, anchors, petState);
          this.pos.x = THREE.MathUtils.clamp(this.pos.x, -0.415, 0.415);
          this.pos.z = THREE.MathUtils.clamp(this.pos.z, -0.195, 0.216);
        }
        const groundY =
          this.phase === "log_perch"
            ? this.targetPos.y
            : this.sampleGroundY(this.pos.x, this.pos.z, anchors);
        this.pos.y = THREE.MathUtils.lerp(this.pos.y, groundY, Math.min(1, clampedDt * 14));
        targetSpeed = 0;

        // Smoothly turn to face prop when drinking / eating / gnawing / inspecting
        if (this.faceTargetPos) {
          const fdx = this.faceTargetPos.x - this.pos.x;
          const fdz = this.faceTargetPos.z - this.pos.z;
          if (Math.hypot(fdx, fdz) > 1e-3) {
            const desiredFaceYaw = Math.atan2(fdx, fdz);
            const dFace = shortestAngleDiff(this.yaw, desiredFaceYaw);
            const turnStep = THREE.MathUtils.clamp(dFace, -2.4 * clampedDt, 2.4 * clampedDt);
            this.yaw += turnStep;
            yawRate = turnStep / clampedDt;
          }
        }

        if (this.phaseTimer <= 0) {
          if (this.phase === "log_perch" && this.goal === "log_climb" && this.logPathIndex + 1 < this.logActivePath.length) {
            // Continue climbing down off the log after periscoping on top
            this.logPathIndex++;
            this.targetPos.copy(this.logActivePath[this.logPathIndex]);
            this.enterPhase("scurry", 8.0);
            activityLabel = "Climbing Down from Log";
          } else {
            // Mark the current server skill as completed so Hammy doesn't repeat the same action until the next brain decision
            this.serverSkillConsumed = true;
            this.chooseNextGoalAndTarget(anchors, null, petState);
            this.enterPhase("scurry", 16.0);
            activityLabel = "Exploring";
          }
        } else {
          switch (this.phase) {
            case "log_perch": {
              targetRear = 0.72;
              this.updateHeadSaccade(clampedDt, 0.58, -0.14, 0.14, 0.14);
              activityLabel = "Periscoping on Top of Log";
              break;
            }
            case "inspect_prop": {
              const prop = this.activeInspectProp;
              const isChewLike = Boolean(prop && (prop.itemId.includes("chew") || prop.itemId.includes("ball")));
              if (isChewLike) {
                targetCrouch = 0.38;
                targetChew = 0.72;
                this.posture.chewPhase += clampedDt * 10.0;
                this.targetHeadYaw = Math.sin(this.posture.chewPhase * 0.25) * 0.14;
                this.targetHeadPitch = 0.16 + Math.sin(this.posture.chewPhase * 0.4) * 0.08;
                this.targetHeadRoll = 0.08;
                activityLabel = prop
                  ? `Sniffing & Nibbling ${prop.name}`
                  : "Sniffing New Prop";
              } else {
                // Curious mammal inspection: lower nose to sniff, then briefly rear up to size it up
                const periscopeMoment = this.phaseTimer > 1.3 && this.phaseTimer < 2.6;
                targetRear = periscopeMoment ? 0.56 : 0.08;
                targetCrouch = periscopeMoment ? 0 : 0.22;
                this.updateHeadSaccade(clampedDt, 0.36, periscopeMoment ? -0.10 : 0.18, 0.12, 0.12);
                activityLabel = prop
                  ? this.activeInspectIsNew
                    ? `Curiously Inspecting New ${prop.name}`
                    : `Inspecting ${prop.name}`
                  : "Curiously Inspecting Prop";
              }
              break;
            }
            case "rear_up": {
              targetRear = 0.88;
              this.updateHeadSaccade(clampedDt, 0.55, -0.18, 0.14, 0.16);
              activityLabel = "Periscoping (Alert)";
              break;
            }
            case "groom": {
              targetRear = 0.48;
              targetGroom = 1.0;
              targetChew = 0.35;
              this.posture.groomPhase += clampedDt * 11.0;
              this.posture.chewPhase += clampedDt * 9.0;
              this.targetHeadYaw = Math.sin(this.posture.groomPhase * 0.25) * 0.12;
              this.targetHeadPitch = 0.18;
              this.targetHeadRoll = Math.sin(this.posture.groomPhase * 0.2) * 0.14;
              activityLabel = "Washing Face";
              break;
            }
            case "forage_eat": {
              // Step 5/6 realistic eating: sits up on haunches, cradles food between both 4-fingered pink paws, chews, cheek pouches bulge
              targetRear = 0.66;
              targetEatHold = 1.0;
              targetGroom = 0.0;
              targetChew = 0.95;
              this.isHoldingFood = true;
              this.posture.chewPhase += clampedDt * 12.5;
              this.targetHeadYaw = Math.sin(this.posture.chewPhase * 0.15) * 0.08;
              this.targetHeadPitch = 0.14 + Math.sin(this.posture.chewPhase * 0.4) * 0.06;
              this.targetHeadRoll = 0;
              activityLabel = "Eating with Both Paws (ANIMATION-DRIVEN)";
              if (!this.hasTriggeredEatCallback && this.phaseTimer < 1.8 && anchors.onFoodConsumed) {
                this.hasTriggeredEatCallback = true;
                anchors.onFoodConsumed(this.activeFoodObjectId || "", this.heldFoodItemId || "food_seed_mix");
              }
              break;
            }
            case "drink": {
              targetRear = 0.40;
              targetChew = 0.55;
              this.isHoldingFood = false;
              this.posture.chewPhase += clampedDt * 8.5;
              this.targetHeadYaw = 0;
              this.targetHeadPitch = -0.34;
              this.targetHeadRoll = 0.08;
              activityLabel = "Drinking Water";
              if (!this.hasTriggeredDrinkCallback && this.phaseTimer < 1.5 && anchors.onWaterConsumed) {
                this.hasTriggeredDrinkCallback = true;
                anchors.onWaterConsumed();
              }
              break;
            }
            case "gnaw": {
              targetCrouch = 0.55;
              targetChew = 0.95;
              this.posture.chewPhase += clampedDt * 11.0;
              this.targetHeadYaw = Math.sin(this.posture.chewPhase * 0.2) * 0.12;
              this.targetHeadPitch = 0.15 + Math.sin(this.posture.chewPhase * 0.5) * 0.1;
              this.targetHeadRoll = 0.15;
              activityLabel = "Gnawing Chew Block";
              break;
            }
            case "dig": {
              targetCrouch = 0.45;
              targetDig = 1.0;
              this.posture.digPhase += clampedDt * 15.0;
              this.targetHeadYaw = Math.sin(this.posture.digPhase * 0.12) * 0.15;
              this.targetHeadPitch = 0.34;
              this.targetHeadRoll = 0;
              activityLabel = "Digging Bedding";
              break;
            }
            case "rest": {
              targetCurl = 0.88;
              this.targetHeadYaw = 0.15;
              this.targetHeadPitch = 0.25;
              this.targetHeadRoll = 0.1;
              activityLabel = this.goal === "corner_sit" ? "Sitting & Resting in Cozy Corner" : "Curled Up Resting";
              break;
            }
            case "sniff":
            default: {
              this.updateHeadSaccade(clampedDt, 0.48, 0.06, 0.18, 0.14);
              const sniffTurn = Math.sin(this.phaseTimer * 1.4) * 0.08 * clampedDt;
              this.yaw += sniffTurn;
              yawRate = sniffTurn / clampedDt;
              activityLabel = "Sniffing & Scanning";
              break;
            }
          }
        }
      }
    }

    // Organic acceleration & braking (no robotic instant start/stop)
    const accelRate = targetSpeed > this.currentSpeed ? 5.5 : 7.5;
    this.currentSpeed = damp(this.currentSpeed, targetSpeed, accelRate, clampedDt);

    // Smoothly blend posture channels (calibrated for lifelike mammal motion)
    this.posture.rearAmount = damp(this.posture.rearAmount, targetRear, 3.6, clampedDt);
    this.posture.crouchAmount = damp(this.posture.crouchAmount, targetCrouch, 4.2, clampedDt);
    this.posture.curlAmount = damp(this.posture.curlAmount, targetCurl, 2.5, clampedDt);
    this.posture.groomAmount = damp(this.posture.groomAmount, targetGroom, 4.5, clampedDt);
    this.posture.eatHoldAmount = damp(this.posture.eatHoldAmount ?? 0, targetEatHold, 5.2, clampedDt);
    this.posture.digAmount = damp(this.posture.digAmount, targetDig, 4.8, clampedDt);
    this.posture.chewAmount = damp(this.posture.chewAmount, targetChew, 6.0, clampedDt);
    this.posture.headYaw = damp(this.posture.headYaw, this.targetHeadYaw, 5.8, clampedDt);
    this.posture.headPitch = damp(this.posture.headPitch, this.targetHeadPitch, 5.8, clampedDt);
    this.posture.headRoll = damp(this.posture.headRoll, this.targetHeadRoll, 5.2, clampedDt);

    // Cheek pouch fill from backend state + active foraging puff (soft-capped at 0.84 for smooth round cheeks)
    const baseCheek = petState?.cheek_pouch_fill ?? 0;
    const forageBonus = this.phase === "forage_eat" ? 0.22 : 0;
    const targetCheekL = THREE.MathUtils.clamp(baseCheek + forageBonus, 0, 0.84);
    const targetCheekR = THREE.MathUtils.clamp(baseCheek * 0.92 + forageBonus * 0.85, 0, 0.84);
    this.smoothCheekL = damp(this.smoothCheekL, targetCheekL, 5.0, clampedDt);
    this.smoothCheekR = damp(this.smoothCheekR, targetCheekR, 5.0, clampedDt);

    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), this.yaw);
    const vx = Math.sin(this.yaw) * this.currentSpeed;
    const vz = Math.cos(this.yaw) * this.currentSpeed;

    const isAlert =
      this.phase === "rear_up" ||
      this.phase === "inspect_prop" ||
      this.phase === "log_perch" ||
      this.microFreezeTimer > 0;
    const isResting = this.phase === "rest";
    const isWheelRun = this.phase === "wheel_run";

    const proceduralConfig: ProceduralLayerConfig = {
      ...DEFAULT_PROCEDURAL_CONFIG,
      breathing: {
        ...DEFAULT_PROCEDURAL_CONFIG.breathing,
        rateHz: isResting ? 0.95 : isWheelRun ? 2.8 : this.phase === "wheel_pause" ? 2.6 : 1.7 + stress * 0.9,
        amplitude: isResting ? 0.85 : isWheelRun ? 0.95 : 0.72,
      },
      whiskerTwitch: {
        ...DEFAULT_PROCEDURAL_CONFIG.whiskerTwitch,
        sniffHz: isResting ? 2.0 : isAlert ? 9.5 : this.currentSpeed > 0.02 ? 8.0 : 6.2 + curiosity * 3.5,
        amplitude: isResting ? 0.15 : isAlert ? 0.95 : 0.78,
      },
      earOrientation: {
        ...DEFAULT_PROCEDURAL_CONFIG.earOrientation,
        alertLevel: isResting ? 0.18 : isAlert ? 0.98 : this.phase === "groom" ? 0.35 : 0.65 + stress * 0.25,
        flickRate: isResting ? 0.12 : isAlert ? 0.9 : 0.45,
      },
      blinkAndGaze: {
        ...DEFAULT_PROCEDURAL_CONFIG.blinkAndGaze,
        sleepiness: isResting ? 0.88 : this.phase === "groom" ? 0.52 : THREE.MathUtils.clamp((0.4 - energy) * 0.8, 0.05, 0.45),
        gazeAmplitude: isResting ? 0.1 : 0.85 + curiosity * 0.2,
      },
      cheekPouch: {
        enabled: true,
        leftFill: this.smoothCheekL,
        rightFill: this.smoothCheekR,
      },
      mouth: {
        enabled: true,
        chewAmount: this.posture.chewAmount,
        chewPhase: this.posture.chewPhase,
        mouthOpen: this.phase === "drink" ? 0.25 : 0,
      },
    };

    const walking = this.currentSpeed > 0.015;
    return {
      pose: {
        rootPosition: [this.pos.x, this.pos.y, this.pos.z],
        rootQuaternion: [q.x, q.y, q.z, q.w],
        velocity: [vx, 0, vz],
        angularVelocity: [0, yawRate, 0],
        footContacts: {
          fl: !walking || Math.sin(this.gaitPhase) > 0,
          fr: !walking || Math.sin(this.gaitPhase + Math.PI) > 0,
          bl: !walking || Math.sin(this.gaitPhase + Math.PI) > 0,
          br: !walking || Math.sin(this.gaitPhase) > 0,
        },
        gaitPhase: this.gaitPhase,
        posture: { ...this.posture },
      },
      proceduralConfig,
      wheelSpinDelta,
      activityLabel,
    };
  }
}
