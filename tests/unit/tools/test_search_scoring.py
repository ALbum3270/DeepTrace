from src.core.tools.search import score_result


def test_score_result_prefers_recent_and_credible():
    recent = {
        "url": "https://openai.com/blog/gpt-5",
        "published_date": "2025-01-01",
    }
    old = {
        "url": "https://twitter.com/someuser/status/1",
        "published_date": "2020-01-01",
    }
    assert score_result(recent) > score_result(old)
