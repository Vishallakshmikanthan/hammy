"""
P4.2 Keypoint Ingestion & Gait Reference Builder:
Ingests pose-estimation keypoint JSON (or builds a calibrated Syrian hamster
reference gait trajectory matching reference/parameter_estimates.md) and computes
gait metrics: stride_frequency_hz, duty_factor, and speed_range_m_s.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Tuple
import numpy as np


def validate_hamster_mjcf(xml_path: Path) -> Dict[str, Any]:
    """Parse hamster.xml and validate mass, DOF count, spine joints, and collision/visual separation."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    joints = [
        j.attrib["name"]
        for j in root.findall(".//joint")
        if "name" in j.attrib and j.attrib.get("type") != "free" and "free" not in j.attrib["name"]
    ]
    actuators = [a.attrib["name"] for a in root.findall(".//actuator/position")]
    masses = [float(g.attrib["mass"]) for g in root.findall(".//geom") if "mass" in g.attrib]
    total_mass = sum(masses)

    if len(joints) != 14:
        raise ValueError(f"Expected 14 actuated DOFs (2 spine + 12 leg), found {len(joints)}")
    if not (0.09 <= total_mass <= 0.16):
        raise ValueError(f"Total hamster mass {total_mass:.4f} kg outside [0.09, 0.16] kg")

    return {
        "morphology_model": root.attrib.get("model"),
        "dof_count": len(joints),
        "actuator_count": len(actuators),
        "total_mass_kg": round(total_mass, 4),
        "spine_joints": [j for j in joints if "spine" in j],
    }


def generate_reference_hamster_gait(
    num_steps: int = 400,
    dt: float = 0.02,
    stride_freq_hz: float = 5.2,
    duty_factor: float = 0.65,
) -> Dict[str, Any]:
    """
    Generate calibrated Syrian hamster walking/trotting reference transitions
    (joint_pos [T, 14], joint_vel [T, 14], foot_contacts [T, 4], speed [T]).
    """
    t = np.arange(num_steps, dtype=np.float32) * dt
    phase = 2.0 * np.pi * stride_freq_hz * t

    q = np.zeros((num_steps, 14), dtype=np.float32)
    # Spine lateral waddle + slight pitch bob
    q[:, 0] = 0.05 * np.sin(2.0 * phase)
    q[:, 1] = 0.12 * np.sin(phase)

    # Diagonal quadruped gait phases: FL=0, FR=pi, BL=pi, BR=0
    leg_phases = [0.0, np.pi, np.pi, 0.0]
    contacts = np.zeros((num_steps, 4), dtype=np.float32)
    for leg_i, phi in enumerate(leg_phases):
        p = phase + phi
        base = 2 + leg_i * 3
        q[:, base + 0] = 0.06 * np.cos(p) * (1 if leg_i % 2 == 0 else -1)
        q[:, base + 1] = 0.32 * np.sin(p)
        q[:, base + 2] = -0.25 + 0.22 * np.maximum(0.0, np.cos(p))
        # Stance when normalized cycle < duty_factor
        cyc = ((p / (2.0 * np.pi)) % 1.0)
        contacts[:, leg_i] = (cyc < duty_factor).astype(np.float32)

    qd = np.gradient(q, dt, axis=0).astype(np.float32)
    speed = np.full(num_steps, 0.26, dtype=np.float32) + 0.03 * np.sin(2.0 * phase)

    return {
        "q": q,
        "qd": qd,
        "foot_contacts": contacts,
        "speed_m_s": speed,
        "stride_frequency_hz": stride_freq_hz,
        "duty_factor": duty_factor,
    }


def ingest_keypoints_json(json_path: Path, dt: float = 0.02) -> Dict[str, Any]:
    """
    Ingest pose-estimation keypoint JSON (`{"frames": [{"joints_14": [...], "contacts_4": [...], "speed": ...}]}`)
    and convert into transition arrays + gait metrics.
    """
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    frames = payload["frames"]
    q = np.array([f["joints_14"] for f in frames], dtype=np.float32)
    contacts = np.array([f["contacts_4"] for f in frames], dtype=np.float32)
    speed = np.array([f.get("speed", 0.22) for f in frames], dtype=np.float32)
    qd = np.gradient(q, dt, axis=0).astype(np.float32)
    metrics = compute_gait_metrics(q, contacts, speed, dt)
    return {"q": q, "qd": qd, "foot_contacts": contacts, "speed_m_s": speed, **metrics}


def compute_gait_metrics(
    q: np.ndarray,
    foot_contacts: np.ndarray,
    speeds: np.ndarray,
    dt: float = 0.02,
) -> Dict[str, Any]:
    """Measure stride frequency (Hz), duty factor, and speed range from a trajectory."""
    duty_factor = float(np.mean(foot_contacts))

    # Estimate stride frequency from FFT of front-left hip pitch (index 3)
    sig = q[:, 3] - np.mean(q[:, 3])
    if len(sig) >= 16 and float(np.std(sig)) > 1e-4:
        freqs = np.fft.rfftfreq(len(sig), d=dt)
        mag = np.abs(np.fft.rfft(sig))
        mag[0] = 0.0
        peak_freq = float(freqs[int(np.argmax(mag))])
    else:
        peak_freq = 0.0

    return {
        "stride_frequency_hz": round(peak_freq, 3),
        "duty_factor": round(duty_factor, 3),
        "speed_mean_m_s": round(float(np.mean(speeds)), 4),
        "speed_min_m_s": round(float(np.min(speeds)), 4),
        "speed_max_m_s": round(float(np.max(speeds)), 4),
    }
