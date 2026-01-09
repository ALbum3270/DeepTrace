"""
Phase1 - BuildFactsIndexNode v2
Creates facts_index_v2 entries with doc_ref, evidence_hint (optional), and programmatically extracted evidence_quote.
Implements locator priority:
  1) use provided sentence_ids/offsets -> extract quote
  2) else use evidence_hint to find substring/approx match -> map to sentence_ids -> extract quote
  3) else mark unlocatable_reason=NO_HINT_NO_REF
"""

from typing import Dict, Any, List
import difflib
from src.core.models.phase1 import EvidenceItem, EvidenceRef, FactsIndexV2

MIN_QUOTE_CHARS = 40

def _extract_substring(text: str, start: int, end: int) -> str:
    if start < 0 or end > len(text) or start >= end:
        return ""
    return text[start:end]


def _find_with_hint(text: str, hint: str):
    """
    Find hint in text; return start,end; allow approximate match via difflib if exact not found.
    """
    if not hint:
        return None
    idx = text.find(hint)
    if idx != -1:
        return idx, idx + len(hint)
    # approximate: take best close match window
    matcher = difflib.SequenceMatcher(None, text, hint)
    match = matcher.find_longest_match(0, len(text), 0, len(hint))
    if match.size > 0:
        start = match.a
        end = start + match.size
        return start, end
    return None


def _map_to_sentences(start: int, end: int, sentences: List[dict]) -> List[str]:
    ids = []
    for sent in sentences:
        s, e = sent["start"], sent["end"]
        if (start >= s and start < e) or (end > s and end <= e) or (start <= s and end >= e):
            ids.append(sent["sentence_id"])
    return ids


async def build_facts_index_v2_node(state: Dict[str, Any], config) -> Dict[str, Any]:
    cleaned_text = state.get("cleaned_text", "")
    sentences = state.get("sentence_meta", [])
    events = state.get("events", [])  # expected list of dicts with event_id/url/credibility_tier/evidence_hint?/sentence_ids?
    normalization_version = state.get("normalization_version", "unknown")
    doc_id = state.get("doc_id", "unknown")

    evidence_items = []
    for ev in events:
        event_id = ev.get("event_id", "")
        url = ev.get("url", "")
        tier = ev.get("credibility_tier", None)
        ref = ev.get("doc_ref", {}) or {}
        sentence_ids = ref.get("sentence_ids") or ev.get("sentence_ids") or []
        offsets = ref.get("offsets")
        hint = ev.get("evidence_hint") or ref.get("evidence_hint")
        quote = None
        unloc_reason = None

        if sentence_ids:
            # use provided sentence_ids to extract quote
            spans = []
            for sid in sentence_ids:
                for s in sentences:
                    if s["sentence_id"] == sid:
                        spans.append((s["start"], s["end"]))
            if spans:
                start = min(s for s, _ in spans)
                end = max(e for _, e in spans)
                quote = _extract_substring(cleaned_text, start, end)
        elif hint:
            span = _find_with_hint(cleaned_text, hint)
            if span:
                start, end = span
                # map to sentences
                sentence_ids = _map_to_sentences(start, end, sentences)
                if sentence_ids:
                    # widen quote to full covered sentences for better context
                    spans = []
                    for sid in sentence_ids:
                        for s in sentences:
                            if s["sentence_id"] == sid:
                                spans.append((s["start"], s["end"]))
                    if spans:
                        start = min(s for s, _ in spans)
                        end = max(e for _, e in spans)
                quote = _extract_substring(cleaned_text, start, end)
        else:
            unloc_reason = "NO_HINT_NO_REF"

        if quote and len(quote.strip()) < MIN_QUOTE_CHARS:
            unloc_reason = "QUOTE_TOO_SHORT"
            quote = ""

        if not quote and not unloc_reason:
            unloc_reason = "LOCATE_FAILED"

        doc_ref = EvidenceRef(
            doc_id=doc_id,
            chunk_id=ref.get("chunk_id"),
            sentence_ids=sentence_ids,
            offsets=offsets,
            evidence_hint=hint,
            evidence_quote=quote,
            quote_hash=None,  # compute later if needed
            unlocatable_reason=unloc_reason,
        )
        evidence_items.append(
            EvidenceItem(
                event_id=event_id,
                url=url,
                credibility_tier=tier,
                doc_ref=doc_ref,
            )
        )

    facts = FactsIndexV2(items=evidence_items, normalization_version=normalization_version)
    return {"facts_index_v2": facts.dict()}
