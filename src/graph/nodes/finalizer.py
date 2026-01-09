"""
Final report generator for DeepTrace V2.
"""

import re
import uuid
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import os

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
try:
    from langchain.chat_models import init_chat_model  # type: ignore
except ImportError:
    from langchain_openai import ChatOpenAI  # type: ignore
    def init_chat_model(model: str, temperature=0, model_provider=None, **kwargs):
        return ChatOpenAI(
            model=model,
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_base_url,
            temperature=temperature,
        )

from src.config.settings import settings
from src.core.utils.llm_safety import safe_ainvoke
from src.graph.state_v2 import GlobalState
from src.core.models.credibility import evaluate_credibility
from src.core.utils.topic_filter import matches_tokens, extract_tokens

import json
import yaml

RENDERER_VERSION = "phase0_markdown_renderer_v1"

def _extract_urls(notes: List[str]) -> List[str]:
    urls = []
    seen = set()
    # Allow typical URL characters; escape hyphen to avoid unintended ranges
    pattern = re.compile(r"https?://[\w\-._~:/?#\[\]@!$&'()*+,;=%]+", re.IGNORECASE)
    for note in notes:
        for url in pattern.findall(note or ""):
            normalized = url.rstrip(")].,>\"' ")
            if normalized and normalized not in seen:
                seen.add(normalized)
                urls.append(normalized)
    return urls


def _topic_tokens(text: str) -> set:
    return set(extract_tokens(text))


def _get_final_answer_draft(messages: List[Any]) -> str:
    for msg in reversed(messages):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("name") == "FinalAnswer":
                    return tc.get("args", {}).get("content", "")
    return ""


def _summarize_sources(urls: List[str]) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
    """
    Compute credibility buckets and counts using evaluate_credibility.
    Official bucket is strict (URL pattern and later LLM verification).
    """
    buckets = {"official": [], "reputable": [], "low": []}
    for url in urls:
        cred = evaluate_credibility(url)
        # Only mark as official candidates if domain is official AND path looks like announcement
        if cred.source_type == "official" and _has_date_or_announcement(url):
            buckets["official"].append(url)  # will be re-verified by LLM
        elif cred.score >= 70:
            buckets["reputable"].append(url)
        else:
            buckets["low"].append(url)
    stats = {
        "total": len(urls),
        "verified": len(buckets["official"]),
        "reputable": len(buckets["reputable"]),
        "rumor": len(buckets["low"]),
    }
    return buckets, stats


def _has_date_or_announcement(url: str) -> bool:
    """
    Heuristic: accept an 'official' URL only if it looks like a dated/announcement page.
    Prevents generic homepages from being treated as verified announcements.
    """
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path = (parsed.path or "").lower()
        if re.search(r"20\\d{2}", path):
            return True
        keywords = ["press", "release", "announce", "announcement", "blog", "news", "updates"]
        return any(k in path for k in keywords)
    except Exception:
        return False


def _filter_official_buckets(buckets: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Keep only official URLs that look like announcements; downgrade the rest to 'reputable'.
    """
    official_raw = list(buckets.get("official", []))
    official_kept = []
    downgraded = []
    for url in official_raw:
        if _has_date_or_announcement(url):
            official_kept.append(url)
        else:
            downgraded.append(url)
    buckets["official"] = official_kept
    if downgraded:
        buckets.setdefault("reputable", []).extend(downgraded)
    return buckets


def _build_snippet_map(urls: List[str], notes: List[str]) -> dict:
    """
    Map URL -> small snippet of note text containing it (for LLM verification).
    """
    snippets = {}
    for url in urls:
        for n in notes:
            if url in n:
                idx = n.find(url)
                start = max(0, idx - 200)
                end = min(len(n), idx + 200)
                snippets[url] = n[start:end]
                break
    return snippets


async def _llm_verify_official(url: str, topic: str, snippet: str, model_name: str):
    """
    Use LLM to verify if a source is an official announcement and whether it is confirmed vs speculative.
    Returns structured dict; on error, returns all False/Unknown.
    """
    system = "You are a strictly skeptical fact-checker. Output JSON only."
    user = f"""
Analyze if the source is an OFFICIAL SOURCE VERIFICATION for: "{topic}".

Source URL: {url}
Snippet:
{snippet[:800]}

Criteria:
- Domain ownership: official company domain (e.g., company's main site), but exclude community/help/forum unless explicitly announcing the target topic.
- Voice: written by company/staff, not community users/support forum.
- Content: direct confirmation or verification about THIS topic. Exclude unrelated product updates.

Return JSON ONLY:
{{
  "is_official_domain": true/false,
  "is_company_voice": true/false,
  "is_on_topic": true/false,
  "classification": "Official Source" | "Official Forum/Help" | "News Media" | "Rumor" | "Off-topic",
  "event_status": "Past/Confirmed" | "Future/Speculation" | "Unknown",
  "reasoning": "short explanation"
}}
"""
    llm = init_chat_model(model=model_name, temperature=0)
    try:
        resp = await safe_ainvoke(llm, [SystemMessage(content=system), HumanMessage(content=user)], model_name=model_name)
        data = json.loads(resp.content)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _render_ascii_timeline(timeline: List[Any]) -> str:
    """
    Render a simple ASCII timeline from timeline entries.
    Supports entries as dicts with 'title' and optional 'time'/'date'.
    """
    if not timeline:
        return "No timeline available."

    def parse_date(entry):
        for key in ["date", "time", "timestamp"]:
            if isinstance(entry, dict) and entry.get(key):
                return str(entry.get(key))[:10]
        return None

    lines = []
    for item in timeline:
        title = item.get("title") if isinstance(item, dict) else str(item)
        date = parse_date(item) or "Unknown"
        lines.append((date, title))

    # Sort by date string lexicographically; Unknown at end
    sorted_lines = sorted(lines, key=lambda x: ("9999-99-99" if x[0] == "Unknown" else x[0], x[1]))
    rendered = []
    for date, title in sorted_lines:
        rendered.append(f"|--{date}-- {title}")
    return "\n".join(rendered)


def _parse_date_candidate(date_str: str):
    if not date_str:
        return None
    ds = str(date_str).strip()
    if len(ds) >= 10 and ds[4] == "-" and ds[7] == "-":
        ds = ds[:10]
        fmt = "%Y-%m-%d"
        try:
            return datetime.strptime(ds, fmt).date()
        except ValueError:
            return None
    if len(ds) >= 7 and ds[4] == "-":
        ds = ds[:7]
        fmt = "%Y-%m"
        try:
            return datetime.strptime(ds, fmt).date()
        except ValueError:
            return None
    if len(ds) >= 4 and ds[:4].isdigit():
        ds = ds[:4]
        fmt = "%Y"
        try:
            return datetime.strptime(ds, fmt).date()
        except ValueError:
            return None
    return None


def _latest_timeline_date(timeline: List[Any]):
    latest = None
    for item in timeline or []:
        if not isinstance(item, dict):
            continue
        for key in ["date", "time", "timestamp"]:
            dt = _parse_date_candidate(item.get(key))
            if dt:
                if not latest or dt > latest:
                    latest = dt
                break
    return latest


def _clean_timeline_entries(raw: List[Any]) -> List[dict]:
    """
    Deduplicate and filter timeline entries.
    - Preserve credibility notes without forcing [Disputed] prefixes.
    - Deduplicate by (date, normalized title); merge descriptions when conflicts arise.
    """
    def _normalize_title(raw_title: str) -> str:
        normalized = re.sub(r"\s+", " ", raw_title.lower()).strip()
        normalized = re.sub(r"[^a-z0-9\s]+", "", normalized)
        return normalized

    from typing import Optional

    def _append_conflict_note(desc: str, source_a: Optional[str], source_b: Optional[str]) -> str:
        sources = [s for s in [source_a, source_b] if s]
        if not sources:
            return desc
        note = f"Conflicting sources: {' vs '.join(sources)}"
        if note in desc:
            return desc
        return f"{desc} {note}".strip() if desc else note

    cleaned: List[dict] = []
    index_by_key: Dict[tuple, int] = {}
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        base_title = item.get("title") or item.get("description") or "Untitled"
        title = base_title
        date = item.get("date") or item.get("time") or item.get("timestamp") or "Unknown"
        source = item.get("source") or item.get("source_url") or item.get("url")
        credibility_tier = item.get("credibility_tier")

        desc = item.get("description", "")
        if source:
            cred = evaluate_credibility(source)
            credibility_tier = credibility_tier or cred.source_type
            if cred.score < 70 and "low-credibility source" not in (desc or "").lower():
                desc = (desc or "").strip()
                desc = f"{desc} (Low-credibility source; treat as unverified.)".strip()
        else:
            # Without a source, mark as unknown credibility in metadata, not title prefix.
            credibility_tier = credibility_tier or "unknown"

        if not date:
            date = "Unknown"

        key = (date, _normalize_title(base_title))
        if key in index_by_key:
            existing = cleaned[index_by_key[key]]
            desc = item.get("description", "")
            existing_desc = existing.get("description", "")
            existing_source = existing.get("source")
            conflict = False
            if source and existing_source and source != existing_source:
                conflict = True
            if desc and existing_desc and desc.strip() != existing_desc.strip():
                conflict = True

            if conflict:
                existing["description"] = _append_conflict_note(existing_desc, existing_source, source)
            elif not existing_source and source:
                existing["source"] = source
            # Keep the stronger credibility tier if available
            if credibility_tier and not existing.get("credibility_tier"):
                existing["credibility_tier"] = credibility_tier
            continue

        cleaned.append(
            {
                "date": date,
                "title": title,
                "description": desc,
                "source": source,
                "credibility_tier": credibility_tier,
            }
        )
        index_by_key[key] = len(cleaned) - 1
    return cleaned


def _build_fact_table(
    timeline: List[dict], conflicts: List[dict], official_sources: List[str]
) -> Dict[str, List[dict]]:
    """
    Build a structured fact table the LLM must stick to.
    Verified only if there is at least one official source AND the entry source is official.
    Everything else is Unverified/Disputed to avoid hallucinated certainty.
    """
    facts_verified: List[dict] = []
    facts_unverified: List[dict] = []
    official_set = set(official_sources or [])
    has_official = bool(official_set)

    for item in timeline or []:
        title = item.get("title", "Untitled")
        source = item.get("source")
        date = item.get("date", "Unknown")
        is_disputed = "[disputed]" in title.lower()
        if not is_disputed and has_official and source and source in official_set:
            facts_verified.append({"fact": title, "date": date, "source": source})
        else:
            facts_unverified.append({"fact": title, "date": date, "source": source or "Unknown"})

    for conf in conflicts or []:
        topic = conf.get("topic", "Unknown conflict")
        verdict = conf.get("verdict", "Unknown verdict")
        facts_unverified.append(
            {"fact": f"Conflict resolution for {topic}: {verdict}", "date": "Unknown", "source": "Debater"}
        )

    return {"verified": facts_verified, "unverified": facts_unverified}


def _strip_section_by_heading(text: str, headings: List[str]) -> str:
    if not text:
        return ""
    heading_set = {h.strip() for h in headings if h}
    if not heading_set:
        return text
    lines = text.splitlines()
    out_lines = []
    skip = False
    for line in lines:
        if not skip and line.strip() in heading_set:
            skip = True
            continue
        if skip and line.startswith("## "):
            skip = False
        if not skip:
            out_lines.append(line)
    return "\n".join(out_lines).strip()


def _replace_in_sections(
    text: str, section_headings: List[str], replacements: List[tuple[str, str]]
) -> str:
    if not text:
        return ""
    target_headings = {h.strip() for h in section_headings if h}
    if not target_headings:
        return text

    lines = text.splitlines()
    sections: List[tuple[str | None, List[str]]] = []
    current_heading = None
    current_lines: List[str] = []

    for line in lines:
        if line.startswith("## "):
            sections.append((current_heading, current_lines))
            current_heading = line.strip()
            current_lines = []
        else:
            current_lines.append(line)
    sections.append((current_heading, current_lines))

    rebuilt: List[str] = []
    for heading, content_lines in sections:
        if heading:
            rebuilt.append(heading)
        content = "\n".join(content_lines)
        if heading in target_headings:
            for pattern, replacement in replacements:
                content = re.sub(pattern, replacement, content, flags=re.I)
        if content:
            rebuilt.append(content)
    return "\n".join(rebuilt).strip()


def _sanitize_llm_output(content: str, has_official: bool, has_verified: bool) -> str:
    if not content:
        return ""
    cleaned = content
    cleaned = _strip_section_by_heading(
        cleaned,
        ["## Timeline Visualization", "## Timeline Visualization (ASCII)"],
    )
    cleaned = _strip_section_by_heading(cleaned, ["## References"])
    cleaned = re.sub(
        r"^References will be appended automatically.*$",
        "",
        cleaned,
        flags=re.M,
    )
    if not has_official or not has_verified:
        cleaned = cleaned.replace(
            "## Key Findings (Verified)", "## Key Findings (Unverified/Disputed)"
        )
        cleaned = cleaned.replace("### Verified vs. Disputed", "### Unverified vs. Disputed")
    if not has_official:
        cleaned = _replace_in_sections(
            cleaned,
            [
                "## Executive Summary",
                "## Key Findings (Verified)",
                "## Key Findings (Unverified/Disputed)",
                "## Key Findings",
            ],
            [
                (r"\bofficially\b", "reportedly"),
                (r"\bconfirmed\b", "reported"),
                (r"\bofficial announcement\b", "reported announcement"),
            ],
        )
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


async def finalizer_node(state: GlobalState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Phase 0 finalizer: structured -> deterministic render + Gate2 audit.
    """
    objective = state.get("objective", state.get("original_query", "Unknown Objective"))
    notes = state.get("research_notes", [])
    timeline = state.get("timeline", [])
    conflicts = state.get("conflicts", [])
    run_id = state.get("run_id") or config.get("configurable", {}).get("thread_id") or str(uuid.uuid4())
    current_ts = datetime.utcnow().isoformat()

    configurable = config.get("configurable", {})
    model_name = configurable.get("finalizer_model", settings.model_name or "gpt-4o")
    severity_map = _load_gate2_severity()
    enabled_policies_snapshot = {
        "phase": "phase0",
        "renderer_version": RENDERER_VERSION,
        "gate2_severity_config_path": getattr(settings, "gate2_severity_config", None),
        "gate2_severity": severity_map,
    }

    if settings.openai_base_url and "openai.com" not in settings.openai_base_url:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_base_url,
            temperature=0,
        )
    else:
        llm = init_chat_model(model=model_name, temperature=0)

    cleaned_timeline = _clean_timeline_entries(timeline)
    facts_index = _build_facts_index(cleaned_timeline, objective, run_id)
    allowed_event_ids = [f.get("event_id") for f in facts_index.get("facts", []) if f.get("event_id")]

    # If we have no grounded facts at all, short-circuit with a guarded minimal report.
    if not facts_index.get("facts"):
        structured_report = {
            "report_id": run_id,
            "run_id": run_id,
            "generated_at": current_ts,
            "sections": [
                {
                    "section_id": "executive_summary",
                    "title": "Executive Summary",
                    "items": [
                        {
                            "item_id": 1,
                            "item_text": f"No grounded evidence collected for: {objective}. Report cannot provide verified claims.",
                            "role": "analysis",
                            "event_ids": [],
                            "assertion_strength": "hedged",
                            "dispute_status": "none",
                            "conflict_group_id": None,
                        }
                    ],
                }
            ],
        }
        report_citations = _export_sidecar(structured_report)
        gate_report = {
            "summary": {"hard": 1, "soft": 0, "warn": 0},
            "violations": [
                {
                    "severity": "HARD",
                    "rule_id": "no_evidence",
                    "item_id": 1,
                    "details": "facts_index is empty; no grounded evidence available.",
                }
            ],
            "facts_index_size": 0,
        }
        final_report = _render_markdown_from_structured(structured_report, gate_report, objective, current_ts)
        return {
            "run_id": run_id,
            "facts_index": facts_index,
            "structured_report": structured_report,
            "report_citations": report_citations,
            "gate_report": gate_report,
            "final_report": final_report,
            "enabled_policies_snapshot": enabled_policies_snapshot,
        }

    structured_report, gen_errors = await _generate_structured_report(
        llm=llm,
        model_name=model_name,
        run_id=run_id,
        objective=objective,
        cleaned_timeline=cleaned_timeline,
        conflicts=conflicts,
        allowed_event_ids=allowed_event_ids,
        notes=notes,
        current_ts=current_ts,
    )
    if gen_errors:
        structured_report.setdefault("generation_errors", []).extend(gen_errors)

    report_citations = _export_sidecar(structured_report)
    _enforce_dispute_rules(structured_report)
    gate_report = _gate2_audit(structured_report, facts_index, severity_map=severity_map)
    final_report = _render_markdown_from_structured(structured_report, gate_report, objective, current_ts)

    return {
        "run_id": run_id,
        "facts_index": facts_index,
        "structured_report": structured_report,
        "report_citations": report_citations,
        "gate_report": gate_report,
        "final_report": final_report,
        "enabled_policies_snapshot": enabled_policies_snapshot,
    }


def _build_facts_index(timeline: List[dict], objective: str, run_id: str) -> dict:
    def _normalize_key(title: str) -> str:
        normalized = re.sub(r"\s+", " ", (title or "").lower()).strip()
        normalized = re.sub(r"[^a-z0-9\s]+", "", normalized)
        return normalized or "untitled"

    facts_by_key: Dict[tuple, dict] = {}
    counter = 1

    for item in timeline or []:
        if not isinstance(item, dict):
            continue
        url = item.get("source") or item.get("source_url") or item.get("url")
        if not url:
            # Without a concrete evidence URL we cannot establish an event anchor
            continue

        title = item.get("title") or item.get("description") or "Untitled"
        date = item.get("date") or item.get("time") or item.get("timestamp") or ""
        key = (date, _normalize_key(title))

        if key not in facts_by_key:
            event_id = item.get("event_id") or f"ev-{counter:04d}"
            counter += 1
            facts_by_key[key] = {
                "event_id": event_id,
                "title": title,
                "topic": objective,
                "date": date,
                "evidences": [],
            }
        fact_entry = facts_by_key[key]
        cred = evaluate_credibility(url)
        fact_entry["evidences"].append(
            {
                "url": url,
                "evidence_quote": (item.get("description") or item.get("title") or "")[:280],
                "credibility_tier": cred.source_type or "unknown",
                "retrieval_ts": datetime.utcnow().isoformat(),
            }
        )

    facts = list(facts_by_key.values())
    return {
        "run_id": run_id,
        "generated_at": datetime.utcnow().isoformat(),
        "facts": facts,
    }


def _coerce_json(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try to extract the first JSON object substring
    if "{" in text and "}" in text:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            snippet = text[start : end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                return None
    return None


async def _generate_structured_report(
    llm,
    model_name: str,
    run_id: str,
    objective: str,
    cleaned_timeline: List[dict],
    conflicts: List[dict],
    allowed_event_ids: List[str],
    notes: List[str],
    current_ts: str,
) -> tuple[dict, List[str]]:
    """
    Ask LLM for structured JSON only; retry a couple times, then degrade deterministically.
    """
    errors: List[str] = []
    timeline_excerpt = cleaned_timeline[:12]
    conflict_excerpt = conflicts[:6]
    notes_blob = "\n".join(notes)[:3000]
    allowed_ids = allowed_event_ids or []

    def _messages(extra_hint: str = "") -> List[Any]:
        schema_hint = json.dumps(
            {
                "report_id": run_id,
                "run_id": run_id,
                "generated_at": current_ts,
                "sections": [
                    {
                        "section_id": "executive_summary",
                        "title": "Executive Summary",
                        "items": [
                            {
                                "item_id": 1,
                                "item_text": "Short summary sentence.",
                                "role": "analysis",
                                "event_ids": [],
                                "assertion_strength": "neutral",
                                "dispute_status": "none",
                                "conflict_group_id": None,
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=True,
        )
        user = (
            f"Objective: {objective}\n"
            f"Today: {current_ts}\n"
            f"Allowed event_ids (must not invent new ones): {allowed_ids}\n"
            "If allowed_event_ids is empty, set event_ids: [] and avoid claiming verification.\n"
            "Use ONLY provided notes/timeline/conflicts. Do NOT add new facts or URLs.\n"
            "Sections to include: Executive Summary (2-4 items), Key Findings (2-6 items), Timeline Highlights (<=10 items), Conflicts (if any conflicts provided).\n"
            "Each item must include: item_id (int), item_text (<=240 chars), role (key_claim|support|analysis), "
            "event_ids (subset of allowed_event_ids), assertion_strength (hedged|neutral|strong), "
            "dispute_status (none|disputed|unresolved_conflict), conflict_group_id (nullable).\n"
            "Only set dispute_status != none when you have either >=2 event_ids OR a conflict_group_id. "
            "If you cannot meet that, set dispute_status=none and prefer role=analysis with hedged tone.\n"
            "For role=key_claim, event_ids must be NON-empty. If you cannot cite an event_id, use role=analysis and event_ids=[].\n"
            "When dispute_status != none, set assertion_strength=hedged.\n"
            f"Timeline (truncated): {timeline_excerpt}\n"
            f"Conflicts (truncated): {conflict_excerpt}\n"
            f"Research Notes (truncated): {notes_blob}\n"
            "Return VALID JSON ONLY that conforms to the schema hint below.\n"
            f"Schema hint: {schema_hint}\n"
            f"{extra_hint}"
        )
        return [
            SystemMessage(
                content=(
                    "You are a structured reporting engine. Output only JSON. "
                    "Never hallucinate event_ids; only use the allowed list. "
                    "Keep text concise and grounded strictly in provided evidence."
                )
            ),
            HumanMessage(content=user),
        ]

    for attempt in range(3):
        resp = await safe_ainvoke(llm, _messages("" if attempt == 0 else "Previous output was invalid. Return JSON only."), model_name=model_name)
        parsed = _coerce_json(resp.content or "")
        if isinstance(parsed, dict) and parsed.get("sections"):
            parsed.setdefault("report_id", run_id)
            parsed.setdefault("run_id", run_id)
            parsed.setdefault("generated_at", current_ts)
            return parsed, errors
        errors.append(f"attempt {attempt+1} parse failed")

    fallback = {
        "report_id": run_id,
        "run_id": run_id,
        "generated_at": current_ts,
        "sections": [
            {
                "section_id": "executive_summary",
                "title": "Executive Summary",
                "items": [
                    {
                        "item_id": 1,
                        "item_text": f"No structured report generated for {objective}.",
                        "role": "analysis",
                        "event_ids": [],
                        "assertion_strength": "hedged",
                        "dispute_status": "disputed" if allowed_ids else "none",
                        "conflict_group_id": None,
                    }
                ],
            }
        ],
        "generation_errors": errors,
    }
    return fallback, errors


def _enforce_dispute_rules(structured_report: dict):
    """
    Post-process the structured report to ensure disputed items obey Phase 0 rules.
    If an item is disputed but lacks multi-source support (>=2 event_ids or conflict_group_id),
    downgrade it to analysis/hedged with dispute_status=none.
    """
    for section in structured_report.get("sections", []) or []:
        for item in section.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            dispute_status = (item.get("dispute_status") or "none").lower()
            event_ids = item.get("event_ids") or []
            has_conflict_group = bool(item.get("conflict_group_id"))
            if dispute_status != "none" and len(event_ids) < 2 and not has_conflict_group:
                item["dispute_status"] = "none"
                item["role"] = "analysis"
                item["assertion_strength"] = "hedged"
                if not event_ids:
                    item["event_ids"] = []


def _export_sidecar(structured_report: dict) -> List[dict]:
    citations: List[dict] = []
    for section in structured_report.get("sections", []) or []:
        for item in section.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            citations.append(
                {
                    "section_id": section.get("section_id"),
                    "item_id": item.get("item_id"),
                    "item_text": item.get("item_text"),
                    "role": item.get("role"),
                    "event_ids": item.get("event_ids") or [],
                    "assertion_strength": item.get("assertion_strength"),
                    "dispute_status": item.get("dispute_status"),
                    "conflict_group_id": item.get("conflict_group_id"),
                }
            )
    return citations


def _contains_strong_word(text: str) -> bool:
    strong_terms = ["confirmed", "official", "officially", "已证实", "确定", "铁证", "毫无疑问"]
    # If the sentence is explicitly hedged/attributed, do not treat it as a strong assertion.
    hedge_terms = ["claim", "claims", "claimed", "rumor", "rumors", "rumoured", "rumored", "reportedly", "alleged", "according to", "sources", "multiple sources", "据称", "传言", "传闻", "据报道", "据报"]
    lowered = (text or "").lower()
    if any(h in lowered for h in hedge_terms):
        return False
    return any(term in lowered for term in strong_terms)


def _must_be_key_claim(text: str) -> bool:
    if not text:
        return False
    patterns = [
        r"\b20\d{2}[-/]\d{1,2}",  # date-like
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d+%",
        r"\b(vs\.|versus|caused|led to|resulted in|导致|因为|所以)\b",
    ]
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def _gate2_audit(structured_report: dict, facts_index: dict, *, severity_map: Optional[dict] = None) -> dict:
    severity_map = severity_map or _load_gate2_severity()
    allowed = {f.get("event_id") for f in facts_index.get("facts", []) if f.get("event_id")}
    violations = []
    summary = {"hard": 0, "soft": 0, "warn": 0}

    for section in structured_report.get("sections", []) or []:
        for item in section.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            item_text = item.get("item_text", "")
            event_ids = item.get("event_ids") or []
            dispute_status = (item.get("dispute_status") or "none").lower()
            assertion_strength = (item.get("assertion_strength") or "").lower()
            role = (item.get("role") or "").lower()

            # Severity lookup helper
            def add_violation(rule_id: str, default: str, details: str):
                severity = severity_map.get(rule_id, default).upper()
                if severity == "DISABLE":
                    return
                summary_key = "warn" if severity == "WARN" else ("soft" if severity == "SOFT" else "hard")
                summary[summary_key] += 1
                violations.append(
                    {
                        "severity": severity,
                        "rule_id": rule_id,
                        "item_id": item.get("item_id"),
                        "details": details,
                    }
                )

            # event_id not in allowed list
            invalid_events = [eid for eid in event_ids if eid not in allowed]
            if invalid_events:
                add_violation("event_id_not_in_facts_index", "HARD", f"event_ids not in facts_index: {invalid_events}")

            # Key claims must cite at least one event_id (Phase 0 traceability)
            if role == "key_claim" and not event_ids:
                add_violation(
                    "key_claim_missing_event_ids",
                    "HARD",
                    "key_claim item must cite at least one event_id",
                )

            # HARD: disputed must be hedged and have multi-source support
            if dispute_status != "none":
                if assertion_strength != "hedged":
                    add_violation("disputed_must_be_hedged", "HARD", "disputed item is not hedged")
                if len(event_ids) < 2 and not item.get("conflict_group_id"):
                    add_violation(
                        "disputed_needs_multiple_events",
                        "HARD",
                        "disputed item requires >=2 event_ids or conflict_group_id",
                    )
                if _contains_strong_word(item_text):
                    add_violation(
                        "strong_word_in_disputed",
                        "HARD",
                        "strong confirmation wording used in disputed item",
                    )

            # WARN: likely key claim but role not key_claim
            if _must_be_key_claim(item_text) and role != "key_claim":
                add_violation("must_be_key_claim", "WARN", "item looks like a key claim but role is not key_claim")

    gate_report = {
        "summary": summary,
        "violations": violations,
        "facts_index_size": len(allowed),
    }
    return gate_report


def _load_gate2_severity() -> dict:
    """
    Load severity config from YAML; fallback to built-in defaults if missing.
    """
    default = {
        "event_id_not_in_facts_index": "HARD",
        "key_claim_missing_event_ids": "HARD",
        "disputed_must_be_hedged": "HARD",
        "disputed_needs_multiple_events": "HARD",
        "strong_word_in_disputed": "HARD",
        "must_be_key_claim": "WARN",
    }
    path = getattr(settings, "gate2_severity_config", None)
    if not path:
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            merged = default.copy()
            merged.update({k: str(v).upper() for k, v in data.items() if isinstance(k, str)})
            return merged
    except Exception:
        return default


def _render_markdown_from_structured(structured_report: dict, gate_report: dict, objective: str, current_ts: str) -> str:
    lines = [
        f"# DeepTrace Report: {objective}",
        f"> Generated: {current_ts}",
        f"> Gate2 Summary: HARD={gate_report.get('summary', {}).get('hard', 0)}, WARN={gate_report.get('summary', {}).get('warn', 0)}",
        "",
    ]
    for section in structured_report.get("sections", []) or []:
        lines.append(f"## {section.get('title') or section.get('section_id') or 'Section'}")
        for item in section.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            evs = item.get("event_ids") or []
            ev_str = ", ".join(evs) if evs else "none"
            lines.append(
                f"- ({item.get('role')}/{item.get('assertion_strength')}/dispute={item.get('dispute_status')}) "
                f"[events: {ev_str}] {item.get('item_text')}"
            )
        lines.append("")

    lines.append("## Gate2 Audit")
    if gate_report.get("violations"):
        for v in gate_report["violations"]:
            lines.append(f"- [{v.get('severity')}] {v.get('rule_id')}: item {v.get('item_id')} -> {v.get('details')}")
    else:
        lines.append("- No violations detected.")
    if structured_report.get("generation_errors"):
        lines.append("")
        lines.append("## Generation Errors")
        for err in structured_report.get("generation_errors", []):
            lines.append(f"- {err}")
    return "\n".join(lines).strip() + "\n"
