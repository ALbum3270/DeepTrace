"""
Offline verifier for Phase1 Gate1 locatability.
Loads facts_index_v2, document_snapshot, sentence_meta and reports failures.
"""

import json
import sys
from pathlib import Path

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def find_sentence_text(doc, sentences, sentence_ids):
    spans = []
    for sid in sentence_ids or []:
        for s in sentences:
            if s.get("sentence_id") == sid:
                spans.append((s.get("start"), s.get("end")))
    if not spans:
        return ""
    start = min(s for s,_ in spans)
    end = max(e for _,e in spans)
    return doc[start:end]

def main(facts_path, doc_path, sentences_path):
    facts = load_json(facts_path)
    doc = load_json(doc_path)
    sentences = load_json(sentences_path)
    failures = []
    for item in facts.get("items", []):
        event_id = item.get("event_id")
        ref = item.get("doc_ref") or {}
        quote = ref.get("evidence_quote") or ""
        reason = ref.get("unlocatable_reason")
        if reason:
            failures.append((event_id, reason))
            continue
        ref_text = find_sentence_text(doc.get("cleaned_text",""), sentences, ref.get("sentence_ids"))
        if not quote or not ref_text or quote not in ref_text:
            failures.append((event_id, "quote_not_reproducible"))
    if failures:
        print("FAILURES:")
        for ev, msg in failures:
            print(f"- {ev}: {msg}")
        sys.exit(1)
    else:
        print("All evidence locatable.")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python scripts/verify_locatability.py facts_index_v2.json document_snapshot.json sentence_meta.json")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
