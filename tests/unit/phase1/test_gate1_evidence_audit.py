import pytest
from src.graph.nodes.gate1_evidence_audit import gate1_evidence_audit_node


@pytest.mark.asyncio
async def test_gate1_key_claim_locatable():
    state = {
        "facts_index_v2": {
            "items": [
                {
                    "event_id": "e1",
                    "doc_ref": {
                        "sentence_ids": ["s1"],
                        "evidence_quote": "Hello World",
                    },
                }
            ]
        },
        "document_snapshot": {"cleaned_text": "Hello World"},
        "sentence_meta": [{"sentence_id": "s1", "start": 0, "end": 11}],
        "structured_report": {"items": [{"event_id": "e1", "role": "key_claim"}]},
    }
    out = await gate1_evidence_audit_node(state, config={})
    report = out["gate1_report"]
    assert report["entries"][0]["severity"] == "OK"
    assert out["metrics_summary"]["key_claim_locatable_rate"] == 1.0


@pytest.mark.asyncio
async def test_gate1_missing_evidence_key_claim():
    state = {
        "facts_index_v2": {"items": [{"event_id": "e2", "doc_ref": {"unlocatable_reason": "NO_HINT_NO_REF"}}]},
        "document_snapshot": {"cleaned_text": ""},
        "sentence_meta": [],
        "structured_report": {"items": [{"event_id": "e2", "role": "key_claim"}]},
    }
    out = await gate1_evidence_audit_node(state, config={})
    report = out["gate1_report"]
    assert report["entries"][0]["severity"] == "SOFT"
