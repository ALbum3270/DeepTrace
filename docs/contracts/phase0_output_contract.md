# Phase 0 Output Contract (Structured → Render → Gate2)

## Artifacts
- `facts_index.json` — produced before finalizer; lists allowed `event_id` with at least one evidence.
- `structured_report.json` — LLM-structured sections/items; `event_ids` must be subset of `facts_index`.
- `report_citations.json` — deterministic transform from `structured_report`.
- `gate_report.json` — deterministic audit (WARN/SOFT/HARD) over structured + facts_index.
- `report.md` — deterministic render from structured + gate.

## Schemas
- See `schemas/*.schema.json` for machine-readable contracts.
- Key invariants (Phase 0):
  - No LLM-invented `event_id`; `event_ids` ⊆ `facts_index.facts[].event_id`.
  - When `dispute_status != none`: `assertion_strength = hedged` and (`event_ids` ≥ 2 or `conflict_group_id` present).
  - Strong-confirmation words are forbidden when disputed (HARD).
  - `must_be_key_claim` heuristic emits WARN when role ≠ `key_claim`.

## Recovery / Degradation
- Finalizer retries JSON parsing; on repeated failure, emits minimal schema-valid `structured_report` with `generation_errors` and records HARD violations in `gate_report`.
- Markdown render never calls the LLM; it is a deterministic template over `structured_report` + `gate_report`.

## Node Responsibilities (current implementation)
- `finalizer_node`:
  - Builds `facts_index` from timeline (deterministic).
  - Calls LLM once (with retries) for `structured_report`.
  - Exports `report_citations`, runs `gate_report`, renders `report.md`.
  - Returns all artifacts into graph state for downstream persistence.

## Severity (Phase 0)
- HARD: `event_id` not in facts_index; disputed not hedged; disputed without multi-source/`conflict_group_id`; disputed with strong-confirmation wording.
- WARN: `must_be_key_claim` heuristic but role ≠ `key_claim`.
- SOFT: reserved (currently unused in Phase 0).
