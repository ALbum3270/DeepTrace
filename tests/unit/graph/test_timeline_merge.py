from src.graph.nodes.timeline_merge import merge_timeline_entries


def test_merge_multi_version_entries():
    timeline = [
        {
            "date": "2024-01-01",
            "title": "Product Alpha v1 released",
            "description": "Initial rollout",
            "source": "https://example.com/a",
        },
        {
            "date": "2024-01-01",
            "title": "Product Alpha v2 released",
            "description": "Second rollout",
            "source": "https://example.com/b",
        },
    ]

    merged = merge_timeline_entries(timeline)
    assert len(merged) == 1
    assert merged[0].get("merge_type") == "multi_version"
    assert "v1" in merged[0].get("description", "")
    assert "v2" in merged[0].get("description", "")


def test_no_merge_without_versions():
    timeline = [
        {
            "date": "2024-01-01",
            "title": "Product Alpha released",
            "description": "Initial rollout",
            "source": "https://example.com/a",
        },
        {
            "date": "2024-01-01",
            "title": "Product Alpha announced",
            "description": "Second article",
            "source": "https://example.com/b",
        },
    ]

    merged = merge_timeline_entries(timeline)
    assert len(merged) == 2
