"""
HAMMY — Daily Digest Builder (`services/notification_worker/digest.py`).
Implements Criterion 4:
  Daily digest built ONLY from recorded events; include event origin (observed vs sampled vs rule) in plain language.
"""

from __future__ import annotations

import collections
import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from infrastructure.database.models import Pet, PetState, WorldEvent

ORIGIN_DESCRIPTIONS = {
    "observed_physics": "Simulated in full 3D physics",
    "sampled_from_skill_model": "Predicted by behavioral AI model",
    "rule": "Care action / Game rule",
}


def _ensure_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


class DailyDigestBuilder:
    """Builds transparent daily summaries strictly from persisted world events."""

    @staticmethod
    def build_digest(
        session: Session,
        pet_id: str,
        since_time: Optional[datetime.datetime] = None,
        now: Optional[datetime.datetime] = None,
    ) -> Dict[str, Any]:
        curr_time = _ensure_utc(now or datetime.datetime.now(datetime.timezone.utc))
        lookback = _ensure_utc(since_time or (curr_time - datetime.timedelta(days=1)))

        pet = session.get(Pet, pet_id)
        if not pet:
            raise ValueError(f"Pet '{pet_id}' not found.")

        pet_state = session.get(PetState, pet_id)

        # 1. Query recorded events in interval
        events = (
            session.query(WorldEvent)
            .filter(
                WorldEvent.pet_id == pet_id,
                WorldEvent.created_at >= lookback,
                WorldEvent.created_at <= curr_time,
            )
            .order_by(WorldEvent.world_tick.asc())
            .all()
        )

        # 2. Aggregations
        skill_counts: Dict[str, int] = collections.defaultdict(int)
        origin_counts: Dict[str, int] = collections.defaultdict(int)
        care_actions_count = 0

        for e in events:
            origin_counts[e.origin] += 1
            if e.skill_name:
                skill_counts[e.skill_name] += 1
            if e.event_type.startswith("care_"):
                care_actions_count += 1

        # 3. Format plain-language Telegram HTML
        drives = pet_state.drives if pet_state else {}
        hunger_pct = int(drives.get("hunger", 0.0) * 100)
        thirst_pct = int(drives.get("thirst", 0.0) * 100)
        energy_pct = int(drives.get("energy", 0.0) * 100)
        comfort_pct = int(drives.get("comfort", 0.0) * 100)
        stress_pct = int(drives.get("stress", 0.0) * 100)

        html_lines = [
            f"🐹 <b>{pet.name}'s Daily Activity Digest</b>",
            f"<i>Period: {lookback.strftime('%b %d, %H:%M')} – {curr_time.strftime('%b %d, %H:%M')} UTC</i>\n",
            "📊 <b>Activity Breakdown (from recorded events):</b>",
            f"• Total events recorded: <b>{len(events)}</b>",
            f"• Eating meals: <b>{skill_counts.get('eat', 0) + skill_counts.get('approach_food', 0)}</b>",
            f"• Water bottle drinks: <b>{skill_counts.get('drink', 0)}</b>",
            f"• Wheel running sessions: <b>{skill_counts.get('run_on_wheel', 0)}</b>",
            f"• Burrow/hideout resting: <b>{skill_counts.get('rest', 0) + skill_counts.get('hide', 0)}</b>",
            f"• Cage explorations: <b>{skill_counts.get('explore_area', 0)}</b>",
            f"• Parent care interactions: <b>{care_actions_count}</b>\n",
            "🧬 <b>Event Provenance (Honesty Rules):</b>",
        ]

        if not origin_counts:
            html_lines.append("• <i>No events logged during this window.</i>")
        else:
            for origin_key, desc in ORIGIN_DESCRIPTIONS.items():
                count = origin_counts.get(origin_key, 0)
                html_lines.append(f"• {desc}: <b>{count} events</b>")

        html_lines.extend([
            "\n❤️ <b>Current Physiological Status:</b>",
            f"• Hunger: <b>{hunger_pct}%</b>",
            f"• Thirst: <b>{thirst_pct}%</b>",
            f"• Energy: <b>{energy_pct}%</b>",
            f"• Comfort: <b>{comfort_pct}%</b>",
            f"• Stress: <b>{stress_pct}%</b>",
        ])

        html_text = "\n".join(html_lines)

        return {
            "pet_id": pet_id,
            "pet_name": pet.name,
            "period_start": lookback.isoformat(),
            "period_end": curr_time.isoformat(),
            "total_events": len(events),
            "skill_counts": dict(skill_counts),
            "origin_counts": dict(origin_counts),
            "care_actions_count": care_actions_count,
            "html_message": html_text,
        }

