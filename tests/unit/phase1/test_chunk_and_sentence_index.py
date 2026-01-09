import pytest
from src.graph.nodes.chunk_and_sentence_index import chunk_and_sentence_index_node, DEFAULT_CHUNK_PARAMS


@pytest.mark.asyncio
async def test_chunk_and_sentence_index_basic():
    text = "Hello world. This is a test. 你好，世界。再见。"
    out = await chunk_and_sentence_index_node(
        {"cleaned_text": text, "doc_id": "doc1", "normalization_version": "v1", "run_id": "run1"},
        config={},
    )
    assert out["chunk_meta"]
    assert out["sentence_meta"]
    manifest = out["index_manifest"]
    assert manifest["chunk_splitter"]["params"]["chunk_size"] == DEFAULT_CHUNK_PARAMS["chunk_size"]
    assert manifest["sentence_splitter"]["backend"] == "rule_based"
