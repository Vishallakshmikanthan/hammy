"""
HAMMY — P1.2: 100-Day Scripted Homeostatic Baseline Simulation & Plot Generator
(`scripts/run_100day_baseline.py`).
Runs `HabitatEnv` with `ScriptedHomeostaticBaselinePolicy` (explicitly labelled `scripted`)
for 100 simulated days (`dt_sec = 60.0 s`, 144,000 steps = 8,640,000 simulated seconds),
computes time-in-healthy-range per drive, saves a visual SVG/PNG plot of the drive trajectories,
and writes the verified results to `docs/research/baselines.md`.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
from simulation.habitat_env import HabitatEnv
from ai.policies.skills import ScriptedHomeostaticBaselinePolicy


def save_svg_drive_plot(days_arr: np.ndarray, history: dict[str, np.ndarray], healthy_pct: dict[str, float], out_path: Path):
    """Generates a clean high-resolution SVG chart of the 6 homeostatic drives + healthy range bars."""
    w, h = 1100, 680
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        '<rect width="100%" height="100%" fill="#11151c"/>',
        '<text x="40" y="42" fill="#f0f4f8" font-family="Segoe UI, sans-serif" font-size="22" font-weight="bold">'
        'HAMMY P1.2 — 100-Day Scripted Homeostatic Baseline (Label: scripted)</text>',
        '<text x="40" y="68" fill="#9fb3c8" font-family="Segoe UI, sans-serif" font-size="14">'
        'Left: 7-Day Circadian Drive Trajectory Sample | Right: 100-Day Time-in-Healthy-Range (%)</text>',
    ]

    # Left panel: 7-day sample trajectories
    px0, py0, pw, ph = 60, 105, 560, 500
    svg.append(f'<rect x="{px0}" y="{py0}" width="{pw}" height="{ph}" fill="#18202c" stroke="#2d3a4b" stroke-width="1.5" rx="6"/>')

    colors = {
        "hunger": "#ff7b54",
        "thirst": "#38bdf8",
        "energy": "#4ade80",
        "comfort": "#c084fc",
        "stress": "#f43f5e",
        "curiosity": "#facc15",
    }

    # Plot first 7 days (sampled every 20 steps for crisp SVG)
    mask_7d = days_arr <= 7.0
    t_7d = days_arr[mask_7d][::6]
    for idx, (d_name, col) in enumerate(colors.items()):
        vals = history[d_name][mask_7d][::6]
        pts = []
        for t_val, v_val in zip(t_7d, vals):
            x = px0 + (t_val / 7.0) * pw
            y = py0 + ph - v_val * ph
            pts.append(f"{x:.1f},{y:.1f}")
        svg.append(f'<polyline fill="none" stroke="{col}" stroke-width="1.8" stroke-opacity="0.88" points="{" ".join(pts)}"/>')
        lx = px0 + 16 + (idx % 3) * 180
        ly = py0 + ph + 28 + (idx // 3) * 24
        svg.append(f'<rect x="{lx}" y="{ly - 11}" width="12" height="12" fill="{col}" rx="2"/>')
        svg.append(f'<text x="{lx + 18}" y="{ly}" fill="#d9e2ec" font-family="Segoe UI, sans-serif" font-size="13">{d_name.capitalize()}</text>')

    # Right panel: 100-Day Time-in-Healthy-Range bar chart
    bx0, by0, bw, bh = 670, 105, 380, 500
    svg.append(f'<rect x="{bx0}" y="{by0}" width="{bw}" height="{bh}" fill="#18202c" stroke="#2d3a4b" stroke-width="1.5" rx="6"/>')
    svg.append(f'<text x="{bx0 + 20}" y="{by0 + 34}" fill="#f0f4f8" font-family="Segoe UI, sans-serif" font-size="16" font-weight="bold">Time-in-Healthy-Range (100 Days)</text>')

    for idx, (d_name, col) in enumerate(colors.items()):
        pct = healthy_pct[d_name]
        y_bar = by0 + 70 + idx * 68
        bar_max_w = 240
        bar_w = max(2.0, (pct / 100.0) * bar_max_w)
        svg.append(f'<text x="{bx0 + 20}" y="{y_bar + 18}" fill="#d9e2ec" font-family="Segoe UI, sans-serif" font-size="14" font-weight="600">{d_name.capitalize()}</text>')
        svg.append(f'<rect x="{bx0 + 105}" y="{y_bar}" width="{bar_max_w}" height="26" fill="#243040" rx="4"/>')
        svg.append(f'<rect x="{bx0 + 105}" y="{y_bar}" width="{bar_w:.1f}" height="26" fill="{col}" rx="4"/>')
        svg.append(f'<text x="{bx0 + 105 + bar_max_w + 10}" y="{y_bar + 18}" fill="#f0f4f8" font-family="Segoe UI, sans-serif" font-size="14" font-weight="bold">{pct:.1f}%</text>')

    svg.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(svg), encoding="utf-8")


def main():
    days = 100
    dt_sec = 300.0  # 5-minute resolution across 100 simulated days (28,800 steps)
    total_steps = int((days * 86400.0) / dt_sec)

    env = HabitatEnv(max_episode_steps=total_steps + 10, dt_sec=dt_sec)
    policy = ScriptedHomeostaticBaselinePolicy()

    obs, _ = env.reset(seed=101)

    drive_names = ["hunger", "thirst", "energy", "comfort", "stress", "curiosity"]
    healthy_counts = {k: 0 for k in drive_names}
    history = {k: np.empty(total_steps, dtype=np.float32) for k in drive_names}
    skill_counts: dict[str, int] = {}
    total_reward = 0.0

    t0 = time.perf_counter()
    for step_idx in range(total_steps):
        action, skill_name = policy.act(obs)
        skill_counts[skill_name] = skill_counts.get(skill_name, 0) + 1
        obs, reward, _, _, info = env.step(action)
        total_reward += reward

        flags = info["healthy_flags"]
        for k in drive_names:
            val = getattr(obs.drives, k)
            history[k][step_idx] = val
            if flags[k]:
                healthy_counts[k] += 1

    elapsed = time.perf_counter() - t0
    healthy_pct = {k: 100.0 * healthy_counts[k] / total_steps for k in drive_names}
    mean_healthy = float(np.mean(list(healthy_pct.values())))

    days_arr = np.arange(total_steps, dtype=np.float32) * (dt_sec / 86400.0)
    svg_path = ROOT_DIR / "docs" / "research" / "baseline_100days_drives.svg"
    save_svg_drive_plot(days_arr, history, healthy_pct, svg_path)

    doc_path = ROOT_DIR / "docs" / "research" / "baselines.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# HAMMY — P1.2 Homeostatic Drives & 100-Day Baseline Report\n",
        "- **Behaviour Label (Non-Negotiable Rule 1):** `scripted` (`ScriptedHomeostaticBaselinePolicy`)",
        "- **Event Origin (Non-Negotiable Rule 2):** `observed_physics`",
        f"- **Simulated Duration:** `100.0 days` (`{total_steps:,}` steps at `dt = {dt_sec:.0f} s`)",
        f"- **Wall-Clock Execution Time:** `{elapsed:.2f} seconds` (`{total_steps / max(elapsed, 1e-6):,.0f}` steps/sec)",
        f"- **Cumulative Homeostatic Reward:** `{total_reward:+.4f}`",
        f"- **Plot Artifact:** `docs/research/baseline_100days_drives.svg`\n",
        "## 1. Time-in-Healthy-Range Across 100 Simulated Days (`scripted`)\n",
        "| Drive | Healthy Bounds | Mean Value | Min / Max | Time in Healthy Range (%) |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    hr = env.drives.cfg["healthy_ranges"]
    for k in drive_names:
        arr = history[k]
        lines.append(
            f"| **{k.capitalize()}** | `[{hr[k][0]:.2f}, {hr[k][1]:.2f}]` | `{float(np.mean(arr)):.3f}` | "
            f"`{float(np.min(arr)):.3f}` / `{float(np.max(arr)):.3f}` | **{healthy_pct[k]:.2f}%** |"
        )
    lines.append(f"\n- **Overall Mean Time-in-Healthy-Range:** **{mean_healthy:.2f}%**\n")
    lines.append("## 2. Skill Allocation Distribution (`scripted`)\n")
    lines.append("| Skill Name | Steps Selected | Share of 100 Days (%) |")
    lines.append("| :--- | :--- | :--- |")
    for sk, cnt in sorted(skill_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| `{sk}` | {cnt:,} | {100.0 * cnt / total_steps:.2f}% |")

    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=" * 72)
    print(f" HAMMY P1.2 — 100-DAY HOMEOSTATIC BASELINE COMPLETE ({elapsed:.2f} s)")
    print("=" * 72)
    for k in drive_names:
        print(f"  * {k:10s} : {healthy_pct[k]:6.2f}% in healthy range (mean={float(np.mean(history[k])):.3f})")
    print(f"  * OVERALL    : {mean_healthy:6.2f}% mean time-in-healthy-range (labelled `scripted`)")
    print(f">> Saved report : {doc_path}")
    print(f">> Saved plot   : {svg_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()
