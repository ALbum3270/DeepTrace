import json
import os
from datetime import datetime
from typing import Dict, Any

from src.graph.state_v2 import GlobalState


def archive_run_node(state: GlobalState) -> Dict[str, Any]:
    """
    Archive artifacts from the run into data/runs/{run_id}/ and emit run_record_path.
    This is deterministic and does not call any LLM.
    """
    run_id = state.get("run_id") or "run"
    base_dir = os.path.join("data", "runs", run_id)
    os.makedirs(base_dir, exist_ok=True)

    artifacts = {}

    def _dump_json(name: str, payload: Any):
        if payload is None:
            return None
        path = os.path.join(base_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        artifacts[f"{name}_path"] = path
        return path

    _dump_json("facts_index", state.get("facts_index"))
    _dump_json("structured_report", state.get("structured_report"))
    _dump_json("report_citations", state.get("report_citations"))
    _dump_json("gate_report", state.get("gate_report"))

    # final_report markdown
    final_report_path = None
    if state.get("final_report"):
        final_report_path = os.path.join(base_dir, "final_report.md")
        with open(final_report_path, "w", encoding="utf-8") as f:
            f.write(state["final_report"])
        artifacts["final_report_path"] = final_report_path

    run_record = {
        "run_id": run_id,
        "archived_at": datetime.utcnow().isoformat(),
        "objective": state.get("objective"),
        "original_query": state.get("original_query"),
        "artifacts": artifacts,
        "enabled_policies_snapshot": state.get("enabled_policies_snapshot") or {},
    }
    renderer_version = (run_record["enabled_policies_snapshot"] or {}).get("renderer_version")
    if renderer_version:
        run_record["renderer_version"] = renderer_version
    run_record_path = os.path.join(base_dir, "run_record.json")
    with open(run_record_path, "w", encoding="utf-8") as f:
        json.dump(run_record, f, ensure_ascii=False, indent=2)

    return {"run_record_path": run_record_path}
