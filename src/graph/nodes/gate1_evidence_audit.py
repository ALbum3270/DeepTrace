"""
Phase1 - Gate1EvidenceAuditNode
Validates facts_index_v2 against DocumentSnapshot and Indexes.
Rules:
 - doc_ref must be parseable (doc_id/chunk_id/sentence_ids)
 - evidence_quote must be reproducible from cleaned_text/sentences (same normalization)
 - role=key_claim (from structured_report) missing locatable evidence => SOFT
 - non key_claim missing => WARN
Outputs gate1_report + metrics_summary (key_claim_locatable_rate).
"""

from typing import Dict, Any, List
from src.core.models.phase1 import Gate1Entry, Gate1Report


def _find_sentence_text(doc: str, sentences: List[dict], sentence_ids: List[str]) -> str:
    spans = []
    for sid in sentence_ids:
        for s in sentences:
            if s["sentence_id"] == sid:
                spans.append((s["start"], s["end"]))
    if not spans:
        return ""
    start = min(s for s, _ in spans)
    end = max(e for _, e in spans)
    return doc[start:end]


async def gate1_evidence_audit_node(state: Dict[str, Any], config) -> Dict[str, Any]:
    facts = state.get("facts_index_v2", {}) or {}
    doc = state.get("document_snapshot", {}) or {}
    sentences = state.get("sentence_meta", []) or []
    structured_report = state.get("structured_report", {}) or {}
    doc_drift_by_key = state.get("doc_drift_by_key") or {}
    # structured_report expected format: items: [{event_id, role}] or sections[*].items[*]
    roles = {}
    for it in structured_report.get("items", []):
        if "event_id" in it:
            roles[it["event_id"]] = it.get("role")
    for section in structured_report.get("sections", []) or []:
        for it in section.get("items", []) or []:
            if "event_ids" in it:
                for eid in it.get("event_ids") or []:
                    roles[eid] = it.get("role")

    entries: List[Gate1Entry] = []
    key_claim_total = 0
    key_claim_locatable = 0
    locatable_total = 0
    locatable_ok = 0
    reason_counts: dict[str, int] = {}

    for item in facts.get("items", []):
        event_id = item.get("event_id", "")
        role = roles.get(event_id)
        doc_ref = (item.get("doc_ref") or {})
        doc_key = doc_ref.get("doc_key") or doc.get("doc_key")
        drift_status = doc_drift_by_key.get(doc_key) if doc_key else None
        quote = doc_ref.get("evidence_quote") or ""
        reason = doc_ref.get("unlocatable_reason")
        sentence_ids = doc_ref.get("sentence_ids") or []

        severity = None
        message = None

        locatable_total += 1
        if role == "key_claim":
            key_claim_total += 1

        if reason:
            severity = "SOFT" if role == "key_claim" else "WARN"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            message = f"Unlocatable evidence: {reason}"
        else:
            # verify quote can be reproduced from sentences
            ref_text = _find_sentence_text(doc.get("cleaned_text", ""), sentences, sentence_ids)
            if quote and ref_text and quote in ref_text:
                severity = "OK"
                message = "Locatable"
                locatable_ok += 1
                if role == "key_claim":
                    key_claim_locatable += 1
            else:
                severity = "SOFT" if role == "key_claim" else "WARN"
                message = "Quote not reproducible"
                if drift_status == "CHANGED_SINCE_LAST_SEEN":
                    message = "Quote not reproducible (possible doc drift)"

        entries.append(Gate1Entry(event_id=event_id, severity=severity, message=message, role=role))

    key_claim_locatable_rate = None
    if key_claim_total > 0:
        key_claim_locatable_rate = key_claim_locatable / key_claim_total
    locatable_rate_overall = None
    if locatable_total > 0:
        locatable_rate_overall = locatable_ok / locatable_total

    report = Gate1Report(entries=entries, key_claim_locatable_rate=key_claim_locatable_rate)
    return {
        "gate1_report": report.dict(),
        "metrics_summary": {
            "key_claim_locatable_rate": key_claim_locatable_rate,
            "locatable_rate_overall": locatable_rate_overall,
            "reason_counts": reason_counts,
        },
    }
