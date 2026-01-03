"""
Final report generator for DeepTrace V2.
"""

import re
from datetime import datetime
from typing import Dict, Any, List, Tuple

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain.chat_models import init_chat_model

from src.config.settings import settings
from src.core.prompts.v2 import FINALIZER_SYSTEM_PROMPT
from src.core.utils.llm_safety import safe_ainvoke
from src.graph.state_v2 import GlobalState
from src.core.models.credibility import evaluate_credibility
from src.core.utils.topic_filter import matches_tokens, extract_tokens

import json

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
    - Keep only entries with credibility >= reputable when a source URL exists.
    - Mark missing-source entries as disputed to avoid overstating certainty.
    """
    def _normalize_title(raw_title: str) -> str:
        normalized = re.sub(r"\s+", " ", raw_title.lower()).strip()
        normalized = re.sub(r"[^a-z0-9\s]+", "", normalized)
        return normalized

    def _mark_disputed(raw_title: str) -> str:
        return raw_title if raw_title.lower().startswith("[disputed]") else f"[Disputed] {raw_title}"

    def _strip_disputed(raw_title: str) -> str:
        lowered = raw_title.lower()
        if lowered.startswith("[disputed]"):
            stripped = raw_title[len("[Disputed]") :].strip()
            return stripped or raw_title
        return raw_title

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

        if source:
            cred = evaluate_credibility(source)
            if cred.score < 70:
                # Drop low-credibility timeline points to avoid polluting the report.
                continue
        else:
            # Without a source, keep but mark as disputed.
            title = _mark_disputed(title)

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
                existing["title"] = _mark_disputed(existing.get("title", "Untitled"))
                existing["description"] = _append_conflict_note(existing_desc, existing_source, source)
            elif not existing_source and source:
                existing["source"] = source
                existing["title"] = _strip_disputed(existing.get("title", "Untitled"))
            continue

        cleaned.append(
            {
                "date": date,
                "title": title,
                "description": item.get("description", ""),
                "source": source,
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
    Generate the final report using the V2 template.
    """
    objective = state.get("objective", "Unknown Objective")
    notes = state.get("research_notes", [])
    timeline = state.get("timeline", [])
    logs = state.get("investigation_log", [])
    messages = state.get("messages", [])
    conflict_candidates = state.get("conflict_candidates", []) or []
    current_date_obj = datetime.utcnow().date()
    current_date = current_date_obj.isoformat()

    configurable = config.get("configurable", {})
    model_name = configurable.get("finalizer_model", settings.model_name or "gpt-4o")

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

    urls = _extract_urls(notes)
    topic_tokens = set(state.get("required_tokens") or _topic_tokens(objective))
    # Filter URLs by topic tokens
    urls = [u for u in urls if matches_tokens(u, topic_tokens)]
    if not topic_tokens:
        # strict mode: if no tokens, treat as unverified/no sources
        urls = []
    buckets, stats = _summarize_sources(urls)
    buckets = _filter_official_buckets(buckets)

    # LLM verify suspected official sources
    snippets = _build_snippet_map(urls, notes)
    official_verified = []
    downgraded = []
    verifier_model = configurable.get("verifier_model", "gpt-4o-mini")
    for url in list(buckets.get("official", [])):
        verdict = await _llm_verify_official(url, objective, snippets.get(url, ""), verifier_model)
        if (
            verdict.get("classification") == "Official Announcement"
            and verdict.get("is_company_voice")
            and verdict.get("is_on_topic")
            and verdict.get("event_status") == "Past/Confirmed"
        ):
            official_verified.append(url)
        else:
            downgraded.append(url)

    buckets["official"] = official_verified
    if downgraded:
        buckets.setdefault("reputable", []).extend(downgraded)

    stats = {
        "total": len(urls),
        "verified": len(buckets["official"]),
        "reputable": len(buckets["reputable"]),
        "rumor": len(buckets["low"]),
    }
    evidence_count = stats["total"]
    draft = _get_final_answer_draft(messages)
    conflicts = state.get("conflicts", [])
    cleaned_timeline = _clean_timeline_entries(
        [t for t in timeline if matches_tokens(t.get("title", "") + " " + t.get("description", ""), topic_tokens)]
    )
    timeline_ascii = _render_ascii_timeline(cleaned_timeline)
    fact_table = _build_fact_table(cleaned_timeline, conflicts, buckets["official"])
    has_verified = bool(fact_table["verified"])
    has_official = bool(buckets["official"])

    data_warnings = []
    if not cleaned_timeline:
        data_warnings.append("No timeline entries extracted.")
    if not urls:
        data_warnings.append("No credible source URLs detected.")
    if conflict_candidates and not conflicts:
        data_warnings.append(f"{len(conflict_candidates)} unresolved conflict candidates remain.")
    recency_threshold = configurable.get("recency_threshold_days", 30)
    latest_date = _latest_timeline_date(cleaned_timeline)
    if latest_date:
        lag_days = (current_date_obj - latest_date).days
        if lag_days > recency_threshold:
            data_warnings.append(
                f"Latest timeline evidence is {latest_date.isoformat()} ({lag_days} days behind). Report may be outdated."
            )
    data_warning_block = "\n".join([f"- {w}" for w in data_warnings]) if data_warnings else "None"

    insufficient_structured = not urls and not cleaned_timeline and not conflicts

    # If there is no evidence, return a guarded minimal report to avoid hallucination.
    if not notes:
        minimal_report = (
            f"# DeepTrace Report: {objective}\n\n"
            f"> **Generated**: {current_date}\n"
            f"> **Evidence Stats**: 0 Sources (Verified: Unknown, Reputable: Unknown, Rumors: Unknown)\n"
            f"> **Confidence Score**: Unknown\n"
            f"> **Time Anchor**: Unknown\n\n"
            "---\n\n"
            "Insufficient evidence collected. No research notes are available to generate a grounded report.\n\n"
            f"Data limitations:\n{data_warning_block}"
        )
        return {"final_report": minimal_report}
    if insufficient_structured:
        minimal_report = (
            f"# DeepTrace Report: {objective}\n\n"
            f"> **Generated**: {current_date}\n"
            f"> **Evidence Stats**: {evidence_count} Sources (Verified: {stats['verified']}, "
            f"Reputable: {stats['reputable']}, Rumors: {stats['rumor']})\n"
            f"> **Confidence Score**: Low\n"
            f"> **Time Anchor**: Unknown\n\n"
            "---\n\n"
            "Insufficient structured evidence to generate a grounded report.\n\n"
            f"Data limitations:\n{data_warning_block}"
        )
        return {"final_report": minimal_report}

    context = (
        f"Objective: {objective}\n\n"
        f"Today: {current_date}\n"
        f"Evidence Count (estimated): {evidence_count}\n"
        f"Evidence Verified Count: {stats['verified']}\n"
        f"Evidence Reputable Count: {stats['reputable']}\n"
        f"Evidence Rumor Count: {stats['rumor']}\n"
        f"Official Sources (only these may support 'Verified'): {buckets['official']}\n"
        f"Reputable Sources (can support, but note they are not official): {buckets['reputable']}\n"
        f"Low Credibility Sources (cannot support verification): {buckets['low']}\n"
        f"Source Bucket Summary: official={len(buckets['official'])}, reputable={len(buckets['reputable'])}, low={len(buckets['low'])}\n"
        f"Research Notes (verbatim, use only these):\n{chr(10).join(notes)}\n\n"
        f"Timeline Entries (use only these, do not invent):\n{cleaned_timeline if cleaned_timeline else 'None'}\n\n"
        f"Timeline (ASCII, include as-is):\n{timeline_ascii}\n\n"
        f"Conflicts (structured, use only these):\n{conflicts if conflicts else 'None'}\n\n"
        f"Fact Table (must only use these facts):\n"
        f"- Verified Facts: {fact_table['verified'] if fact_table['verified'] else 'None'}\n"
        f"- Unverified/Disputed Facts: {fact_table['unverified'] if fact_table['unverified'] else 'None'}\n\n"
        f"Data Quality Warnings:\n{data_warning_block}\n\n"
        f"Conflict/Process Log:\n{chr(10).join(logs) if logs else 'None'}\n\n"
        f"Supervisor Draft (if any, use only as-is):\n{draft if draft else 'None'}"
    )

    if buckets["official"]:
        time_anchor = "Relies on confirmed official announcements"
    elif buckets["reputable"]:
        time_anchor = "No confirmed official announcements; uses reputable sources only (provisional)"
    else:
        time_anchor = "No official/reputable sources; findings are unverified"

    header = (
        f"# DeepTrace Report: {objective}\n\n"
        f"> **Generated**: {current_date}\n"
        f"> **Evidence Stats**: {evidence_count} Sources (Verified: {stats['verified']}, Reputable: {stats['reputable']}, Rumors: {stats['rumor']})\n"
        f"> **Confidence Score**: Unknown\n"
        f"> **Time Anchor**: {time_anchor}\n\n"
        "---\n\n"
    )

    system_msg = FINALIZER_SYSTEM_PROMPT.format(research_topic=objective)
    user_msg = (
        "Produce ONLY the sections after the header (starting from '## Executive Summary'). "
        "Do NOT rewrite the header; it will be prepended. "
        "Use ONLY the provided notes/timeline/logs/conflicts. Do NOT add new sources, URLs, dates, or claims. "
        "If information is missing, write 'Unknown'. Keep ASCII-only for the timeline. "
        "Evidence Stats and Generated date are fixed in the header; do not change them. "
        "Do NOT add a Timeline Visualization or References section; they will be injected automatically. "
        "Verification rule: Only official announcement URLs (dated press/blog/release pages) may support 'Verified' statements. "
        "If there are zero such official sources, all findings are provisional; avoid 'official/confirmed' wording and treat conclusions as Unverified/Disputed even if reputable sources exist. "
        "Low-credibility sources cannot justify verification; mark such findings as Unverified/Disputed. "
        "In Key Findings, clearly separate Verified (only use facts listed under Verified Facts) vs Unverified/Disputed (only use the provided Unverified/Disputed Facts). "
        "If there are zero Verified Facts, label the section as 'Key Findings (Unverified/Disputed)' and do NOT include a Verified subsection. "
        "You MUST only restate facts from the Fact Table; do NOT add new facts, dates, or sources. "
        "Do NOT duplicate the ASCII timeline block.\n\n"
        f"{context}"
    )
    messages = [
        SystemMessage(content=system_msg),
        HumanMessage(content=user_msg),
    ]

    response = await safe_ainvoke(llm, messages, model_name=model_name)

    references_section = ""
    if urls:
        references_lines = []
        ref_idx = 1
        if buckets["official"]:
            references_lines.append("### Official")
            for url in buckets["official"]:
                references_lines.append(f"[{ref_idx}] {url}")
                ref_idx += 1
        if buckets["reputable"]:
            references_lines.append("### Reputable")
            for url in buckets["reputable"]:
                references_lines.append(f"[{ref_idx}] {url}")
                ref_idx += 1
        if buckets["low"]:
            references_lines.append("### Low Credibility")
            for url in buckets["low"]:
                references_lines.append(f"[{ref_idx}] {url}")
                ref_idx += 1
        references_section = "\n\n## References\n" + "\n".join(references_lines)

    # Insert ASCII timeline directly after header to avoid LLM hallucination
    timeline_block = "\n## Timeline Visualization (ASCII)\n```plaintext\n" + timeline_ascii + "\n```\n\n"

    sanitized_content = _sanitize_llm_output(
        response.content or "", has_official=has_official, has_verified=has_verified
    )
    final_report = header + timeline_block + sanitized_content + references_section
    return {"final_report": final_report}
