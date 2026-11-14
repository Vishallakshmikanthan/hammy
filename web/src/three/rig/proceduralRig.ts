import * as THREE from "three";
import type { LoadedHamsterAsset, ProceduralLayerConfig } from "./types";

interface SpringState {
  offset: THREE.Vector3;
  velocity: THREE.Vector3;
}

export class ProceduralRigLayer {
  private elapsed = 0;
  private nextBlinkAt = 2.6;
  private blinkProgress = 0;
  private isBlinking = false;
  private prevRootPos = new THREE.Vector3();
  private prevVel = new THREE.Vector3();
  private hasPrev = false;

  private readonly springs: Record<string, SpringState> = {
    jiggle_cheek_L: { offset: new THREE.Vector3(), velocity: new THREE.Vector3() },
    jiggle_cheek_R: { offset: new THREE.Vector3(), velocity: new THREE.Vector3() },
    jiggle_flank_L: { offset: new THREE.Vector3(), velocity: new THREE.Vector3() },
    jiggle_flank_R: { offset: new THREE.Vector3(), velocity: new THREE.Vector3() },
    jiggle_scruff: { offset: new THREE.Vector3(), velocity: new THREE.Vector3() },
  };

  constructor(private readonly asset: LoadedHamsterAsset) {}

  private setMorph(name: string, value: number): void {
    const clamped = THREE.MathUtils.clamp(value, 0, 1);
    for (const mesh of this.asset.morphMeshes) {
      const idx = mesh.morphTargetDictionary?.[name];
      if (idx !== undefined && mesh.morphTargetInfluences) {
        mesh.morphTargetInfluences[idx] = clamped;
      }
    }
  }

  public update(dt: number, config: ProceduralLayerConfig): void {
    const safeDt = Math.min(dt, 0.05);
    this.elapsed += safeDt;

    // 1. Breathing
    if (config.breathing.enabled) {
      const breath = (Math.sin(this.elapsed * Math.PI * 2 * config.breathing.rateHz) * 0.5 + 0.5) * config.breathing.amplitude;
      this.setMorph("breath_in", breath);
      const spine2 = this.asset.bones.get("spine_2");
      if (spine2) {
        spine2.rotation.x += (breath - 0.5 * config.breathing.amplitude) * 0.04;
      }
    } else {
      this.setMorph("breath_in", 0);
    }

    // 2. Whisker twitch & nose wrinkle (sniff-synchronised 5-10 Hz in organic bursts)
    if (config.whiskerTwitch.enabled) {
      const sniff = Math.sin(this.elapsed * Math.PI * 2 * config.whiskerTwitch.sniffHz);
      const burst = THREE.MathUtils.clamp(
        0.45 + 0.35 * Math.sin(this.elapsed * 1.9) + 0.25 * Math.sin(this.elapsed * 4.7),
        0.15,
        1.0
      );
      const amp = config.whiskerTwitch.amplitude * burst;
      this.setMorph("whisker_forward", (sniff * 0.5 + 0.5) * amp);
      this.setMorph("nose_wrinkle", Math.max(0, sniff) * 0.78 * amp);

      const wL = this.asset.bones.get("whisker_L");
      const wR = this.asset.bones.get("whisker_R");
      if (wL) wL.rotation.y += sniff * 0.16 * amp;
      if (wR) wR.rotation.y -= sniff * 0.16 * amp;
    } else {
      this.setMorph("whisker_forward", 0);
      this.setMorph("nose_wrinkle", 0);
    }

    // 3. Ear orientation + independent micro-flicks
    if (config.earOrientation.enabled) {
      const earL = this.asset.bones.get("ear_L_1");
      const earR = this.asset.bones.get("ear_R_1");
      const flickL = Math.pow(Math.max(0, Math.sin(this.elapsed * Math.PI * config.earOrientation.flickRate)), 16);
      const flickR = Math.pow(Math.max(0, Math.sin(this.elapsed * Math.PI * config.earOrientation.flickRate + 1.15)), 16);
      const alertAngle = (config.earOrientation.alertLevel - 0.5) * 0.38;
      if (earL) earL.rotation.z += alertAngle + flickL * 0.28;
      if (earR) earR.rotation.z -= alertAngle + flickR * 0.22;
      this.setMorph("ear_fold", Math.max(0, 1 - config.earOrientation.alertLevel) * 0.72);
    } else {
      this.setMorph("ear_fold", 0);
    }

    // 4. Blink & gaze micro-movements
    if (config.blinkAndGaze.enabled) {
      if (!this.isBlinking && this.elapsed >= this.nextBlinkAt) {
        this.isBlinking = true;
        this.blinkProgress = 0;
      }
      let blinkVal = 0;
      if (this.isBlinking) {
        this.blinkProgress += safeDt / 0.18; // 180ms natural blink
        if (this.blinkProgress >= 1) {
          this.isBlinking = false;
          this.nextBlinkAt = this.elapsed + config.blinkAndGaze.blinkIntervalSec * (0.75 + Math.random() * 0.5);
        } else {
          blinkVal = Math.sin(this.blinkProgress * Math.PI);
        }
      }
      this.setMorph("blink", blinkVal);
      this.setMorph("squint", config.blinkAndGaze.sleepiness);

      const eyeL = this.asset.bones.get("eye_L");
      const eyeR = this.asset.bones.get("eye_R");
      const gazeX = Math.sin(this.elapsed * 0.9) * 0.08 * config.blinkAndGaze.gazeAmplitude;
      const gazeY = Math.cos(this.elapsed * 1.4) * 0.05 * config.blinkAndGaze.gazeAmplitude;
      if (eyeL) {
        eyeL.rotation.y += gazeX;
        eyeL.rotation.x += gazeY;
      }
      if (eyeR) {
        eyeR.rotation.y += gazeX;
        eyeR.rotation.x += gazeY;
      }
    } else {
      this.setMorph("blink", 0);
      this.setMorph("squint", 0);
    }

    // 5. Tail stub micro-motion
    if (config.tail.enabled) {
      const t1 = this.asset.bones.get("tail_1");
      if (t1) {
        t1.rotation.y += Math.sin(this.elapsed * 3.1) * 0.12 * config.tail.wagAmplitude;
      }
    }

    // 6. Spring-bone fur/skin jiggle
    const curPos = this.asset.root.position;
    const accel = new THREE.Vector3();
    if (this.hasPrev && safeDt > 1e-4) {
      const vel = curPos.clone().sub(this.prevRootPos).divideScalar(safeDt);
      accel.copy(vel).sub(this.prevVel).divideScalar(safeDt);
      this.prevVel.copy(vel);
    }
    this.prevRootPos.copy(curPos);
    this.hasPrev = true;

    const k = config.springJiggle.stiffness;
    const d = config.springJiggle.damping;
    const jAmp = config.springJiggle.enabled ? config.springJiggle.amplitude : 0;

    for (const [bname, st] of Object.entries(this.springs)) {
      if (jAmp <= 0.001) {
        st.offset.set(0, 0, 0);
        st.velocity.set(0, 0, 0);
        continue;
      }
      // Spring force F = -k*x - d*v - accel*0.02
      const force = st.offset.clone().multiplyScalar(-k).addScaledVector(st.velocity, -d).addScaledVector(accel, -0.025 * jAmp);
      st.velocity.addScaledVector(force, safeDt);
      st.offset.addScaledVector(st.velocity, safeDt);
      st.offset.clampLength(0, 0.25);

      const bone = this.asset.bones.get(bname);
      if (bone) {
        bone.rotation.x += st.offset.z * 0.8 + Math.sin(this.elapsed * 4.2) * 0.015 * jAmp;
        bone.rotation.z += st.offset.x * 0.8;
      }
    }

    // 7. Cheek pouch fill (0..1)
    if (config.cheekPouch.enabled) {
      this.setMorph("cheek_pouch_left", config.cheekPouch.leftFill);
      this.setMorph("cheek_pouch_right", config.cheekPouch.rightFill);
    } else {
      this.setMorph("cheek_pouch_left", 0);
      this.setMorph("cheek_pouch_right", 0);
    }

    // 8. Mouth & chewing morphs
    if (config.mouth?.enabled) {
      const chewAmt = THREE.MathUtils.clamp(config.mouth.chewAmount, 0, 1);
      const chewWave = (Math.sin(config.mouth.chewPhase) * 0.5 + 0.5) * chewAmt;
      const mouthOpenVal = Math.max(0, Math.sin(config.mouth.chewPhase)) * 0.5 * chewAmt + config.mouth.mouthOpen;
      this.setMorph("chew", chewWave);
      this.setMorph("mouth_open", mouthOpenVal);
    } else {
      this.setMorph("chew", 0);
      this.setMorph("mouth_open", 0);
    }
  }
}

