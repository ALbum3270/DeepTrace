
from src.core.models.evidence import Evidence
from src.core.verification.span_extractor import SpanExtractor

def test_span_extraction_logic():
    """测试 Span Extractor 的分块与 Hash ID 生成"""
    
    # Setup Evidence
    content = "This is sentence one. This is sentence two! And three? \n   Sentence four."
    evidence = Evidence(content=content, id="ev123")
    
    extractor = SpanExtractor()
    spans = extractor.extract_spans(evidence)
    
    # Assertions
    # Should split into 4 spans
    assert len(spans) == 4
    
    # Check Span 0
    s0 = spans[0]
    assert s0.evidence_id == "ev123"
    assert s0.chunk_index == 0
    assert s0.content == "This is sentence one."
    # ID Format: [Ev123#c0@<hash>]
    assert s0.citation_id.startswith("[Evev123#c0@")
    assert s0.citation_id.endswith("]")
    
    # Check Span 1
    s1 = spans[1]
    assert s1.chunk_index == 1
    assert s1.content == "This is sentence two!"
    
    # Check Determinism
    # Same content should give same hash
    text_s1 = "This is sentence two!"
    # Re-extract just to verify hash
    spans_again = extractor.extract_spans(Evidence(content=text_s1, id="temp"))
    assert spans_again[0].content_hash == s1.content_hash

def test_short_noise_filter():
    """测试过滤短噪音"""
    content = "Ok. Hi. This is real content."
    evidence = Evidence(content=content)
    spans = SpanExtractor().extract_spans(evidence)
    
    # "Ok." (3 chars) "Hi." (3 chars) "This..." (>5 chars)
    # The logic says len < 5 -> skip.
    # So only "This is real content." should remain.
    
    assert len(spans) == 1
    assert spans[0].content == "This is real content."
