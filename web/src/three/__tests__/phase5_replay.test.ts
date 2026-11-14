import { describe, expect, it } from "vitest";
import { ClipPlayer, type TrajectoryClip } from "../replay/clipPlayer";

function makeClip(id: string, startT: number, endT: number, startX: number, endX: number): TrajectoryClip {
  return {
    schema_version: "1.0.0",
    clip_id: id,
    pet_id: "pet_hammy_01",
    skill_id: "explore_area",
    seed: 42,
    origin: "observed_physics",
    behaviour_type: "learned",
    morphology_version: "hamster_v1.0.0",
    environment_version: "habitat_v1",
    fps: 20,
    start_sim_time_sec: startT,
    end_sim_time_sec: endT,
    keyframes: [
      {
        t_sec: 0,
        root_pos: [startX, 0.055, 0],
        root_quat: [0, 0, 0, 1],
        joint_angles: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        foot_contacts: [true, true, true, true],
      },
      {
        t_sec: endT - startT,
        root_pos: [endX, 0.055, 0],
        root_quat: [0, 0.7071, 0, 0.7071],
        joint_angles: [0.2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        foot_contacts: [false, true, true, false],
      },
    ],
  };
}

describe("P5.1 Trajectory ClipPlayer", () => {
  it("interpolates root pose and chains seamlessly across clips", () => {
    const player = new ClipPlayer();
    const c1 = makeClip("clip_1", 10.0, 12.0, 0.0, 0.2);
    const c2 = makeClip("clip_2", 12.0, 14.0, 0.2, 0.4);
    player.enqueue(c2); // out-of-order enqueue should sort by start_sim_time_sec
    player.enqueue(c1);

    const mid1 = player.step(1.0)!;
    expect(mid1.clipId).toBe("clip_1");
    expect(mid1.origin).toBe("observed_physics");
    expect(mid1.behaviourType).toBe("learned");
    expect(mid1.rootPos[0]).toBeCloseTo(0.1, 4);
    expect(mid1.jointAngles[0]).toBeCloseTo(0.1, 4);

    // Advance 1.5s -> 2.5s total -> 0.5s into clip_2
    const mid2 = player.step(1.5)!;
    expect(mid2.clipId).toBe("clip_2");
    expect(mid2.rootPos[0]).toBeCloseTo(0.25, 4);
  });

  it("resumes coherently at resumeSimTime after reconnecting from offline", () => {
    const player = new ClipPlayer();
    const c1 = makeClip("clip_1", 100.0, 102.0, 0.0, 0.2);
    const c2 = makeClip("clip_2", 102.0, 104.0, 0.2, 0.4);
    player.reconnectFrom([c1, c2], 103.0);

    const pose = player.samplePose()!;
    expect(pose.clipId).toBe("clip_2");
    expect(pose.rootPos[0]).toBeCloseTo(0.3, 4);
  });
});

