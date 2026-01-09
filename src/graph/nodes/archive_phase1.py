"""
Phase1 - ArchiveRunNode
Archives DocumentSnapshot, Indexes, facts_index_v2, gate1_report to files.
"""

import json
from pathlib import Path
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

def _write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def archive_phase1_node(state: Dict[str, Any], config: RunnableConfig):
    run_id = state.get("run_id", "run")
    base = Path("artifacts") / "phase1" / run_id

    artifacts = {
        "document_snapshot.json": state.get("document_snapshot"),
        "chunk_meta.json": state.get("chunk_meta"),
        "sentence_meta.json": state.get("sentence_meta"),
        "index_manifest.json": state.get("index_manifest"),
        "facts_index_v2.json": state.get("facts_index_v2"),
        "gate1_report.json": state.get("gate1_report"),
        "metrics_summary.json": state.get("metrics_summary"),
    }
    for name, data in artifacts.items():
        if data is not None:
            _write_json(base / name, data)

    return {"archive_path": str(base)}
