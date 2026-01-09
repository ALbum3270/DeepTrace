import pytest
from src.graph.nodes.build_document_snapshot import build_document_snapshot_node


@pytest.mark.asyncio
async def test_build_document_snapshot_basic():
    state = {
        "cleaned_text": "Hello World",
        "final_url": "https://example.com/article",
        "extractor_version": "trafilatura",
        "doc_quality_flags": [],
    }
    out = await build_document_snapshot_node(state, config={})
    snapshot = out["document_snapshot"]
    assert snapshot["doc_id"]
    assert snapshot["text_digest"]
    assert snapshot["normalization_version"]
    assert snapshot["doc_key_preview"]
    assert snapshot["doc_version_id_preview"]
