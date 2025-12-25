"""
Post-process Debater verdicts to update GlobalState.
"""

from typing import List, Dict, Any, Optional

from src.graph.state_v2 import GlobalState


def _find_last_resolve_call(messages: List[Any]) -> Dict[str, Any]:
    for idx in range(len(messages) - 1, -1, -1):
        msg = messages[idx]
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("name") == "ResolveConflict":
                    return tc
    return {}


def _extract_winner(verdict_text: str) -> Optional[str]:
    lowered = verdict_text.lower()
    # naive heuristic: look for "claim X" winner
    for token in ["claim 1", "claim one", "claim a"]:
        if token in lowered and ("true" in lowered or "wins" in lowered or "most likely" in lowered):
            return "Claim 1"
    for token in ["claim 2", "claim two", "claim b"]:
        if token in lowered and ("true" in lowered or "wins" in lowered or "most likely" in lowered):
            return "Claim 2"
    return None


def _conflict_key(topic: str, claims: List[str], source_ids: List[str]) -> tuple:
    return (
        (topic or "").strip().lower(),
        tuple(sorted(set(source_ids or []))),
        tuple(sorted(set(claims or []))),
    )


def debater_postprocess(state: GlobalState) -> Dict[str, Any]:
    """
    Append Debater verdicts into research_notes, timeline, and structured conflicts.
    """
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_msg = messages[-1]
    if getattr(last_msg, "type", None) != "tool":
        return {}

    verdict = getattr(last_msg, "content", "") or ""
    if not verdict:
        return {}

    tool_call = _find_last_resolve_call(messages)
    tool_args = tool_call.get("args", {}) if tool_call else {}
    topic = tool_args.get("topic", "Unknown")
    claims = tool_args.get("claims", [])
    source_ids = tool_args.get("source_ids", [])

    note_lines = [
        f"[Debater Verdict] Topic: {topic}",
    ]
    if claims:
        for i, claim in enumerate(claims):
            src = source_ids[i] if i < len(source_ids) else "Unknown"
            note_lines.append(f"- Claim {i + 1}: {claim} (Source: {src})")
    note_lines.append("Verdict:")
    note_lines.append(verdict.strip())
    note = "\n".join(note_lines)

    conflict_entry = {
        "topic": topic,
        "claims": claims,
        "source_ids": source_ids,
        "verdict": verdict.strip(),
        "winner": _extract_winner(verdict),
    }

    timeline_entry = {
        "title": f"Conflict Resolution: {topic}",
        "status": "resolved",
        "verdict": verdict.strip(),
        "claims": claims,
        "sources": source_ids,
    }

    existing_timeline = list(state.get("timeline", []))
    existing_timeline.append(timeline_entry)
    conflicts = list(state.get("conflicts", []))
    conflicts.append(conflict_entry)
    existing_candidates = list(state.get("conflict_candidates", []) or [])

    resolved_key = _conflict_key(topic, claims, source_ids)
    pruned_candidates = []
    for candidate in existing_candidates:
        if not candidate:
            continue
        candidate_key = _conflict_key(
            candidate.get("topic", ""),
            candidate.get("claims") or [],
            candidate.get("source_ids") or [],
        )
        if candidate_key == resolved_key:
            continue
        pruned_candidates.append(candidate)

    # Avoid duplicate note insertion if already present
    existing_notes = state.get("research_notes", []) or []
    new_notes: list[str] = []
    if note not in existing_notes:
        new_notes.append(note)

    update: Dict[str, Any] = {
        "investigation_log": [f"Conflict resolved for topic: {topic}"],
        "timeline": existing_timeline,
        "conflicts": conflicts,
    }
    if pruned_candidates != existing_candidates:
        update["conflict_candidates"] = pruned_candidates
    if new_notes:
        update["research_notes"] = new_notes
    return update
