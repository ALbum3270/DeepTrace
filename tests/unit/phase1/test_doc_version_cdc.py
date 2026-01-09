import json
from pathlib import Path

from src.graph.nodes.doc_version_cdc import doc_version_cdc_node


def test_doc_version_cdc_writes_and_appends(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    snap = {
        "doc_id": "doc1",
        "final_url": "https://example.com/a?x=1",
        "doc_key": "https://example.com/a",
        "doc_version_id": "v1",
        "text_digest": "d1",
    }
    out1 = doc_version_cdc_node({"document_snapshot": snap, "run_id": "run1"})
    p = Path(out1["doc_version_cdc_path"])
    assert p.exists()
    assert out1["drift_status"] == "FIRST_SEEN"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["doc_key"] == "https://example.com/a"
    assert data["latest_doc_version_id"] == "v1"
    assert len(data["versions"]) == 1
    assert data["versions"][0]["seen_runs"] == ["run1"]

    out2 = doc_version_cdc_node({"document_snapshot": snap, "run_id": "run2"})
    assert out2["drift_status"] == "UNCHANGED"
    data2 = json.loads(Path(out2["doc_version_cdc_path"]).read_text(encoding="utf-8"))
    assert len(data2["versions"]) == 1
    assert sorted(data2["versions"][0]["seen_runs"]) == ["run1", "run2"]


def test_doc_version_cdc_detects_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    snap1 = {"doc_id": "d1", "doc_key": "https://example.com/a", "doc_version_id": "v1"}
    snap2 = {"doc_id": "d2", "doc_key": "https://example.com/a", "doc_version_id": "v2"}
    out1 = doc_version_cdc_node({"document_snapshot": snap1, "run_id": "r1"})
    assert out1["drift_status"] == "FIRST_SEEN"
    out2 = doc_version_cdc_node({"document_snapshot": snap2, "run_id": "r2"})
    assert out2["drift_status"] == "CHANGED_SINCE_LAST_SEEN"
