import * as THREE from "three";

export interface TrajectoryKeyframe {
  t_sec: number;
  root_pos: [number, number, number];
  root_quat: [number, number, number, number];
  joint_angles: number[];
  foot_contacts: [boolean, boolean, boolean, boolean];
}

export interface TrajectoryClip {
  schema_version: string;
  clip_id: string;
  pet_id: string;
  skill_id: string;
  seed: number;
  origin: "observed_physics" | "sampled_from_skill_model" | "rule";
  behaviour_type: "learned" | "scripted" | "rule";
  morphology_version: string;
  environment_version: string;
  fps: number;
  start_sim_time_sec: number;
  end_sim_time_sec: number;
  keyframes: TrajectoryKeyframe[];
}

export interface InterpolatedClipPose {
  rootPos: [number, number, number];
  rootQuat: [number, number, number, number];
  jointAngles: number[];
  footContacts: [boolean, boolean, boolean, boolean];
  clipId: string;
  skillId: string;
  seed: number;
  origin: TrajectoryClip["origin"];
  behaviourType: TrajectoryClip["behaviour_type"];
}

export class ClipPlayer {
  private queue: TrajectoryClip[] = [];
  private activeIdx = 0;
  private localTimeSec = 0;

  private readonly qA = new THREE.Quaternion();
  private readonly qB = new THREE.Quaternion();
  private readonly qOut = new THREE.Quaternion();

  public enqueue(clip: TrajectoryClip): void {
    if (this.queue.some((c) => c.clip_id === clip.clip_id)) return;
    this.queue.push(clip);
    this.queue.sort((a, b) => a.start_sim_time_sec - b.start_sim_time_sec);
  }

  public reconnectFrom(clips: TrajectoryClip[], resumeSimTime?: number): void {
    this.queue = [];
    this.activeIdx = 0;
    this.localTimeSec = 0;
    for (const c of clips) {
      this.enqueue(c);
    }
    if (resumeSimTime !== undefined && this.queue.length > 0) {
      const idx = this.queue.findIndex((c) => c.end_sim_time_sec > resumeSimTime);
      if (idx >= 0) {
        this.activeIdx = idx;
        this.localTimeSec = Math.max(0, resumeSimTime - this.queue[idx].start_sim_time_sec);
      }
    }
  }

  public get activeClip(): TrajectoryClip | null {
    return this.queue[this.activeIdx] ?? null;
  }

  public get queueLength(): number {
    return this.queue.length;
  }

  public step(dtSec: number): InterpolatedClipPose | null {
    if (this.queue.length === 0) return null;
    this.localTimeSec += Math.max(0, dtSec);

    // Seamless clip chaining across queued clips
    while (this.activeIdx < this.queue.length) {
      const cur = this.queue[this.activeIdx];
      const duration = Math.max(1e-4, cur.end_sim_time_sec - cur.start_sim_time_sec);
      if (this.localTimeSec < duration) break;

      if (this.activeIdx + 1 < this.queue.length) {
        this.localTimeSec -= duration;
        this.activeIdx++;
      } else {
        // Hold final keyframe of last clip until new clips arrive
        this.localTimeSec = duration;
        break;
      }
    }

    return this.samplePose();
  }

  public samplePose(): InterpolatedClipPose | null {
    const clip = this.activeClip;
    if (!clip || clip.keyframes.length === 0) return null;

    const kfs = clip.keyframes;
    if (kfs.length === 1 || this.localTimeSec <= kfs[0].t_sec) {
      const k = kfs[0];
      return {
        rootPos: [...k.root_pos],
        rootQuat: [...k.root_quat],
        jointAngles: [...k.joint_angles],
        footContacts: [...k.foot_contacts],
        clipId: clip.clip_id,
        skillId: clip.skill_id,
        seed: clip.seed,
        origin: clip.origin,
        behaviourType: clip.behaviour_type,
      };
    }

    const last = kfs[kfs.length - 1];
    if (this.localTimeSec >= last.t_sec) {
      return {
        rootPos: [...last.root_pos],
        rootQuat: [...last.root_quat],
        jointAngles: [...last.joint_angles],
        footContacts: [...last.foot_contacts],
        clipId: clip.clip_id,
        skillId: clip.skill_id,
        seed: clip.seed,
        origin: clip.origin,
        behaviourType: clip.behaviour_type,
      };
    }

    // Binary or linear search for bracketing keyframes
    let idx = 0;
    while (idx + 1 < kfs.length && kfs[idx + 1].t_sec < this.localTimeSec) {
      idx++;
    }
    const a = kfs[idx];
    const b = kfs[Math.min(idx + 1, kfs.length - 1)];
    const span = Math.max(1e-6, b.t_sec - a.t_sec);
    const alpha = THREE.MathUtils.clamp((this.localTimeSec - a.t_sec) / span, 0, 1);

    const rootPos: [number, number, number] = [
      THREE.MathUtils.lerp(a.root_pos[0], b.root_pos[0], alpha),
      THREE.MathUtils.lerp(a.root_pos[1], b.root_pos[1], alpha),
      THREE.MathUtils.lerp(a.root_pos[2], b.root_pos[2], alpha),
    ];

    this.qA.set(a.root_quat[0], a.root_quat[1], a.root_quat[2], a.root_quat[3]).normalize();
    this.qB.set(b.root_quat[0], b.root_quat[1], b.root_quat[2], b.root_quat[3]).normalize();
    this.qOut.slerpQuaternions(this.qA, this.qB, alpha);

    const jointAngles = a.joint_angles.map((v, j) => THREE.MathUtils.lerp(v, b.joint_angles[j] ?? v, alpha));
    const footContacts = alpha < 0.5 ? a.foot_contacts : b.foot_contacts;

    return {
      rootPos,
      rootQuat: [this.qOut.x, this.qOut.y, this.qOut.z, this.qOut.w],
      jointAngles,
      footContacts: [...footContacts] as [boolean, boolean, boolean, boolean],
      clipId: clip.clip_id,
      skillId: clip.skill_id,
      seed: clip.seed,
      origin: clip.origin,
      behaviourType: clip.behaviour_type,
    };
  }
}

