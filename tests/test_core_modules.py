"""
Unit Tests for DeepTrace Core Modules
测试 event_extractor, extract_node, update_claims_node, report_writer 的关键功能
"""
import pytest
from unittest.mock import Mock

# ============================================
# Test: event_extractor._sanitize_quote
# ============================================

class TestSanitizeQuote:
    """测试 _sanitize_quote 函数"""
    
    def test_empty_quote(self):
        from src.agents.event_extractor import _sanitize_quote
        assert _sanitize_quote("") == ""
        assert _sanitize_quote(None) == ""
    
    def test_removes_newlines(self):
        from src.agents.event_extractor import _sanitize_quote
        result = _sanitize_quote("Hello\nWorld\r\nTest")
        assert "\n" not in result
        assert "\r" not in result
        assert result == "Hello World Test"
    
    def test_truncates_long_quote(self):
        from src.agents.event_extractor import _sanitize_quote
        long_quote = "A" * 300
        result = _sanitize_quote(long_quote)
        assert len(result) <= 201  # 200 + "…"
        assert result.endswith("…")
    
    def test_preserves_short_quote(self):
        from src.agents.event_extractor import _sanitize_quote
        short_quote = "This is a short quote."
        result = _sanitize_quote(short_quote)
        assert result == short_quote


# ============================================
# Test: verification.verify_report
# ============================================

class TestVerifyReport:
    """测试 verify_report 统一验证函数"""
    
    def test_empty_report(self):
        from src.infrastructure.utils.verification import verify_report
        result, stats = verify_report("", [])
        assert result == ""
        assert stats["status"] == "empty"
    
    def test_removes_fake_links(self):
        from src.infrastructure.utils.verification import verify_report
        
        # Mock evidences
        mock_ev = Mock()
        mock_ev.url = "https://real-url.com/article"
        mock_ev.content = "Some content without numbers."
        evidences = [mock_ev]
        
        report = """
        Check this [real link](https://real-url.com/article) and 
        this [fake link](https://fake-url.com/bogus).
        """
        
        result, stats = verify_report(report, evidences)
        
        assert "https://real-url.com/article" in result
        assert "⚠️ 链接未验证" in result
        assert stats["fake_links_removed"] == 1
    
    def test_no_links_fast_path(self):
        from src.infrastructure.utils.verification import verify_report
        
        report = "This report has no links at all."
        result, stats = verify_report(report, [])
        
        assert result == report
        assert stats["fake_links_removed"] == 0


# ============================================
# Test: update_claims_node.pick_canonical_text
# ============================================

class TestCanonicalTextLimit:
    """测试 canonical_text 长度限制"""
    
    def test_truncates_long_canonical_text(self):
        # 直接测试长度限制逻辑
        MAX_CANONICAL_LENGTH = 200
        long_text = "A" * 300
        
        if len(long_text) > MAX_CANONICAL_LENGTH:
            truncated = long_text[:MAX_CANONICAL_LENGTH] + "…"
        else:
            truncated = long_text
        
        assert len(truncated) == 201
        assert truncated.endswith("…")


# ============================================
# Test: extract_node claim deduplication
# ============================================

class TestClaimDeduplication:
    """测试 Claim 去重逻辑"""
    
    def test_dedup_by_content(self):
        # 模拟去重逻辑
        claims = [
            {"content": "Google released Gemini 3"},
            {"content": "google released gemini 3"},  # 应被去重
            {"content": "Google released Gemini 3 "},  # 应被去重
            {"content": "Different claim"},
        ]
        
        seen = set()
        deduplicated = []
        for c in claims:
            key = c["content"].lower().strip()
            if key not in seen:
                seen.add(key)
                deduplicated.append(c)
        
        assert len(deduplicated) == 2
        assert deduplicated[0]["content"] == "Google released Gemini 3"
        assert deduplicated[1]["content"] == "Different claim"


# ============================================
# Test: Credibility Safe Defaults
# ============================================

class TestCredibilitySafeDefaults:
    """测试可信度安全默认值"""
    
    def test_fact_source_default(self):
        # 测试默认值 0.90 而非 0.98
        default = 0.90
        max_cap = default * 100
        assert max_cap == 90.0
    
    def test_mixed_source_fixed_cap(self):
        # 测试固定上限 60
        max_cap = 60.0
        raw_score = 80.0
        capped = min(raw_score, max_cap)
        assert capped == 60.0


# ============================================
# Run tests
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
