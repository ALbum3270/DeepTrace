"""
Worker Nodes for DeepTrace V2.
Implements the core actions of the Investigator: Fetching and Extracting (Prototyping).
"""

from typing import List, Dict
import re
import logging
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
try:
    from langchain.chat_models import init_chat_model  # type: ignore
except ImportError:
    from langchain_openai import ChatOpenAI  # type: ignore
    from src.config.settings import settings
    def init_chat_model(model: str, temperature=0, model_provider=None, **kwargs):
        return ChatOpenAI(
            model=model,
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_base_url,
            temperature=temperature,
        )
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None  # Optional dependency; handled at runtime

from src.config.settings import settings
from src.graph.state_v2 import WorkerState
from src.core.tools.search import tavily_search_tool
from src.core.models.v2_structures import SearchConfiguration, ExtractionResult
from src.core.prompts.v2_search import QUERY_GENERATOR_SYSTEM_PROMPT
from src.core.prompts.v2_extraction import EXTRACTION_SYSTEM_PROMPT
from src.core.utils.llm_safety import safe_ainvoke
from src.llm.thinking import emit_think_plan
from src.core.models.credibility import evaluate_credibility
from src.core.utils.topic_filter import matches_tokens

logger = logging.getLogger(__name__)


def _normalize_date_string(date_str: str) -> str:
    """
    Normalize date strings to YYYY-MM-DD / YYYY-MM / YYYY; otherwise 'Unknown'.
    """
    if not date_str:
        return "Unknown"
    ds = str(date_str).strip()
    # Accept exact formats
    if len(ds) >= 10 and ds[:10].count("-") == 2:
        return ds[:10]
    # YYYY-MM pattern
    if len(ds) >= 7 and ds[4] == "-" and ds[0:4].isdigit() and ds[5:7].isdigit():
        return ds[:7]
    # YYYY only
    if len(ds) >= 4 and ds[0:4].isdigit():
        return ds[:4]
    return "Unknown"


def _normalize_topic(text: str) -> str:
    if not text:
        return ""
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    normalized = re.sub(r"[^\w\s]+", "", normalized)
    return normalized


def _normalize_claim(text: str) -> str:
    if not text:
        return ""
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    return normalized


def _build_conflict_candidates(timeline_entries: List[dict]) -> List[dict]:
    """
    Detect lightweight conflict candidates:
    - same day
    - same topic (normalized title/description)
    - multiple sources with differing claim text
    """
    groups: Dict[tuple, List[dict]] = {}
    for entry in timeline_entries:
        date = entry.get("date") or "Unknown"
        if date == "Unknown":
            continue
        title = entry.get("title") or ""
        desc = entry.get("description") or ""
        topic_key = _normalize_topic(title or desc)
        if not topic_key:
            continue
        key = (date, topic_key)
        groups.setdefault(key, []).append(entry)

    candidates: List[dict] = []
    for (date, topic_key), entries in groups.items():
        sources = [e.get("source") for e in entries if e.get("source")]
        unique_sources = sorted(set(sources))
        if len(unique_sources) < 2:
            continue
        claim_texts = [
            _normalize_claim(f"{e.get('title','')} {e.get('description','')}").strip()
            for e in entries
        ]
        unique_claims = sorted(set([c for c in claim_texts if c]))
        if len(unique_claims) < 2:
            # multiple sources but same claim -> corroboration, not conflict
            continue

        claims = []
        source_ids = []
        for e in entries:
            claim = f"{e.get('title','')} - {e.get('description','')}".strip(" -")
            claims.append(claim or e.get("title") or "Unknown claim")
            source_ids.append(e.get("source") or "Unknown")

        topic_label = entries[0].get("title") or entries[0].get("description") or topic_key
        candidates.append(
            {
                "candidate_id": f"{date}|{topic_key}",
                "date": date,
                "topic": topic_label,
                "claims": claims,
                "source_ids": source_ids,
            }
        )
    return candidates


async def fetch_node_v2(state: WorkerState, config: RunnableConfig):
    """
    Executes search based on the Topic.
    Uses LLM to generate optimized queries.
    """
    topic = state.get("topic", "")
    required_tokens = state.get("required_tokens") or []
    if not topic:
        return {"messages": [AIMessage(content="No topic provided.")]}
    if not required_tokens:
        # Strict mode: no tokens, no research
        return {"messages": [AIMessage(content="No required tokens; skipping off-topic research.")]}

    # 1. Config
    configurable = config.get("configurable", {})
    model_name = configurable.get("search_model", settings.model_name or "gpt-4o")


    # 2. Generate Queries (LLM)
    queries = [topic] # Default fallback
    
    try:
        # Init LLM
        if settings.openai_base_url and "openai.com" not in settings.openai_base_url and ChatOpenAI:
            llm = ChatOpenAI(
                model=model_name,
                openai_api_key=settings.openai_api_key,
                openai_api_base=settings.openai_base_url,
                temperature=0
            )
        else:
             llm = init_chat_model(model=model_name, temperature=0)
             
        # Plan before action
        await emit_think_plan(
            llm,
            model_name,
            task="Generate search queries",
            context=f"Topic: {topic}",
        )

        # Use PydanticOutputParser for compatibility
        from langchain_core.output_parsers import PydanticOutputParser
        parser = PydanticOutputParser(pydantic_object=SearchConfiguration)
        
        prompt = [
            SystemMessage(content=QUERY_GENERATOR_SYSTEM_PROMPT + "\n\n" + parser.get_format_instructions()),
            HumanMessage(content=f"Topic: {topic}")
        ]
        
        response = await safe_ainvoke(llm, prompt, model_name=model_name)
        config_obj: SearchConfiguration = parser.parse(response.content)
        
        if config_obj and config_obj.queries:
            queries = config_obj.queries
            
    except Exception as e:
        # Fallback to single topic if generation fails
        # logger.warning(f"Query generation failed: {e}")
        pass


    # Inject required tokens into queries to enforce on-topic search
    queries_with_tokens = []
    for q in queries:
        if required_tokens and not matches_tokens(q, set(required_tokens)):
            q = f"{q} {' '.join(required_tokens)}".strip()
        queries_with_tokens.append(q)

    # 3. Call Tool (Execute Search)
    try:
        # Use ainvoke for async tools
        # Search tool accepts 'queries' list
        search_result = await tavily_search_tool.ainvoke(
            {"queries": queries_with_tokens}, config=config
        )
    except Exception as e:
        search_result = f"Search failed: {str(e)}"

    # 4. Store Result in History
    # We include the queries used so the Extractor knows the context
    header = f"Search Queries Used: {queries_with_tokens}\n\n"
    message = AIMessage(content=f"{header}Required tokens: {required_tokens}\nsearch_results: {search_result}")

    return {"messages": [message]}

async def extract_node_v2(state: WorkerState, config: RunnableConfig):
    """
    Extracts structured events from search results using an LLM.
    """
    messages = state.get("messages", [])
    if not messages:
         return {"research_notes": "No search results to extract from.", "conflict_candidates": []}

    # 1. Config
    configurable = config.get("configurable", {})
    model_name = configurable.get("extraction_model", settings.model_name or "gpt-4o")

    # 2. Prepare Context (Concatenate Search Results)
    # We look for the 'AIMessage' from fetch_node that contains "search_results:"
    # Or just use all content if it's simpler.
    search_content = "\n\n".join([m.content for m in messages if hasattr(m, "content")])
    
    if not search_content:
        return {"research_notes": "No content found in search messages.", "conflict_candidates": []}


    # 3. Init LLM
    if settings.openai_base_url and "openai.com" not in settings.openai_base_url and ChatOpenAI:
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_base_url,
            temperature=0
        )
    else:
        llm = init_chat_model(model=model_name, temperature=0)

    # Plan before action
    await emit_think_plan(
        llm,
        model_name,
        task="Extract timeline events",
        context=f"Topic: {state.get('topic', '')}",
    )

    # Use OutputParser instead of tool calling
    from langchain_core.output_parsers import PydanticOutputParser
    parser = PydanticOutputParser(pydantic_object=ExtractionResult)

    # Extract candidate URLs to constrain source_url choices (improves grounding + parse success)
    url_pattern = re.compile(r"https?://[\w\-._~:/?#\[\]@!$&'()*+,;=%]+", re.IGNORECASE)
    available_urls = list(dict.fromkeys([u.rstrip(")].,>\"' ") for u in url_pattern.findall(search_content)]))
    url_hint = ""
    if available_urls:
        url_hint = "Available URLs (use one of these for source_url):\n" + "\n".join(available_urls[:40]) + "\n\n"

    # 4. Invoke
    prompt = [
        SystemMessage(
            content=(
                EXTRACTION_SYSTEM_PROMPT
                + "\n\nReturn JSON only. "
                + parser.get_format_instructions()
            )
        ),
        HumanMessage(
            content=(
                f"{url_hint}Here are the search results:\n{search_content[:20000]}"
            )
        ),  # Limit context to avoid overflow
    ]
    
    try:
        response = await safe_ainvoke(llm, prompt, model_name=model_name)
        try:
            result: ExtractionResult = parser.parse(response.content)
        except Exception:
            # One repair attempt: ask for JSON only
            repair_prompt = [
                SystemMessage(
                    content=(
                        "Your previous output could not be parsed. "
                        "Output ONLY valid JSON that matches the schema.\n\n"
                        + parser.get_format_instructions()
                    )
                ),
                HumanMessage(content=f"{url_hint}Search results:\n{search_content[:20000]}"),
            ]
            response = await safe_ainvoke(llm, repair_prompt, model_name=model_name)
            result = parser.parse(response.content)
        
        # 5. Format Output for Pipeline
        event_lines = []
        timeline_entries = []
        required_tokens = set(state.get("required_tokens") or [])
        for ev in result.events:
            norm_date = _normalize_date_string(ev.date)
            # Filter by topic tokens and credibility
            if required_tokens and not matches_tokens(
                f"{ev.title} {ev.description} {ev.source_url}", required_tokens
            ):
                continue
            # Require a real URL to establish grounding (Phase 0)
            if not ev.source_url or str(ev.source_url).strip().lower() in {"unknown", "n/a", "none"}:
                continue

            cred = evaluate_credibility(ev.source_url)
            title = ev.title
            description = ev.description
            # Keep low-cred sources but mark them as disputed/unverified instead of dropping everything.
            if cred.score < 70:
                if not str(title).lower().startswith("[disputed]"):
                    title = f"[Disputed] {title}"
                if "low-credibility source" not in (description or "").lower():
                    description = (description or "").strip()
                    description = f"{description} (Low-credibility source; treat as unverified.)".strip()

            line = f"[EVENT] {norm_date} | {title} | {description} (Source: {ev.source_url})"
            event_lines.append(line)
            timeline_entries.append(
                {
                    "date": norm_date,
                    "title": title,
                    "description": description,
                    "source": ev.source_url,
                    "credibility_score": cred.score,
                    "credibility_tier": cred.source_type,
                }
            )

        formatted_notes = "\n".join(event_lines)
        conflict_candidates = _build_conflict_candidates(timeline_entries)

        # We append this to the history so Compressor can see it explicitly as "Extracted Intelligence"
        return {
            "messages": [AIMessage(content=f"extracted_events:\n{formatted_notes}")],
            "timeline": timeline_entries,
            "conflict_candidates": conflict_candidates,
        }

    except Exception as e:
        # Fallback to raw content if extraction fails
        return {
            "messages": [AIMessage(content=f"Extraction failed: {str(e)}. Raw results retained.")],
            "timeline": [],
            "conflict_candidates": [],
        }
