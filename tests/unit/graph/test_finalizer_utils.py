import pytest

from src.graph.nodes import finalizer


def test_filter_official_buckets_requires_announcement():
    buckets = {
        "official": [
            "https://openai.com",
            "https://openai.com/blog/gpt-5-update-2025-08-07",
        ],
        "reputable": [],
        "low": [],
    }
    filtered = finalizer._filter_official_buckets(buckets)
    assert "https://openai.com/blog/gpt-5-update-2025-08-07" in filtered["official"]
    # Homepage without announcement markers should be downgraded
    assert "https://openai.com" not in filtered["official"]
    assert "https://openai.com" in filtered["reputable"]


def test_clean_timeline_entries_filters_low_and_marks_disputed():
    raw = [
        {
            "date": "2024-10-01",
            "title": "Tech outlet reports GPT-5 rumor",
            "source": "https://theverge.com/tech/gpt5-rumor",
        },
        {
            "date": "2024-10-01",
            "title": "Duplicate rumor",
            "source": "https://theverge.com/tech/gpt5-rumor",
        },
        {
            "date": "2024-11-01",
            "title": "Unverified social post",
            "source": "https://twitter.com/someuser/status/1",
        },
        {
            "title": "No source provided",
            "date": None,
        },
    ]

    cleaned = finalizer._clean_timeline_entries(raw)
    # Keeps reputable source, drops duplicate/low-cred
    assert any("Tech outlet reports" in item["title"] for item in cleaned)
    assert not any("twitter.com" in (item.get("source") or "") for item in cleaned)
    # No-source entry is kept but marked disputed
    assert any(item["title"].startswith("[Disputed]") for item in cleaned)
