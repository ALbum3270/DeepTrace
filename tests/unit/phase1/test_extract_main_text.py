import pytest
from src.graph.nodes.extract_main_text import extract_main_text_node


@pytest.mark.asyncio
async def test_extract_main_text_node_no_html():
    out = await extract_main_text_node({"raw_html": ""}, config={})
    assert out["extractor_version"] == "none"
    assert "no_input_html" in out["doc_quality_flags"]


@pytest.mark.asyncio
async def test_extract_main_text_node_basic():
    html = "<html><body><p>Hello</p><p>World</p></body></html>"
    out = await extract_main_text_node({"raw_html": html}, config={})
    assert out["cleaned_text"]
    assert out["extractor_version"] in {"trafilatura", "jusText", "readability", "naive"}
