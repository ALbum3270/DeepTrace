"""
Timeline merge node for DeepTrace V2.
Merges same-topic multi-version entries into a structured single entry.
"""

from typing import Any, Dict, List, Tuple, TYPE_CHECKING
import re

from src.graph.state_v2 import GlobalState

VERSION_PATTERNS = [
    re.compile(r"\b(?:v|ver|version)\s*([0-9]+(?:\.[0-9]+){0,2})\b", re.IGNORECASE),
]


def _extract_versions(text: str) -> List[str]:
    if not text:
        return []
    versions: List[str] = []
    for pattern in VERSION_PATTERNS:
        for match in pattern.findall(text):
            version = match if isinstance(match, str) else match[0]
            if version:
                versions.append(f"v{version}")
    # Deduplicate while preserving order
    seen = set()
    deduped: List[str] = []
    for v in versions:
        if v not in seen:
            seen.add(v)
            deduped.append(v)
    return deduped


def _strip_version_tokens(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    for pattern in VERSION_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return cleaned


def _normalize_topic_key(text: str) -> str:
    if not text:
        return ""
    cleaned = _strip_version_tokens(text)
    cleaned = cleaned.lower()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"[^a-z0-9\s]+", "", cleaned)
    return cleaned.strip()


def _build_variants(entries: List[dict]) -> Tuple[List[str], List[str], List[str]]:
    variants: List[str] = []
    versions: List[str] = []
    sources: List[str] = []

    for entry in entries:
        title = entry.get("title") or ""
        description = entry.get("description") or ""
        source = entry.get("source") or "Unknown"
        text = f"{title} {description}"
        entry_versions = _extract_versions(text)
        versions.extend(entry_versions)
        sources.append(source)

        version_label = ", ".join(entry_versions) if entry_versions else "unspecified"
        variants.append(f"- {version_label}: {title} {description} (Source: {source})".strip())

    # Deduplicate versions and sources
    versions = list(dict.fromkeys([v for v in versions if v]))
    sources = list(dict.fromkeys([s for s in sources if s and s != "Unknown"]))
    return variants, versions, sources


def _merge_group(date: str, entries: List[dict]) -> dict:
    base_title_raw = entries[0].get("title") or entries[0].get("description") or "Topic"
    base_title = _strip_version_tokens(base_title_raw).strip() or base_title_raw
    variants, versions, sources = _build_variants(entries)

    description_lines = ["Multiple versions reported for the same topic."]
    if versions:
        description_lines.append(f"Versions: {', '.join(versions)}")
    if variants:
        description_lines.append("Variant details:")
        description_lines.extend(variants)
    if sources:
        description_lines.append(f"Sources: {', '.join(sources)}")

    return {
        "date": date,
        "title": f"[Disputed] {base_title}",
        "description": "\n".join(description_lines).strip(),
        "source": None,
        "versions": versions,
        "sources": sources,
        "merge_type": "multi_version",
    }


def merge_timeline_entries(timeline: List[dict]) -> List[dict]:
    if not timeline:
        return []

    grouped: Dict[Tuple[str, str], List[dict]] = {}
    passthrough: List[dict] = []

    for entry in timeline:
        if not isinstance(entry, dict):
            continue
        title = entry.get("title") or ""
        if title.lower().startswith("conflict resolution"):
            passthrough.append(entry)
            continue

        date = entry.get("date") or entry.get("time") or entry.get("timestamp") or "Unknown"
        if date == "Unknown":
            passthrough.append(entry)
            continue

        text = f"{title} {entry.get('description', '')}"
        versions = _extract_versions(text)
        if not versions:
            passthrough.append(entry)
            continue

        base_key = _normalize_topic_key(title or entry.get("description", ""))
        if not base_key:
            passthrough.append(entry)
            continue

        grouped.setdefault((date, base_key), []).append(entry)

    merged: List[dict] = []
    for (date, _), entries in grouped.items():
        all_versions: List[str] = []
        for entry in entries:
            all_versions.extend(_extract_versions(f"{entry.get('title','')} {entry.get('description','')}"))
        unique_versions = sorted(set(all_versions))
        if len(unique_versions) < 2:
            merged.extend(entries)
            continue
        merged.append(_merge_group(date, entries))

    return passthrough + merged


def timeline_merge_node(state: "GlobalState") -> Dict[str, Any]:
    """
    Merge same-topic multi-version timeline entries to reduce noise and avoid conflicting duplicates.
    """
    timeline = state.get("timeline", []) or []
    merged = merge_timeline_entries(timeline)
    return {"timeline": merged}
