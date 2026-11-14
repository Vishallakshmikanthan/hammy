"""
HAMMY — P8.1: Cinematic Render Queue & Verified Telegram Clip Delivery.
Captions are built strictly from verified recorded WorldEventV1 records and clip metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Literal

from contracts.schemas import TrajectoryClipV1, WorldEventV1

CameraPreset = Literal["low_macro", "three_quarter", "wide"]


@dataclass(frozen=True)
class RenderBudget:
    samples: int = 64
    res_x: int = 1280
    res_y: int = 720


@dataclass
class CinematicJob:
    clip_id: str
    seed: int
    camera_preset: CameraPreset
    budget: RenderBudget
    output_path: Path
    status: Literal["queued", "completed"] = "queued"


class CinematicRenderQueue:
    def __init__(self, output_dir: Path = Path("renders/cinematic")) -> None:
        self.output_dir = output_dir
        self.jobs: List[CinematicJob] = []

    def enqueue(
        self,
        clip: TrajectoryClipV1,
        camera_preset: CameraPreset = "three_quarter",
        budget: RenderBudget = RenderBudget(),
    ) -> CinematicJob:
        out_path = self.output_dir / f"{clip.clip_id}_{camera_preset}_seed{clip.seed}.mp4"
        job = CinematicJob(
            clip_id=clip.clip_id,
            seed=clip.seed,
            camera_preset=camera_preset,
            budget=budget,
            output_path=out_path,
        )
        self.jobs.append(job)
        return job


def build_verified_clip_caption(clip: TrajectoryClipV1, events: List[WorldEventV1]) -> str:
    """
    Build a Telegram caption strictly from verified recorded events and clip metadata.
    Never invents unrecorded observations.
    """
    matching = [
        e
        for e in events
        if e.pet_id == clip.pet_id
        and clip.start_sim_time_sec <= e.sim_time_sec <= clip.end_sim_time_sec
    ]
    lines = [
        f"Hammy Cinematic Moment — Skill: {clip.skill_id}",
        f"Origin: {clip.origin.value} | Behaviour: {clip.behaviour_type.value} | Seed: {clip.seed}",
    ]
    if matching:
        ev_summary = ", ".join(f"{e.event_type} ({e.origin.value})" for e in matching[:3])
        lines.append(f"Verified events: {ev_summary}")
    else:
        lines.append("Verified events: none recorded in window")
    return "\n".join(lines)


def deliver_cinematic_clip(
    chat_id: str,
    clip: TrajectoryClipV1,
    events: List[WorldEventV1],
    video_path: Path,
    send_video_fn: Callable[[str, Path, str], dict],
) -> dict:
    caption = build_verified_clip_caption(clip, events)
    return send_video_fn(chat_id, video_path, caption)

