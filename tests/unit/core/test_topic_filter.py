from src.core.utils.topic_filter import extract_tokens, matches_tokens
from src.config.topic_settings import topic_settings


def test_extract_tokens_regex_and_explicit():
    topic_settings.ALLOW_FALLBACK_TOKENS = False
    text = "Research on GPT5 and GPT-4.1 roadmap"
    tokens = extract_tokens(text)
    normalized = [t.replace(" ", "") for t in tokens]
    assert "gpt5" in normalized
    assert any("gpt-4.1" in t or "gpt4.1" in t for t in normalized)


def test_matches_tokens_false_when_empty():
    assert matches_tokens("anything", set()) is False
