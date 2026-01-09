"""
Phase2 - Doc Version CDC (Change Data Capture)

Maintain a persistent version history per normalized document key (URL).
This is deterministic (no LLM) and enables later audits like:
- "same URL changed content between runs"
- "quote became unreproducible due to doc drift"

Storage:
  data/doc_versions/<doc_key_hash>.json
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.utcnow().isoformat()

def _load_record(path: Path, doc_key: str) -> dict:
    record = {
        "doc_key": doc_key,
        "latest_doc_version_id": None,
        "updated_at": None,
        "versions": [],
    }
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                record.update(loaded)
        except Exception:
            pass
    return record


def _trim_versions(record: dict, *, max_versions: int) -> dict:
    versions = record.get("versions") or []
    if max_versions <= 0 or len(versions) <= max_versions:
        return record
    # keep most recently seen versions (by last_seen)
    def _key(v: dict) -> str:
        return v.get("last_seen") or v.get("first_seen") or ""
    versions_sorted = sorted(versions, key=_key, reverse=True)[:max_versions]
    record["versions"] = versions_sorted
    return record


def peek_doc_version(doc_key: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (cdc_path, latest_doc_version_id) if record exists.
    """
    base_dir = Path("data") / "doc_versions"
    key_hash = _sha256(doc_key)[:16]
    path = base_dir / f"{key_hash}.json"
    if not path.exists():
        return None, None
    record = _load_record(path, doc_key)
    return str(path), record.get("latest_doc_version_id")


def doc_version_cdc_node(state: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = state.get("document_snapshot") or {}
    doc_key = snapshot.get("doc_key") or snapshot.get("final_url") or snapshot.get("doc_id") or "unknown"
    doc_version_id = snapshot.get("doc_version_id") or snapshot.get("doc_version_id_preview") or snapshot.get("text_digest")
    run_id = state.get("run_id") or snapshot.get("run_id")
    doc_id = snapshot.get("doc_id")

    base_dir = Path("data") / "doc_versions"
    base_dir.mkdir(parents=True, exist_ok=True)
    key_hash = _sha256(doc_key)[:16]
    path = base_dir / f"{key_hash}.json"

    record = _load_record(path, doc_key)
    previous_latest = record.get("latest_doc_version_id")
    if previous_latest is None:
        drift_status = "FIRST_SEEN"
    elif previous_latest == doc_version_id:
        drift_status = "UNCHANGED"
    else:
        drift_status = "CHANGED_SINCE_LAST_SEEN"

    versions = record.get("versions") or []
    found = None
    for v in versions:
        if v.get("doc_version_id") == doc_version_id:
            found = v
            break
    if found is None:
        found = {
            "doc_version_id": doc_version_id,
            "first_seen": _now_iso(),
            "last_seen": _now_iso(),
            "seen_runs": [],
            "doc_ids": [],
        }
        versions.append(found)
    else:
        found["last_seen"] = _now_iso()

    if run_id and run_id not in found["seen_runs"]:
        found["seen_runs"].append(run_id)
    if doc_id and doc_id not in found["doc_ids"]:
        found["doc_ids"].append(doc_id)

    record["doc_key"] = doc_key
    record["latest_doc_version_id"] = doc_version_id
    record["updated_at"] = _now_iso()
    record["versions"] = versions

    try:
        max_versions = int(os.getenv("DEEPTRACE_DOC_VERSION_MAX_VERSIONS", "50"))
    except Exception:
        max_versions = 50
    record = _trim_versions(record, max_versions=max_versions)

    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "doc_version_cdc_path": str(path),
        "doc_key": doc_key,
        "doc_version_id": doc_version_id,
        "doc_versions_count": len(versions),
        "previous_latest_doc_version_id": previous_latest,
        "drift_status": drift_status,
    }
