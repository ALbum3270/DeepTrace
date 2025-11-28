from typing import List
from ..core.models.events import EventNode, EventStatus
from ..core.models.timeline import Timeline

def build_timeline(events: List[EventNode]) -> Timeline:
    """Assemble a list of EventNode objects into a Timeline.

    - Events are sorted chronologically by ``time`` (fallback to ``created_at``).
    - Each EventNode's ``evidence_ids`` list is left untouched; if missing, an empty list is set.
    - The returned ``Timeline`` contains the sorted events and an empty ``open_questions`` list.
    """
    # Ensure every event has an evidence_ids attribute (pydantic model may already have it)
    for ev in events:
        if not hasattr(ev, "evidence_ids") or ev.evidence_ids is None:
            ev.evidence_ids = []  # type: ignore[attr-defined]

    # Sort events by time; if time is None, use created_at as fallback
    sorted_events = sorted(
        events,
        key=lambda e: e.time if getattr(e, "time", None) is not None else getattr(e, "created_at", None)
    )

    # Build and return the Timeline
    return Timeline(events=sorted_events, open_questions=[])
