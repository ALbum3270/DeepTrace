from src.graph.nodes.worker_nodes import _normalize_date_string


def test_normalize_date_string():
    assert _normalize_date_string("2025-08-07T12:00:00Z") == "2025-08-07"
    assert _normalize_date_string("2025-08") == "2025-08"
    assert _normalize_date_string("2025") == "2025"
    assert _normalize_date_string("") == "Unknown"
    assert _normalize_date_string("unknown format") == "Unknown"
