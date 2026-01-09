"""
Phase1 Sidecar Node
Minimal-intrusion post-processing hook:
- Iterate evidences (with full_content/url)
- For each: ExtractMainText -> DocumentSnapshot -> Chunk/Sentence Index
- Aggregate events (with hints) -> FactsIndex_v2
- Gate1 Audit
- Archive artifacts under artifacts/phase1/<run_id>/<doc_id> and global facts/gate1.

Assumptions:
- state["evidences"]: list of dicts with keys: id?, full_content?, url?, title/description as hints
- state["timeline"]: list of events {event_id?, title, description, url}
- state may contain structured_report for key_claim roles; if missing, Gate1 will treat roles as None.
"""

import hashlib
from pathlib import Path
import json
from typing import Dict, Any, List, DefaultDict
from collections import defaultdict

from src.graph.nodes.extract_main_text import extract_main_text_node
from src.graph.nodes.build_document_snapshot import build_document_snapshot_node
from src.graph.nodes.chunk_and_sentence_index import chunk_and_sentence_index_node
from src.graph.nodes.build_facts_index_v2 import build_facts_index_v2_node
from src.graph.nodes.gate1_evidence_audit import gate1_evidence_audit_node
from src.graph.nodes.archive_phase1 import archive_phase1_node
from src.graph.nodes.doc_version_cdc import doc_version_cdc_node


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

def _normalize_url(url: str) -> str:
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url or "")
        # drop query/fragment; normalize path trailing slash
        path = (parsed.path or "").rstrip("/")
        normalized = parsed._replace(path=path, query="", fragment="")
        return urlunparse(normalized)
    except Exception:
        return (url or "").rstrip("/")


def _ensure_event_ids(events: List[dict]) -> List[dict]:
    result = []
    for ev in events or []:
        eid = ev.get("event_id")
        if not eid:
            base = (ev.get("title") or "") + (ev.get("description") or "") + (ev.get("url") or "")
            eid = "ev_" + _hash(base)[:12]
        ev["event_id"] = eid
        result.append(ev)
    return result


def _collect_key_claim_hints(structured_report: dict) -> Dict[str, List[str]]:
    """
    Build event_id -> [hints] mapping using key_claim item_text, which is closer to source sentences than timeline summaries.
    """
    hints: DefaultDict[str, List[str]] = defaultdict(list)
    # sectioned format
    for section in structured_report.get("sections", []) or []:
        for it in section.get("items", []) or []:
            if it.get("role") != "key_claim":
                continue
            text = it.get("item_text") or ""
            for eid in it.get("event_ids") or []:
                if text:
                    hints[eid].append(text)
    # fallback flat items
    for it in structured_report.get("items", []) or []:
        if it.get("role") != "key_claim":
            continue
        text = it.get("item_text") or ""
        eid = it.get("event_id")
        if eid and text:
            hints[eid].append(text)
    return hints


def _facts_for_doc(facts_index: dict, doc_url: str) -> List[dict]:
    """
    Prefer finalizer-produced facts_index because it assigns canonical event_ids that structured_report cites.
    Filter facts down to those that reference this document URL.
    """
    facts = (facts_index or {}).get("facts") or []
    if not doc_url:
        return list(facts)
    doc_norm = _normalize_url(doc_url)
    selected = []
    for fact in facts:
        evidences = fact.get("evidences") or []
        for evd in evidences:
            if _normalize_url(evd.get("url") or "") == doc_norm:
                selected.append(fact)
                break
    return selected


def _collect_roles(structured_report: dict) -> Dict[str, str]:
    roles: Dict[str, str] = {}
    for section in structured_report.get("sections", []) or []:
        for it in section.get("items", []) or []:
            role = it.get("role")
            for eid in it.get("event_ids") or []:
                if role and eid:
                    roles[eid] = role
    for it in structured_report.get("items", []) or []:
        eid = it.get("event_id")
        role = it.get("role")
        if role and eid:
            roles[eid] = role
    return roles


async def phase1_sidecar_node(state: Dict[str, Any], config) -> Dict[str, Any]:
    evidences = state.get("evidences") or []
    timeline = _ensure_event_ids(state.get("timeline") or [])
    structured_report = state.get("structured_report", {})
    facts_index = state.get("facts_index") or {}
    run_id = state.get("run_id", "run")
    key_claim_hints = _collect_key_claim_hints(structured_report)
    roles = _collect_roles(structured_report)

    all_facts_items = []
    all_reports = []
    doc_versions_summary = []

    for evd in evidences:
        raw_html = evd.get("full_content") or ""
        url = evd.get("url") or ""
        if not raw_html:
            continue

        doc_id = evd.get("id") or _hash(url)[:12]
        # Extract main text
        emt = await extract_main_text_node({"raw_html": raw_html}, config)
        # Build snapshot
        snapshot_input = {
            "cleaned_text": emt["cleaned_text"],
            "final_url": url,
            "extractor_version": emt.get("extractor_version"),
            "doc_quality_flags": emt.get("doc_quality_flags"),
            "doc_id": doc_id,
            "run_id": run_id,
            "source": evd.get("source"),
        }
        snap = await build_document_snapshot_node(snapshot_input, config)
        # Phase2 CDC: record this doc version per URL key
        cdc_out = doc_version_cdc_node({"document_snapshot": snap["document_snapshot"], "run_id": run_id})
        doc_versions_summary.append(
            {
                "doc_id": snap["document_snapshot"].get("doc_id"),
                "doc_key": cdc_out.get("doc_key"),
                "doc_version_id": cdc_out.get("doc_version_id"),
                "previous_latest_doc_version_id": cdc_out.get("previous_latest_doc_version_id"),
                "drift_status": cdc_out.get("drift_status"),
                "doc_version_cdc_path": cdc_out.get("doc_version_cdc_path"),
                "final_url": snap["document_snapshot"].get("final_url"),
            }
        )
        # Chunk/Sentence index
        idx = await chunk_and_sentence_index_node(
            {
                "cleaned_text": emt["cleaned_text"],
                "doc_id": doc_id,
                "normalization_version": snap["document_snapshot"]["normalization_version"],
                "run_id": run_id,
            },
            config,
        )

        # Build facts index for this doc:
        # Prefer finalizer facts_index (canonical event_id) filtered by this URL;
        # fallback to timeline events if facts_index is missing.
        events_payload = []
        per_doc_facts = _facts_for_doc(facts_index, url)
        if per_doc_facts:
            for fact in per_doc_facts:
                event_id = fact.get("event_id")
                if not event_id:
                    continue
                hint_parts = []
                if key_claim_hints.get(event_id):
                    hint_parts.extend(key_claim_hints[event_id])
                title = (fact.get("title") or "").strip()
                date = (fact.get("date") or "").strip()
                if title or date:
                    hint_parts.append(f"{date} {title}".strip())
                for evd in fact.get("evidences") or []:
                    evd_hint = (evd.get("evidence_quote") or "").strip()
                    if evd_hint:
                        hint_parts.append(evd_hint)
                events_payload.append(
                    {
                        "event_id": event_id,
                        "url": url,
                        "credibility_tier": None,
                        "evidence_hint": " | ".join(hint_parts) if hint_parts else None,
                    }
                )
        else:
            for t in timeline:
                hint_parts = []
                if key_claim_hints.get(t["event_id"]):
                    hint_parts.extend(key_claim_hints[t["event_id"]])
                tl_hint = f"{t.get('title','')} {t.get('description','')}".strip()
                if tl_hint:
                    hint_parts.append(tl_hint)
                events_payload.append(
                    {
                        "event_id": t["event_id"],
                        "url": t.get("url") or url,
                        "credibility_tier": None,
                        "evidence_hint": " | ".join(hint_parts) if hint_parts else None,
                    }
                )

        facts_out = await build_facts_index_v2_node(
            {
                "cleaned_text": emt["cleaned_text"],
                "sentence_meta": idx["sentence_meta"],
                "events": events_payload,
                "doc_id": doc_id,
                "doc_key": snap["document_snapshot"].get("doc_key"),
                "doc_version_id": snap["document_snapshot"].get("doc_version_id"),
                "normalization_version": snap["document_snapshot"]["normalization_version"],
            },
            config,
        )

        # Gate1 audit for this doc (using structured_report if available)
        drift_map = {it.get("doc_key"): it.get("drift_status") for it in doc_versions_summary if it.get("doc_key")}
        gate1_out = await gate1_evidence_audit_node(
            {
                "facts_index_v2": facts_out["facts_index_v2"],
                "document_snapshot": snap["document_snapshot"],
                "sentence_meta": idx["sentence_meta"],
                "structured_report": structured_report,
                "doc_drift_by_key": drift_map,
            },
            config,
        )

        # Archive per-doc
        archive_state = {
            "run_id": run_id + f"_{doc_id}",
            "document_snapshot": snap["document_snapshot"],
            "chunk_meta": idx["chunk_meta"],
            "sentence_meta": idx["sentence_meta"],
            "index_manifest": idx["index_manifest"],
            "facts_index_v2": facts_out["facts_index_v2"],
            "gate1_report": gate1_out["gate1_report"],
            "metrics_summary": gate1_out.get("metrics_summary"),
        }
        await archive_phase1_node(archive_state, config)

        all_facts_items.extend(facts_out["facts_index_v2"]["items"])
        all_reports.extend(gate1_out["gate1_report"]["entries"])

    # Aggregate facts/report
    agg_dir = Path("artifacts") / "phase1" / run_id
    agg_dir.mkdir(parents=True, exist_ok=True)

    # If we have structured_report roles, ensure key_claims that couldn't be processed still appear as SOFT gaps.
    ok_event_ids = {e.get("event_id") for e in all_reports if e.get("severity") == "OK"}
    seen_event_ids = {e.get("event_id") for e in all_reports}
    key_claim_event_ids = {eid for eid, role in roles.items() if role == "key_claim"}
    for eid in sorted(key_claim_event_ids):
        if eid in seen_event_ids:
            continue
        all_reports.append(
            {
                "event_id": eid,
                "severity": "SOFT",
                "message": "Unlocatable evidence: NO_DOCUMENT_SNAPSHOT",
                "role": "key_claim",
            }
        )

    key_claim_total = len(key_claim_event_ids)
    key_claim_locatable = len([eid for eid in key_claim_event_ids if eid in ok_event_ids])
    key_claim_locatable_rate = (key_claim_locatable / key_claim_total) if key_claim_total else None
    locatable_total = len(all_reports)
    locatable_ok = len([e for e in all_reports if e.get("severity") == "OK"])
    locatable_rate_overall = (locatable_ok / locatable_total) if locatable_total else None
    reason_counts: Dict[str, int] = {}
    for e in all_reports:
        msg = e.get("message") or ""
        if msg.startswith("Unlocatable evidence: "):
            reason = msg.split("Unlocatable evidence: ", 1)[1].strip()
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    (agg_dir / "facts_index_v2.json").write_text(
        json.dumps({"items": all_facts_items}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (agg_dir / "gate1_report.json").write_text(
        json.dumps(
            {"entries": all_reports, "key_claim_locatable_rate": key_claim_locatable_rate},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (agg_dir / "metrics_summary.json").write_text(
        json.dumps(
            {
                "key_claim_locatable_rate": key_claim_locatable_rate,
                "locatable_rate_overall": locatable_rate_overall,
                "reason_counts": reason_counts,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    # Phase2 CDC summary for this run
    (agg_dir / "doc_versions_summary.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "documents": doc_versions_summary,
                "summary": {
                    "docs_total": len(doc_versions_summary),
                    "docs_changed": len([d for d in doc_versions_summary if d.get("drift_status") == "CHANGED_SINCE_LAST_SEEN"]),
                    "docs_unchanged": len([d for d in doc_versions_summary if d.get("drift_status") == "UNCHANGED"]),
                    "docs_first_seen": len([d for d in doc_versions_summary if d.get("drift_status") == "FIRST_SEEN"]),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {"phase1_archive": str(agg_dir)}
