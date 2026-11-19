"""Stage 2 acceptance tests: keypoints CSV, gait stats, REAL+SYNTHETIC reference clips, overlays."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from contracts.locomotion_contracts import (
    ACTUATED_JOINT_NAMES,
    JOINT_LIMITS_HIGH,
    JOINT_LIMITS_LOW,
    MODEL_VERSION,
)
from training.reference_library import ReferenceMotionLibrary, load_reference_clip


def test_keypoint_csvs_present_and_valid():
    for clip in ("video1_syrian_groom", "video6_wheel_run", "video7_platform_walk"):
        raw_p = Path(f"data/keypoints/{clip}_raw.csv")
        clean_p = Path(f"data/keypoints/{clip}_clean.csv")
        assert raw_p.exists(), f"Missing {raw_p}"
        assert clean_p.exists(), f"Missing {clean_p}"
        df = pd.read_csv(clean_p)
        assert len(df) >= 50
        for kp in ("nose", "mid_spine", "tail_base", "fl_paw", "bl_paw"):
            assert f"{kp}_x" in df.columns
            assert f"{kp}_y" in df.columns
            assert f"{kp}_conf" in df.columns


def test_reference_motion_library_modes_and_labeling():
    lib_all = ReferenceMotionLibrary("data/reference_motion", source_filter="mixed")
    lib_synth = ReferenceMotionLibrary("data/reference_motion", source_filter="synthetic")
    lib_real = ReferenceMotionLibrary("data/reference_motion", source_filter="real")

    assert len(lib_synth) >= 5, "Expected at least 5 SYNTHETIC gait clips"
    assert len(lib_real) >= 2, "Expected at least 2 REAL_VIDEO retargeted clips"
    assert len(lib_all) == len(lib_synth) + len(lib_real)

    # Every SYNTHETIC clip must carry explicit SYNTHETIC tag in clip_id & filename
    for p in Path("data/reference_motion").glob("*.npz"):
        clip = load_reference_clip(p)
        assert clip.model_version == MODEL_VERSION
        assert clip.joint_names == ACTUATED_JOINT_NAMES
        assert np.all(np.isfinite(clip.joint_angles))
        assert np.all(clip.joint_angles >= JOINT_LIMITS_LOW - 1e-4)
        assert np.all(clip.joint_angles <= JOINT_LIMITS_HIGH + 1e-4)
        if clip.source_type == "SYNTHETIC":
            assert "SYNTHETIC" in p.stem
            assert "SYNTHETIC" in clip.clip_id
        else:
            assert clip.source_type == "REAL_VIDEO"
            assert "SYNTHETIC" not in p.stem

    # Verify command-conditioned selection works across modes
    c_walk = lib_synth.select_for_command(vx_cmd=0.12, yaw_cmd=0.0)
    assert c_walk is not None
    sample = c_walk.sample_at_time(0.5)
    assert sample["joint_angles"].shape == (16,)
    assert sample["ref_phase"].shape == (2,)
    assert np.all(np.isfinite(sample["joint_angles"]))


def test_gait_statistics_and_overlays_exist():
    stats_p = Path("data/reference_motion/gait_statistics.json")
    assert stats_p.exists()
    stats = json.loads(stats_p.read_text(encoding="utf-8"))
    assert "real_video_measured" in stats
    assert "synthetic_reference_targets" in stats
    assert stats["real_video_measured"]["wheel_running_video6"]["stride_freq_hz"] > 0

    for video in (
        "renders/stage2/overlay_video1_keypoints.mp4",
        "renders/stage2/overlay_video6_wheel_keypoints.mp4",
        "renders/stage2/overlay_video7_walk_keypoints.mp4",
        "renders/stage2/mujoco_ref_video6_wheel_REAL.mp4",
        "renders/stage2/mujoco_ref_walk_slow_SYNTHETIC.mp4",
        "renders/stage2/mujoco_ref_trot_medium_SYNTHETIC.mp4",
        "renders/stage2/mujoco_ref_stop_start_SYNTHETIC.mp4",
    ):
        vp = Path(video)
        assert vp.exists() and vp.stat().st_size > 10_000, f"Missing or empty render: {vp}"
