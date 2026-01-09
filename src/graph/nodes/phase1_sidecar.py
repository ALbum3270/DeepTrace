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


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


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


async def phase1_sidecar_node(state: Dict[str, Any], config) -> Dict[str, Any]:
    evidences = state.get("evidences") or []
    timeline = _ensure_event_ids(state.get("timeline") or [])
    structured_report = state.get("structured_report", {})
    run_id = state.get("run_id", "run")
    key_claim_hints = _collect_key_claim_hints(structured_report)

    all_facts_items = []
    all_reports = []

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
        }
        snap = await build_document_snapshot_node(snapshot_input, config)
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

        # Build facts index for this doc: use timeline events as evidence list, with hint from title/description
        events_payload = []
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
                    "url": t.get("url"),
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
                "normalization_version": snap["document_snapshot"]["normalization_version"],
            },
            config,
        )

        # Gate1 audit for this doc (using structured_report if available)
        gate1_out = await gate1_evidence_audit_node(
            {
                "facts_index_v2": facts_out["facts_index_v2"],
                "document_snapshot": snap["document_snapshot"],
                "sentence_meta": idx["sentence_meta"],
                "structured_report": structured_report,
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
    (agg_dir / "facts_index_v2.json").write_text(
        json.dumps({"items": all_facts_items}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (agg_dir / "gate1_report.json").write_text(
        json.dumps({"entries": all_reports}, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {"phase1_archive": str(agg_dir)}
