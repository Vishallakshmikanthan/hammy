"""Render Stage 1 10-second standing stability video and 4-view model inspection sheet."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import imageio.v2 as imageio
import mujoco
import numpy as np

from contracts.locomotion_contracts import (
    DEFAULT_STAND_JOINTS,
    MODEL_VERSION,
    export_locomotion_json_schemas,
)

MODEL_PATH = Path("simulation/models/hamster/hamster.xml")
OUT_DIR = Path("renders/stage1")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    export_locomotion_json_schemas(Path("contracts/json_schema"))

    model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
    data = mujoco.MjData(model)
    key_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "stand")
    mujoco.mj_resetDataKeyframe(model, data, key_id)
    mujoco.mj_forward(model, data)

    # Show visual geoms (group 2) and hide collision capsules (group 3) for clean render
    scene_opt = mujoco.MjvOption()
    scene_opt.geomgroup[2] = 1
    scene_opt.geomgroup[3] = 0

    renderer = mujoco.Renderer(model, height=540, width=960)

    # 1. Capture 4-view static hero sheet (3/4, side, front, top)
    cams = ["track_three_quarter", "track_side", "track_front", "track_top"]
    labels = ["Three-Quarter View", "Side Profile", "Front View", "Top View"]
    tiles = []
    for cam, label in zip(cams, labels):
        renderer.update_scene(data, camera=cam, scene_option=scene_opt)
        img = renderer.render().copy()
        img = cv2.resize(img, (480, 270))
        cv2.putText(img, label, (14, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 3)
        cv2.putText(img, label, (14, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        tiles.append(img)
    sheet = np.vstack([np.hstack(tiles[0:2]), np.hstack(tiles[2:4])])
    sheet_path = OUT_DIR / "hamster_model_4view.png"
    imageio.imwrite(sheet_path, sheet)

    # 2. Simulate 10.0 s standing and render 25 fps multi-angle video
    dt = model.opt.timestep
    sim_duration = 10.0
    video_fps = 25
    steps_per_frame = int(round((1.0 / video_fps) / dt))
    n_frames = int(round(sim_duration * video_fps))

    init_xy = data.qpos[0:2].copy()
    z_hist = []
    tilt_hist = []
    paw_forces = {k: [] for k in ("fl_touch", "fr_touch", "bl_touch", "br_touch")}
    sensor_ids = {k: model.sensor_adr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, k)] for k in paw_forces}

    frames = []
    for f_idx in range(n_frames):
        for _ in range(steps_per_frame):
            data.ctrl[:] = DEFAULT_STAND_JOINTS
            mujoco.mj_step(model, data)
            z_hist.append(float(data.qpos[2]))
            w, x, y, qz = data.qpos[3:7]
            up_z = 1.0 - 2.0 * (x * x + y * y)
            tilt_hist.append(float(np.degrees(np.arccos(np.clip(up_z, -1.0, 1.0)))))
            for k, adr in sensor_ids.items():
                paw_forces[k].append(float(data.sensordata[adr]))

        t_sec = (f_idx + 1) / video_fps
        cam_idx = min(3, int(t_sec // 2.5))
        renderer.update_scene(data, camera=cams[cam_idx], scene_option=scene_opt)
        frame = renderer.render().copy()
        drift = float(np.linalg.norm(data.qpos[0:2] - init_xy)) * 1000.0
        hud = f"{MODEL_VERSION} | t={t_sec:4.1f}s | {labels[cam_idx]} | z={data.qpos[2]*1000:.1f}mm | drift={drift:.2f}mm | tilt={tilt_hist[-1]:.2f}deg"
        cv2.rectangle(frame, (0, 0), (960, 36), (25, 25, 30), -1)
        cv2.putText(frame, hud, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)
        frames.append(frame)

    renderer.close()

    video_path = OUT_DIR / "hamster_stand_10s.mp4"
    imageio.mimsave(video_path, frames, fps=video_fps, quality=8)

    drift_final_mm = float(np.linalg.norm(data.qpos[0:2] - init_xy)) * 1000.0
    metrics = {
        "model_version": MODEL_VERSION,
        "total_mass_kg": round(float(np.sum(model.body_mass)), 4),
        "actuated_dof": int(model.nu),
        "sim_duration_s": sim_duration,
        "dt_s": dt,
        "nan_count": int(np.sum(~np.isfinite(data.qpos)) + np.sum(~np.isfinite(data.qvel))),
        "pelvis_z_min_mm": round(min(z_hist) * 1000.0, 2),
        "pelvis_z_max_mm": round(max(z_hist) * 1000.0, 2),
        "pelvis_z_final_mm": round(z_hist[-1] * 1000.0, 2),
        "max_tilt_deg": round(max(tilt_hist), 3),
        "final_xy_drift_mm": round(drift_final_mm, 3),
        "mean_paw_touch_N": {k: round(float(np.mean(v)), 3) for k, v in paw_forces.items()},
        "video_path": str(video_path),
        "four_view_path": str(sheet_path),
    }
    metrics_path = OUT_DIR / "standing_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
