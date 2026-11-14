import * as THREE from "three";
import type { PetState, WorldEvent } from "../../types";
import {
  DEFAULT_PROCEDURAL_CONFIG,
  type HamsterPostureState,
  type PhysicsPoseInput,
  type ProceduralLayerConfig,
} from "../rig/types";

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
  hideoutBox?: THREE.Box3;
  wheelBox?: THREE.Box3;
  wheelTrackY?: number;
  sampleBeddingY?: (x: number, z: number) => number;
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
  | "rest";

type HabitatGoal = "wander" | "wheel" | "water" | "hideout" | "bowl" | "chew";

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
  };

  private smoothCheekL = 0;
  private smoothCheekR = 0;

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

  private pushOutOfProps(
    v: THREE.Vector3,
    anchors: HabitatPropAnchors,
    petState?: PetState | null
  ): THREE.Vector3 {
    const bodyRadius = 0.036;
    const obstacles: Array<{ pos: THREE.Vector3; radius: number }> = [
      { pos: anchors.bowlPos, radius: 0.072 },
      { pos: anchors.chewPos, radius: 0.044 },
    ];

    const allowHideout =
      Boolean(petState?.inside_hideout) ||
      (this.goal === "hideout" && this.goalStage !== "approach");
    if (!allowHideout && !anchors.hideoutBox) {
      obstacles.push({ pos: anchors.hideoutPos, radius: 0.115 });
    }

    const allowWheel =
      Boolean(petState?.on_wheel) ||
      (this.goal === "wheel" && this.goalStage !== "approach");
    if (!allowWheel && !anchors.wheelBox) {
      obstacles.push({ pos: anchors.wheelPos, radius: 0.15 });
    }

    if (!petState?.inside_tunnel && !anchors.tunnelBoxes?.length && !anchors.tunnelBox) {
      obstacles.push({ pos: anchors.tunnelPos, radius: 0.115 });
    }

    for (let pass = 0; pass < 2; pass++) {
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

      if (!allowHideout && anchors.hideoutBox) {
        this.pushOutOfBox2D(v, anchors.hideoutBox, 0.034);
      }
      if (!allowWheel && anchors.wheelBox) {
        this.pushOutOfBox2D(v, anchors.wheelBox, 0.032);
      }
      if (!petState?.inside_tunnel) {
        if (anchors.tunnelBoxes && anchors.tunnelBoxes.length > 0) {
          this.pushOutOfTunnelBoxes(v, anchors.tunnelBoxes, bodyRadius);
        } else if (anchors.tunnelBox) {
          this.pushOutOfBox2D(v, anchors.tunnelBox, bodyRadius);
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
    v.x = THREE.MathUtils.clamp(v.x, -0.43, 0.43);
    v.z = THREE.MathUtils.clamp(v.z, -0.215, 0.215);
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
    // Upright wheel is open on its +Z front face (around z = -0.085); approach directly in front of it
    const zEntry = anchors.wheelBox ? anchors.wheelBox.max.z + 0.055 : anchors.wheelPos.z + 0.10;
    return this.clampFloor(
      new THREE.Vector3(anchors.wheelPos.x, anchors.beddingY, Math.min(0.16, zEntry)),
      anchors
    );
  }

  private getHideoutDoorPos(anchors: HabitatPropAnchors): THREE.Vector3 {
    const zDoor = anchors.hideoutBox ? anchors.hideoutBox.max.z + 0.065 : anchors.hideoutPos.z + 0.12;
    return this.clampFloor(
      new THREE.Vector3(anchors.hideoutPos.x, anchors.beddingY, zDoor),
      anchors
    );
  }

  private getWheelTrackPos(anchors: HabitatPropAnchors): THREE.Vector3 {
    const trackY = anchors.wheelTrackY ?? anchors.beddingY + 0.018;
    return new THREE.Vector3(anchors.wheelPos.x, trackY, anchors.wheelPos.z);
  }

  private isInsideAnyObstacle(x: number, z: number, anchors: HabitatPropAnchors): boolean {
    const probe = new THREE.Vector3(x, anchors.beddingY, z);
    const beforeX = probe.x;
    const beforeZ = probe.z;
    this.pushOutOfProps(probe, anchors, null);
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

  private setGoalTargetWithTunnelCorridor(dest: THREE.Vector3, anchors: HabitatPropAnchors): void {
    this.waypointQueue = [];
    if (this.segmentIsClear(this.pos.x, this.pos.z, dest.x, dest.z, anchors)) {
      this.targetPos.copy(dest);
      return;
    }

    // BFS over open habitat corridor waypoints to route cleanly around rotated tunnel pipes & props
    const nodes: Array<{ x: number; z: number }> = [
      { x: this.pos.x, z: this.pos.z },
      { x: -0.26, z: 0.12 },   // front-left open area
      { x: -0.09, z: 0.14 },   // front-left pocket
      { x: -0.09, z: 0.213 },  // front-left-center lane
      { x: 0.05, z: 0.213 },   // front lane in front of tunnel_straight_1
      { x: 0.17, z: 0.213 },   // front-right corner lane
      { x: 0.17, z: 0.16 },    // front-right near chew/bowl
      { x: 0.20, z: 0.12 },    // gap between bowl and chew block
      { x: 0.22, z: 0.02 },    // open pocket between hideout, chew, and bowl
      { x: 0.145, z: -0.02 },  // center-right corridor between tunnel & hideout
      { x: 0.13, z: -0.16 },   // back-right corridor
      { x: 0.0, z: -0.165 },   // back-center behind tunnel_curve
      { x: -0.11, z: -0.16 },  // back-left corridor
      { x: -0.27, z: -0.01 },  // front of upright wheel
      { x: 0.38, z: 0.04 },    // east corridor (water spout)
      { x: dest.x, z: dest.z },
    ];

    const startIdx = 0;
    const goalIdx = nodes.length - 1;
    const parent = new Array<number>(nodes.length).fill(-1);
    const visited = new Array<boolean>(nodes.length).fill(false);
    const queue: number[] = [startIdx];
    visited[startIdx] = true;

    while (queue.length > 0) {
      const cur = queue.shift()!;
      if (cur === goalIdx) break;
      for (let nxt = 1; nxt < nodes.length; nxt++) {
        if (visited[nxt]) continue;
        if (this.segmentIsClear(nodes[cur].x, nodes[cur].z, nodes[nxt].x, nodes[nxt].z, anchors)) {
          visited[nxt] = true;
          parent[nxt] = cur;
          queue.push(nxt);
        }
      }
    }

    if (parent[goalIdx] !== -1) {
      const path: THREE.Vector3[] = [];
      let cur = goalIdx;
      while (cur !== startIdx && cur !== -1) {
        const n = nodes[cur];
        path.push(new THREE.Vector3(n.x, this.sampleGroundY(n.x, n.z, anchors), n.z));
        cur = parent[cur];
      }
      path.reverse();
      if (path.length > 0) {
        this.targetPos.copy(path[0]);
        this.waypointQueue = path.slice(1);
        return;
      }
    }

    this.targetPos.copy(dest);
  }

  private chooseNextGoalAndTarget(
    anchors: HabitatPropAnchors,
    latestSkill: string | null,
    petState?: PetState | null
  ): void {
    this.faceTargetPos = null;
    this.waypointQueue = [];

    if (latestSkill === "eat" || latestSkill === "hoard") {
      this.goal = "bowl";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.bowlPos.clone();
      this.setGoalTargetWithTunnelCorridor(
        this.clampFloor(new THREE.Vector3(anchors.bowlPos.x - 0.095, anchors.beddingY, anchors.bowlPos.z), anchors, petState),
        anchors
      );
      return;
    }
    if (latestSkill === "drink") {
      this.goal = "water";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.spoutPos.clone();
      this.setGoalTargetWithTunnelCorridor(
        this.clampFloor(new THREE.Vector3(anchors.spoutPos.x - 0.045, anchors.beddingY, anchors.spoutPos.z + 0.025), anchors, petState),
        anchors
      );
      return;
    }
    if (latestSkill === "gnaw") {
      this.goal = "chew";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.chewPos.clone();
      this.setGoalTargetWithTunnelCorridor(
        this.clampFloor(new THREE.Vector3(anchors.chewPos.x - 0.058, anchors.beddingY, anchors.chewPos.z + 0.015), anchors, petState),
        anchors
      );
      return;
    }

    // Autonomous habitat goal selection (works offline / between server updates)
    const energy = petState?.drives.energy ?? 0.7;
    const hunger = petState?.drives.hunger ?? 0.35;
    const thirst = petState?.drives.thirst ?? 0.3;

    const r = this.nextRand();
    if (energy < 0.32 || (this.goal !== "hideout" && r < 0.16)) {
      this.goal = "hideout";
      this.goalStage = "approach";
      this.setGoalTargetWithTunnelCorridor(this.getHideoutDoorPos(anchors), anchors);
      return;
    }
    if (this.goal !== "wheel" && r < 0.40) {
      this.goal = "wheel";
      this.goalStage = "approach";
      this.goalCyclesLeft = 1 + Math.floor(this.nextRand() * 2);
      this.setGoalTargetWithTunnelCorridor(this.getWheelEntryPos(anchors), anchors);
      return;
    }
    if (this.goal !== "water" && r < 0.56 + thirst * 0.1) {
      this.goal = "water";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.spoutPos.clone();
      this.setGoalTargetWithTunnelCorridor(
        this.clampFloor(new THREE.Vector3(anchors.spoutPos.x - 0.045, anchors.beddingY, anchors.spoutPos.z + 0.025), anchors, petState),
        anchors
      );
      return;
    }
    if (this.goal !== "bowl" && r < 0.72 + hunger * 0.1) {
      this.goal = "bowl";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.bowlPos.clone();
      this.setGoalTargetWithTunnelCorridor(
        this.clampFloor(new THREE.Vector3(anchors.bowlPos.x - 0.095, anchors.beddingY, anchors.bowlPos.z), anchors, petState),
        anchors
      );
      return;
    }
    if (this.goal !== "chew" && r < 0.82) {
      this.goal = "chew";
      this.goalStage = "approach";
      this.faceTargetPos = anchors.chewPos.clone();
      this.setGoalTargetWithTunnelCorridor(
        this.clampFloor(new THREE.Vector3(anchors.chewPos.x - 0.058, anchors.beddingY, anchors.chewPos.z + 0.015), anchors, petState),
        anchors
      );
      return;
    }

    // Open-bedding exploration (avoiding all tunnel pipes & props)
    this.goal = "wander";
    this.goalStage = "approach";
    const base = petState ? this.mapServerPos(petState, anchors) : this.pos;
    for (let attempt = 0; attempt < 10; attempt++) {
      const rx = attempt < 5 ? base.x + (this.nextRand() * 2 - 1) * 0.22 : (this.nextRand() * 2 - 1) * 0.36;
      const rz = attempt < 5 ? base.z + (this.nextRand() * 2 - 1) * 0.14 : (this.nextRand() * 2 - 1) * 0.15;
      const cx = THREE.MathUtils.clamp(rx, -0.39, 0.39);
      const cz = THREE.MathUtils.clamp(rz, -0.16, 0.16);
      if (!this.isInsideAnyObstacle(cx, cz, anchors)) {
        this.targetPos.set(cx, this.sampleGroundY(cx, cz, anchors), cz);
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

    if ((this.goal === "bowl" || latestSkill === "eat" || latestSkill === "hoard") && this.pos.distanceTo(anchors.bowlPos) < 0.15) {
      this.goalStage = "active";
      this.faceTargetPos = anchors.bowlPos.clone();
      this.enterPhase("forage_eat", 1.8 + this.nextRand() * 1.8);
      return;
    }
    if (
      (this.goal === "water" || latestSkill === "drink") &&
      Math.hypot(this.pos.x - anchors.spoutPos.x, this.pos.z - anchors.spoutPos.z) < 0.14
    ) {
      this.goalStage = "active";
      this.faceTargetPos = anchors.spoutPos.clone();
      this.enterPhase("drink", 1.6 + this.nextRand() * 1.4);
      return;
    }
    if ((this.goal === "chew" || latestSkill === "gnaw") && this.pos.distanceTo(anchors.chewPos) < 0.13) {
      this.goalStage = "active";
      this.faceTargetPos = anchors.chewPos.clone();
      this.enterPhase("gnaw", 1.6 + this.nextRand() * 1.5);
      return;
    }

    // Naturalistic ethogram transitions on open bedding
    const r = this.nextRand();
    if (energy < 0.25 && r < 0.45) {
      this.enterPhase("rest", 2.4 + this.nextRand() * 2.2);
      return;
    }
    if ((this.prevPhase === "forage_eat" || this.prevPhase === "dig") && r < 0.55) {
      this.enterPhase("groom", 1.8 + this.nextRand() * 1.5);
      return;
    }

    const rearProb = 0.24 + curiosity * 0.16 + stress * 0.15;
    const groomProb = rearProb + 0.18;
    const digProb = groomProb + (petState?.inside_tunnel ? 0.05 : 0.16 + curiosity * 0.08);

    if (r < rearProb) {
      this.enterPhase("rear_up", 1.1 + this.nextRand() * 1.3);
    } else if (r < groomProb) {
      this.enterPhase("groom", 1.6 + this.nextRand() * 1.6);
    } else if (r < digProb) {
      this.enterPhase("dig", 1.0 + this.nextRand() * 1.1);
    } else {
      this.enterPhase("sniff", 0.9 + this.nextRand() * 1.3);
    }
  }

  private updateHeadSaccade(dt: number, yawRange: number, pitchBase: number, pitchRange: number, rollRange: number): void {
    this.headSaccadeTimer -= dt;
    if (this.headSaccadeTimer <= 0) {
      this.headSaccadeTimer = 0.18 + this.nextRand() * 0.45;
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

    // Sync server target when PetState updates
    if (petState) {
      const posKey = `${petState.position_xyz[0]?.toFixed(3)},${petState.position_xyz[1]?.toFixed(3)},${petState.on_wheel},${petState.inside_hideout},${petState.inside_tunnel}`;
      if (posKey !== this.lastServerPosKey) {
        this.lastServerPosKey = posKey;
        this.faceTargetPos = null;
        if (petState.on_wheel) {
          this.goal = "wheel";
          this.goalStage = "active";
          this.targetPos.copy(this.getWheelTrackPos(anchors));
        } else if (petState.inside_hideout) {
          this.goal = "hideout";
          this.goalStage = "active";
          this.targetPos.set(
            anchors.hideoutPos.x,
            this.sampleGroundY(anchors.hideoutPos.x, anchors.hideoutPos.z, anchors) - 0.004,
            anchors.hideoutPos.z
          );
        } else if (petState.inside_tunnel) {
          this.goal = "wander";
          this.goalStage = "approach";
          this.targetPos.set(
            anchors.tunnelPos.x,
            this.sampleGroundY(anchors.tunnelPos.x, anchors.tunnelPos.z, anchors),
            anchors.tunnelPos.z
          );
        } else {
          this.goal = "wander";
          this.goalStage = "approach";
          this.targetPos.copy(this.mapServerPos(petState, anchors));
        }

        if (this.pos.distanceTo(this.targetPos) > 0.025) {
          this.enterPhase("scurry", 4.5);
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
    let targetDig = 0;
    let targetChew = 0;

    const onWheelActive =
      (petState?.on_wheel && distToTarget < 0.06) ||
      (this.goal === "wheel" && this.goalStage === "active" && distToTarget < 0.06);

    const insideHideoutActive =
      (petState?.inside_hideout && distToTarget < 0.06) ||
      (this.goal === "hideout" && this.goalStage === "active" && distToTarget < 0.06);

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
        this.enterPhase("wheel_run", 2.0 + this.nextRand() * 2.2);
      } else if (this.phaseTimer <= 0) {
        if (this.phase === "wheel_run") {
          this.wheelCoastVel = 5.4;
          this.enterPhase("wheel_pause", 0.9 + this.nextRand() * 1.1);
        } else if (!petState?.on_wheel && this.goal === "wheel") {
          if (this.goalCyclesLeft > 0) {
            this.goalCyclesLeft--;
            this.wheelBurstSpeed = 0.30 + this.nextRand() * 0.14;
            this.enterPhase("wheel_run", 1.8 + this.nextRand() * 2.2);
          } else {
            // Hop off wheel back to entry point
            this.goalStage = "exit";
            this.targetPos.copy(this.getWheelEntryPos(anchors));
            this.enterPhase("scurry", 2.5);
          }
        } else {
          this.wheelBurstSpeed = 0.30 + this.nextRand() * 0.14;
          this.enterPhase("wheel_run", 1.8 + this.nextRand() * 2.8);
        }
      }

      if (this.phase === "wheel_run") {
        targetSpeed = this.wheelBurstSpeed;
        this.gaitPhase += clampedDt * 20.5;
        wheelSpinDelta = clampedDt * 5.6;
        targetCrouch = 0.25;
        this.targetHeadYaw = 0;
        this.targetHeadPitch = -0.06;
        this.targetHeadRoll = 0;
        activityLabel = "Sprinting on Wheel";
      } else if (this.phase === "wheel_pause") {
        targetSpeed = 0;
        this.wheelPauseElapsed += clampedDt;
        // Damped wheel coasting + gentle pendulum rock
        this.wheelCoastVel *= Math.exp(-4.5 * clampedDt);
        const rock =
          this.wheelPauseElapsed < 1.1
            ? Math.sin(this.wheelPauseElapsed * 8.5) * Math.exp(-this.wheelPauseElapsed * 3.0) * 0.8
            : 0;
        wheelSpinDelta = (this.wheelCoastVel + rock) * clampedDt;
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
      this.phase = "rest";
      targetSpeed = 0;
      targetCurl = 0.92;
      this.targetHeadYaw = 0.12;
      this.targetHeadPitch = 0.25;
      this.targetHeadRoll = 0.08;
      activityLabel = "Curled Up in Hideout";

      if (!petState?.inside_hideout && this.goal === "hideout") {
        this.phaseTimer -= clampedDt;
        if (this.phaseTimer <= 0) {
          this.goalStage = "exit";
          this.targetPos.copy(this.getHideoutDoorPos(anchors));
          this.enterPhase("scurry", 2.5);
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
          distToTarget < 0.025 ||
          (this.goal === "water" && distToSpout2D < 0.085 && this.waypointQueue.length === 0) ||
          this.phaseTimer <= 0
        ) {
          if (this.waypointQueue.length > 0 && distToTarget < 0.04) {
            this.targetPos.copy(this.waypointQueue.shift()!);
            this.stuckTimer = 0;
            this.stuckCheckPos.copy(this.pos);
            this.enterPhase("scurry", 6.0);
          } else {
          const arrived = distToTarget < 0.035;
          // Handle multi-stage prop transitions (wheel & hideout)
          if (this.goal === "wheel" && this.goalStage === "approach") {
            if (arrived) {
              this.goalStage = "active";
              this.targetPos.copy(this.getWheelTrackPos(anchors));
              this.enterPhase("scurry", 2.5);
              activityLabel = "Hopping onto Wheel";
            } else {
              this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
              this.enterPhase("scurry", 7.5);
            }
          } else if (this.goal === "hideout" && this.goalStage === "approach") {
            if (arrived) {
              this.goalStage = "active";
              this.targetPos.set(
                anchors.hideoutPos.x,
                this.sampleGroundY(anchors.hideoutPos.x, anchors.hideoutPos.z, anchors) - 0.004,
                anchors.hideoutPos.z
              );
              this.enterPhase("scurry", 2.5);
              this.phaseTimer = 3.2 + this.nextRand() * 2.5;
              activityLabel = "Entering Hideout";
            } else {
              this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
              this.enterPhase("scurry", 7.5);
            }
          } else if (this.goalStage === "exit") {
            this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
            this.enterPhase("scurry", 4.5);
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
          const turnStep = THREE.MathUtils.clamp(dYaw, -8.5 * clampedDt, 8.5 * clampedDt);
          this.yaw += turnStep;
          yawRate = turnStep / clampedDt;

          // Head leads the turn slightly, nose slightly down sniffing path
          this.targetHeadYaw = THREE.MathUtils.clamp(dYaw * 0.65, -0.55, 0.55);
          this.targetHeadPitch = 0.12;
          this.targetHeadRoll = THREE.MathUtils.clamp(-dYaw * 0.2, -0.15, 0.15);

          const maxMoveSpeed = petState?.inside_tunnel ? 0.17 : 0.25 + curiosity * 0.05;
          targetSpeed = maxMoveSpeed;
          const stepDist = Math.min(distToTarget, this.currentSpeed * clampedDt);
          const prevX = this.pos.x;
          const prevZ = this.pos.z;
          if (distToTarget > 1e-4) {
            this.pos.x += (dx / distToTarget) * stepDist;
            this.pos.z += (dz / distToTarget) * stepDist;
          }
          this.pushOutOfProps(this.pos, anchors, petState);
          // If blocked head-on by an obstacle, slide tangentially around it
          const moved = Math.hypot(this.pos.x - prevX, this.pos.z - prevZ);
          if (stepDist > 1e-4 && moved < stepDist * 0.35 && distToTarget > 1e-4) {
            const perpX = -dz / distToTarget;
            const perpZ = dx / distToTarget;
            this.pos.x += perpX * stepDist * 0.85;
            this.pos.z += perpZ * stepDist * 0.85;
            this.pushOutOfProps(this.pos, anchors, petState);
          }

          if (this.goalStage !== "active") {
            this.pos.x = THREE.MathUtils.clamp(this.pos.x, -0.43, 0.43);
            this.pos.z = THREE.MathUtils.clamp(this.pos.z, -0.215, 0.215);
          }

          // Anti-jiggle stuck detector: if net progress < 5mm over 0.45s, pick a fresh unobstructed goal
          this.stuckTimer += clampedDt;
          if (this.stuckTimer >= 0.45) {
            const netMoved = Math.hypot(this.pos.x - this.stuckCheckPos.x, this.pos.z - this.stuckCheckPos.z);
            this.stuckCheckPos.copy(this.pos);
            this.stuckTimer = 0;
            if (netMoved < 0.006 && this.goalStage === "approach") {
              this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
              this.enterPhase("scurry", 6.0);
            }
          }

          // Smoothly track Y: elevated when hopping onto wheel, otherwise bedding height
          const groundY =
            this.goal === "wheel" && this.goalStage === "active"
              ? this.getWheelTrackPos(anchors).y
              : this.sampleGroundY(this.pos.x, this.pos.z, anchors);
          this.pos.y = THREE.MathUtils.lerp(this.pos.y, groundY, Math.min(1, clampedDt * 14));

          this.gaitPhase += clampedDt * 16.5;
          activityLabel = petState?.inside_tunnel
            ? "Exploring Tunnel"
            : this.goal === "wheel"
            ? "Heading to Wheel"
            : this.goal === "water"
            ? "Heading to Water"
            : this.goal === "hideout"
            ? "Heading to Hideout"
            : this.goal === "bowl"
            ? "Heading to Food Bowl"
            : this.goal === "chew"
            ? "Heading to Chew Block"
            : latestSkill
            ? `Scurrying (${latestSkill.replace(/_/g, " ")})`
            : "Scurrying";
        }
      } else {
        // Stationary / micro-behavior phases — stay flush with local bedding
        const groundY = this.sampleGroundY(this.pos.x, this.pos.z, anchors);
        this.pos.y = THREE.MathUtils.lerp(this.pos.y, groundY, Math.min(1, clampedDt * 14));
        targetSpeed = 0;

        // Smoothly turn to face prop when drinking / eating / gnawing
        if (this.faceTargetPos) {
          const fdx = this.faceTargetPos.x - this.pos.x;
          const fdz = this.faceTargetPos.z - this.pos.z;
          if (Math.hypot(fdx, fdz) > 1e-3) {
            const desiredFaceYaw = Math.atan2(fdx, fdz);
            const dFace = shortestAngleDiff(this.yaw, desiredFaceYaw);
            const turnStep = THREE.MathUtils.clamp(dFace, -8.0 * clampedDt, 8.0 * clampedDt);
            this.yaw += turnStep;
            yawRate = turnStep / clampedDt;
          }
        }

        if (this.phaseTimer <= 0) {
          this.chooseNextGoalAndTarget(anchors, latestSkill, petState);
          this.enterPhase("scurry", 7.5);
          activityLabel = "Scurrying";
        } else {
          switch (this.phase) {
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
              this.posture.groomPhase += clampedDt * 30.0;
              this.posture.chewPhase += clampedDt * 22.0;
              this.targetHeadYaw = Math.sin(this.posture.groomPhase * 0.25) * 0.12;
              this.targetHeadPitch = 0.18;
              this.targetHeadRoll = Math.sin(this.posture.groomPhase * 0.2) * 0.14;
              activityLabel = "Washing Face";
              break;
            }
            case "forage_eat": {
              targetCrouch = 0.62;
              targetChew = 0.9;
              this.posture.chewPhase += clampedDt * 26.0;
              this.targetHeadYaw = Math.sin(this.posture.chewPhase * 0.15) * 0.14;
              this.targetHeadPitch = 0.28 + Math.sin(this.posture.chewPhase * 0.35) * 0.08;
              this.targetHeadRoll = 0;
              activityLabel = "Nibbling & Stuffing Cheeks";
              break;
            }
            case "drink": {
              targetRear = 0.40;
              targetChew = 0.55;
              this.posture.chewPhase += clampedDt * 20.0;
              this.targetHeadYaw = 0;
              this.targetHeadPitch = -0.34;
              this.targetHeadRoll = 0.08;
              activityLabel = "Drinking Water";
              break;
            }
            case "gnaw": {
              targetCrouch = 0.55;
              targetChew = 0.95;
              this.posture.chewPhase += clampedDt * 28.0;
              this.targetHeadYaw = Math.sin(this.posture.chewPhase * 0.2) * 0.12;
              this.targetHeadPitch = 0.15 + Math.sin(this.posture.chewPhase * 0.5) * 0.1;
              this.targetHeadRoll = 0.15;
              activityLabel = "Gnawing Chew Block";
              break;
            }
            case "dig": {
              targetCrouch = 0.45;
              targetDig = 1.0;
              this.posture.digPhase += clampedDt * 40.0;
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
              activityLabel = "Curled Up Resting";
              break;
            }
            case "sniff":
            default: {
              this.updateHeadSaccade(clampedDt, 0.48, 0.06, 0.18, 0.14);
              const sniffTurn = Math.sin(this.phaseTimer * 2.4) * 0.14 * clampedDt;
              this.yaw += sniffTurn;
              yawRate = sniffTurn / clampedDt;
              activityLabel = "Sniffing & Scanning";
              break;
            }
          }
        }
      }
    }

    // Snappy acceleration / braking characteristic of real hamsters
    const accelRate = targetSpeed > this.currentSpeed ? 18.0 : 22.0;
    this.currentSpeed = damp(this.currentSpeed, targetSpeed, accelRate, clampedDt);

    // Smoothly blend posture channels (head snaps fast, body postures blend organically)
    this.posture.rearAmount = damp(this.posture.rearAmount, targetRear, 9.0, clampedDt);
    this.posture.crouchAmount = damp(this.posture.crouchAmount, targetCrouch, 10.0, clampedDt);
    this.posture.curlAmount = damp(this.posture.curlAmount, targetCurl, 5.0, clampedDt);
    this.posture.groomAmount = damp(this.posture.groomAmount, targetGroom, 11.0, clampedDt);
    this.posture.digAmount = damp(this.posture.digAmount, targetDig, 12.0, clampedDt);
    this.posture.chewAmount = damp(this.posture.chewAmount, targetChew, 14.0, clampedDt);
    this.posture.headYaw = damp(this.posture.headYaw, this.targetHeadYaw, 16.0, clampedDt);
    this.posture.headPitch = damp(this.posture.headPitch, this.targetHeadPitch, 16.0, clampedDt);
    this.posture.headRoll = damp(this.posture.headRoll, this.targetHeadRoll, 14.0, clampedDt);

    // Cheek pouch fill from backend state + active foraging puff
    const baseCheek = petState?.cheek_pouch_fill ?? 0;
    const forageBonus = this.phase === "forage_eat" ? 0.25 : 0;
    const targetCheekL = THREE.MathUtils.clamp(baseCheek + forageBonus, 0, 1);
    const targetCheekR = THREE.MathUtils.clamp(baseCheek * 0.92 + forageBonus * 0.85, 0, 1);
    this.smoothCheekL = damp(this.smoothCheekL, targetCheekL, 5.0, clampedDt);
    this.smoothCheekR = damp(this.smoothCheekR, targetCheekR, 5.0, clampedDt);

    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), this.yaw);
    const vx = Math.sin(this.yaw) * this.currentSpeed;
    const vz = Math.cos(this.yaw) * this.currentSpeed;

    const isAlert = this.phase === "rear_up" || this.microFreezeTimer > 0;
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
