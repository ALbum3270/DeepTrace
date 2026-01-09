import pytest
from src.graph.nodes.build_facts_index_v2 import build_facts_index_v2_node


@pytest.mark.asyncio
async def test_build_facts_index_with_hint():
    cleaned = "Hello world. This is a GPT-5 release article with sufficient detail for quoting."
    sentences = [
        {"sentence_id": "s1", "start": 0, "end": 12},
        {"sentence_id": "s2", "start": 13, "end": len(cleaned)},
    ]
    events = [
        {
            "event_id": "e1",
            "url": "https://example.com",
            "evidence_hint": "GPT-5 release",
        }
    ]
    out = await build_facts_index_v2_node(
        {"cleaned_text": cleaned, "sentence_meta": sentences, "events": events, "doc_id": "doc1"},
        config={},
    )
    facts = out["facts_index_v2"]["items"]
    assert facts[0]["doc_ref"]["evidence_quote"]
    assert facts[0]["doc_ref"]["unlocatable_reason"] is None


@pytest.mark.asyncio
async def test_build_facts_index_no_hint():
    out = await build_facts_index_v2_node(
        {"cleaned_text": "text", "sentence_meta": [], "events": [{"event_id": "e2"}], "doc_id": "doc1"},
        config={},
    )
    facts = out["facts_index_v2"]["items"]
    assert facts[0]["doc_ref"]["unlocatable_reason"] == "NO_HINT_NO_REF"
