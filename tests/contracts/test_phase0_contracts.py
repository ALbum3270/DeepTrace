import json
import sys
import site
from pathlib import Path

import pytest

# Skip if core dependencies are missing (e.g., running outside Album env).
try:
    import langchain_core  # noqa: F401
except ImportError:  # pragma: no cover - env guard
    pytest.skip("langchain_core not installed; skip contract tests", allow_module_level=True)

# Ensure a working attr/attrs module for jsonschema in environments where a user-site attr.py shadows attrs.
try:
    user_site = site.getusersitepackages()
    if user_site in sys.path:
        sys.path.remove(user_site)
    import attr as _attr  # type: ignore
    import attrs as _attrs  # type: ignore
    sys.modules["attr"] = _attr
    sys.modules["attrs"] = _attrs
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jsonschema

from src.graph.nodes.finalizer import _gate2_audit, _must_be_key_claim
from src.config.settings import settings


ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "tests" / "fixtures" / "phase0"

# Use a test-local severity config so rule coverage is stable even if production config disables some rules.
settings.gate2_severity_config = str(FIXTURES / "gate2_severity_test.yaml")


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(schema_name: str, fixture_name: str):
    schema = _load_json(SCHEMAS / schema_name)
    payload = _load_json(FIXTURES / fixture_name)
    jsonschema.validate(instance=payload, schema=schema)


def test_facts_index_schema_valid():
    _validate("facts_index.schema.json", "facts_index_valid.json")


def test_structured_report_schema_valid():
    _validate("structured_report.schema.json", "structured_report_valid.json")


def test_report_citations_schema_valid():
    _validate("report_citations.schema.json", "report_citations_valid.json")


def test_gate_report_schema_valid():
    _validate("gate_report.schema.json", "gate_report_valid.json")


def test_run_record_schema_valid():
    _validate("run_record.schema.json", "run_record_valid.json")


def test_gate2_hard_event_id_not_in_facts_index():
    facts_index = _load_json(FIXTURES / "facts_index_valid.json")
    structured_report = _load_json(FIXTURES / "structured_report_valid.json")
    # Introduce an invalid event_id
    structured_report["sections"][0]["items"][0]["event_ids"] = ["ev-missing"]
    gate = _gate2_audit(structured_report, facts_index)
    hard_rules = {v["rule_id"] for v in gate["violations"] if v["severity"] == "HARD"}
    assert "event_id_not_in_facts_index" in hard_rules


def test_gate2_hard_disputed_requirements():
    facts_index = _load_json(FIXTURES / "facts_index_valid.json")
    structured_report = _load_json(FIXTURES / "structured_report_valid.json")
    structured_report["sections"][0]["items"][0].update(
        {
            "dispute_status": "disputed",
            "assertion_strength": "strong",
            "event_ids": ["ev-001"],
            "conflict_group_id": None,
            "item_text": "officially confirmed release date",
        }
    )
    gate = _gate2_audit(structured_report, facts_index)
    hard_rules = {v["rule_id"] for v in gate["violations"] if v["severity"] == "HARD"}
    assert "disputed_must_be_hedged" in hard_rules
    assert "disputed_needs_multiple_events" in hard_rules
    assert "strong_word_in_disputed" in hard_rules


def test_gate2_warn_must_be_key_claim():
    facts_index = _load_json(FIXTURES / "facts_index_valid.json")
    structured_report = _load_json(FIXTURES / "structured_report_valid.json")
    structured_report["sections"][0]["items"][0].update(
        {
            "item_text": "2025-05-01 release announced",
            "role": "analysis",  # not key_claim
            "event_ids": ["ev-001"],
            "assertion_strength": "neutral",
            "dispute_status": "none",
        }
    )
    assert _must_be_key_claim(structured_report["sections"][0]["items"][0]["item_text"])
    gate = _gate2_audit(structured_report, facts_index)
    warn_rules = {v["rule_id"] for v in gate["violations"] if v["severity"] == "WARN"}
    assert "must_be_key_claim" in warn_rules


def test_gate2_hard_key_claim_missing_event_ids():
    facts_index = _load_json(FIXTURES / "facts_index_valid.json")
    structured_report = _load_json(FIXTURES / "structured_report_valid.json")
    structured_report["sections"][0]["items"][0].update(
        {
            "role": "key_claim",
            "event_ids": [],
            "assertion_strength": "neutral",
            "dispute_status": "none",
        }
    )
    gate = _gate2_audit(structured_report, facts_index)
    hard_rules = {v["rule_id"] for v in gate["violations"] if v["severity"] == "HARD"}
    assert "key_claim_missing_event_ids" in hard_rules
