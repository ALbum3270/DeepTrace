"""
Supervisor Node for DeepTrace V2.
Orchestrates the investigation process by delegating tasks to workers or providing a final answer.
"""

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
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

from src.graph.state_v2 import GlobalState
from src.core.models_v2 import ConductResearch, FinalAnswer, ResolveConflict, BreadthResearch, DepthResearch
from src.core.prompts.v2 import RESEARCH_SYSTEM_PROMPT
from src.core.tools.thinking import think_tool
from src.core.utils.llm_safety import safe_ainvoke

from src.config.settings import settings
from src.core.utils.topic_filter import matches_tokens

# Default Model for Supervisor (Needs reasoning capability)
DEFAULT_SUPERVISOR_MODEL = settings.model_name or "gpt-4o"
MAX_RESEARCH_ROUNDS = 2  # Lower threshold to converge faster in testing
CONFLICT_CANDIDATE_CACHE_MAX = 200
MAX_CONFLICT_CANDIDATES = 200


def _candidate_identity(candidate: dict) -> str:
    candidate_id = (candidate.get("candidate_id") or "").strip().lower()
    if candidate_id:
        return candidate_id
    date = (candidate.get("date") or "").strip().lower()
    topic = (candidate.get("topic") or "").strip().lower()
    if date or topic:
        return f"{date}|{topic}".strip("|")
    return ""


def _prune_conflict_candidates(candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []
    seen = set()
    pruned = []
    for candidate in candidates:
        if not candidate:
            continue
        identity = _candidate_identity(candidate)
        if identity:
            if identity in seen:
                continue
            seen.add(identity)
        pruned.append(candidate)
    if len(pruned) > MAX_CONFLICT_CANDIDATES:
        pruned = pruned[-MAX_CONFLICT_CANDIDATES:]
    return pruned

async def supervisor_node(state: GlobalState, config: RunnableConfig):
    """
    The Brain of DeepTrace V2.
    Decides whether to research more (Worker) or answer (End).
    """
    
    # 1. Config
    configurable = config.get("configurable", {})
    model_name = configurable.get("supervisor_model", DEFAULT_SUPERVISOR_MODEL)
    
    # 2. Tools
    tools = [ConductResearch, BreadthResearch, DepthResearch, ResolveConflict, FinalAnswer, think_tool]
    
    # 3. Model Init
    # 3. Model Init
    # Robust initialization for Custom Endpoints (e.g. DeepSeek/Qwen via ModelScope)
    if settings.openai_base_url and "openai.com" not in settings.openai_base_url:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_base_url,
            temperature=0
        )
    else:
        # Standard fallback
        llm = init_chat_model(model=model_name, model_provider="openai")
        
    supervisor = llm.bind_tools(tools)
    
    # 4. Prompt Construction
    # Using the ODR-inspired Research System Prompt
    # We inject the current Objective and any Research Notes into the context.
    
    # Format current state into prompt
    objective = state.get("objective", "No Objective")
    required_tokens = state.get("required_tokens", [])
    notes = state.get("research_notes", [])
    history_messages = state.get("messages", [])

    # If no tokens, short-circuit with a clear message (avoid off-topic drift)
    if not required_tokens:
        from langchain_core.messages import ToolMessage
        return {
            "messages": [
                ToolMessage(
                    tool_call_id="tokens-missing",
                    content="No required tokens provided; please supply explicit keywords to continue research.",
                )
            ]
        }
    
    # Track research cycles to enforce a soft cap
    executed = state.get("executed_tools", [])
    research_calls = sum(1 for t in executed if t.get("name") in ("ConductResearch", "BreadthResearch", "DepthResearch"))
    # Debug: print current research call count
    import logging
    _logger = logging.getLogger("DeepTrace")
    _logger.info(f"📊 Supervisor: research_calls={research_calls}/{MAX_RESEARCH_ROUNDS}, executed_tools={len(executed)}")

    def _conflict_key_from_payload(payload: dict) -> tuple:
        topic = (payload.get("topic") or "").strip().lower()
        sources = tuple(sorted(set(payload.get("source_ids") or [])))
        claims = tuple(sorted(set(payload.get("claims") or [])))
        return (topic, sources, claims)

    def _conflict_key_from_executed(tool_entry: dict) -> tuple:
        args = tool_entry.get("args") or {}
        payload = {
            "topic": args.get("topic"),
            "claims": args.get("claims"),
            "source_ids": args.get("source_ids"),
        }
        return _conflict_key_from_payload(payload)

    # Auto-trigger ResolveConflict for lightweight conflict candidates
    conflict_candidates = state.get("conflict_candidates", []) or []
    conflict_cache = list(state.get("conflict_candidate_cache", []) or [])
    conflict_cache_set = set(conflict_cache)
    executed_conflicts = {
        _conflict_key_from_executed(t)
        for t in executed
        if t.get("name") == "ResolveConflict"
    }
    new_cache_ids = []

    for candidate in conflict_candidates:
        if not candidate:
            continue
        candidate_id = candidate.get("candidate_id")
        if not candidate_id:
            candidate_id = "|".join(
                [
                    (candidate.get("date") or "").strip().lower(),
                    (candidate.get("topic") or "").strip().lower(),
                ]
            ) or None
        if candidate_id and candidate_id in conflict_cache_set:
            continue
        topic = candidate.get("topic") or ""
        if required_tokens and not matches_tokens(topic, set(required_tokens)):
            continue
        claims = candidate.get("claims") or []
        source_ids = candidate.get("source_ids") or []
        if len(claims) < 2:
            continue
        if len(set(source_ids)) < 2:
            continue
        candidate_key = _conflict_key_from_payload(candidate)
        if candidate_key in executed_conflicts:
            if candidate_id:
                conflict_cache_set.add(candidate_id)
                new_cache_ids.append(candidate_id)
            continue
        if candidate_id:
            conflict_cache_set.add(candidate_id)
            new_cache_ids.append(candidate_id)
        response = AIMessage(
            content="Auto-trigger conflict resolution for same-day multi-source discrepancy.",
            tool_calls=[
                {
                    "id": f"auto-conflict-{abs(hash(candidate_key))}",
                    "name": "ResolveConflict",
                    "args": {
                        "topic": topic,
                        "claims": claims,
                        "source_ids": source_ids,
                    },
                }
            ],
        )
        break
    else:
        response = None

    new_cache = conflict_cache + new_cache_ids
    if len(new_cache) > CONFLICT_CANDIDATE_CACHE_MAX:
        new_cache = new_cache[-CONFLICT_CANDIDATE_CACHE_MAX:]
    cache_updated = new_cache != conflict_cache

    # Current Context (Summary of what we have found so far)
    # Context Compression: Keep last 3 full notes, truncate older ones
    context_parts = []
    for i, n in enumerate(notes):
        if i >= len(notes) - 3:
             context_parts.append(f"- Note: {n}")
        else:
             snippet = n[:100] + "..." if len(n) > 100 else n
             context_parts.append(f"- (Old) Note: {snippet} (Truncated)")
             
    context_str = "\n".join(context_parts)
    if not context_str:
        context_str = "No research notes yet."

    # Include recent tool results (e.g., Debater verdicts or dedup warnings)
    tool_messages = [
        m
        for m in history_messages
        if getattr(m, "type", None) == "tool" and getattr(m, "content", None)
    ]
    tool_context_lines = []
    for tm in tool_messages[-2:]:
        content = tm.content.strip()
        if len(content) > 500:
            content = content[:500] + "..."
        tool_context_lines.append(f"- ToolResult: {content}")
    tool_context = "\n".join(tool_context_lines) if tool_context_lines else "No tool results yet."
    def _last_tool_name(messages):
        for idx in range(len(messages) - 1, -1, -1):
            msg = messages[idx]
            if getattr(msg, "type", None) == "tool":
                tool_call_id = getattr(msg, "tool_call_id", None)
                if not tool_call_id:
                    return None
                for j in range(idx - 1, -1, -1):
                    prev = messages[j]
                    if hasattr(prev, "tool_calls") and prev.tool_calls:
                        for tc in prev.tool_calls:
                            if tc.get("id") == tool_call_id:
                                return tc.get("name")
                return None
        return None

    last_tool_name = _last_tool_name(history_messages)
    force_finalize = any(
        ("do not call this tool again" in tm.content.lower())
        or ("retrieved from cache" in tm.content.lower())
        for tm in tool_messages[-5:]
    ) or any(
        "retrieved from cache" in tm.content.lower() for tm in tool_messages
    )
        
    system_msg = RESEARCH_SYSTEM_PROMPT.format(
        research_topic=objective # In initial prompt, objective is the topic
    )
    
    # We append a specific instruction about the current context
    think_instruction = ""
    if last_tool_name and last_tool_name.lower() == "think_tool":
        think_instruction = "You already called think_tool. Do not call it again; choose the next action."
    else:
        think_instruction = "Remember to call think_tool before any other tool."

    if force_finalize:
        context_instruction = (
            f" Current Research Findings:\n{context_str}\n\n"
            f"Recent Tool Results:\n{tool_context}\n\n"
            "A prior tool call was blocked as a duplicate. You MUST call FinalAnswer now "
            "using the existing information. Do NOT call any other tool."
        )
    else:
        context_instruction = (
            f" Current Research Findings:\n{context_str}\n\n"
            f"Recent Tool Results:\n{tool_context}\n\n"
            f"{think_instruction} "
            "If a tool result indicates a conflict was resolved or cached, do NOT call ResolveConflict again. "
            "Assess if this information is sufficient to answer the objective. "
            "If yes, call FinalAnswer. If no, call ConductResearch with a specific sub-topic."
        )
    
    messages = [
        SystemMessage(content=system_msg + context_instruction),
        HumanMessage(
            content=(
                f"Current Objective: {objective}\n"
                f"Required tokens (on-topic filter): {required_tokens}\n"
                "All research queries MUST include these tokens explicitly. "
                "If no matching information is found, report 'No Data for required tokens' instead of switching topic."
            )
        ),
    ]
    
    # 5. Execution
    fallback_finalize = False
    # If recent tool messages indicate duplicate/cache, force FinalAnswer to avoid loops
    if response is not None:
        pass
    elif force_finalize or research_calls >= MAX_RESEARCH_ROUNDS:
        from langchain_core.messages import AIMessage
        fallback_finalize = True
        fallback_reason = (
            "Prior tool was blocked; forcing FinalAnswer."
            if force_finalize
            else f"Research cap reached ({MAX_RESEARCH_ROUNDS}); finalize with current notes."
        )
        fallback_content = "\n".join(notes) if notes else "Finalize based on existing information."
        response = AIMessage(
            content=fallback_reason,
            tool_calls=[{
                "id": "final-answer-cache",
                "name": "FinalAnswer",
                "args": {"content": fallback_content}
            }]
        )
    else:
        # The supervisor returns a Message with Tool Calls.
        response = await safe_ainvoke(supervisor, messages, model_name=model_name)
    
    # 6. Semantic Deduplication & state update
    messages_out = [response]
    new_executed = []
    final_report = None
    
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_calls = response.tool_calls
        tool_names = {tc.get("name") for tc in tool_calls if tc.get("name")}

        # If FinalAnswer is present, ignore other tool calls for safety.
        if "FinalAnswer" in tool_names:
            for tc in tool_calls:
                if tc.get("name") != "FinalAnswer":
                    continue
                tool_args = tc.get("args", {})
                new_executed.append({"name": "FinalAnswer", "args": tool_args})
                final_report = tool_args.get("content", "")
                break
        else:
            from src.core.verification.provenance import compute_semantic_similarity
            for tc in tool_calls:
                tool_name = tc.get("name")
                tool_args = tc.get("args", {})
                tool_call_id = tc.get("id")

                if tool_name in ("ConductResearch", "BreadthResearch", "DepthResearch"):
                    current_topic = tool_args.get("topic", "")
                    # Enforce tokens in topic
                    if required_tokens and not any(tok in current_topic.lower() for tok in required_tokens):
                        current_topic = f"{current_topic} {' '.join(required_tokens)}".strip()
                        tc["args"]["topic"] = current_topic
                    if not required_tokens:
                        from langchain_core.messages import ToolMessage
                        tm = ToolMessage(tool_call_id=tool_call_id, content="No required tokens provided; cannot proceed.")
                        messages_out.append(tm)
                        continue

                    is_dup = False
                    for past_tool in executed:
                        if past_tool["name"] in ("ConductResearch", "BreadthResearch", "DepthResearch"):
                            past_topic = past_tool["args"].get("topic", "")
                            sim = compute_semantic_similarity(current_topic, past_topic)
                            if sim >= settings.SEMANTIC_SIMILARITY_THRESHOLD:
                                is_dup = True
                                from langchain_core.messages import ToolMessage
                                warning_msg = (
                                    f"Semantic duplicate detected (Sim={sim:.2f}). "
                                    f"You already researched '{past_topic}'. "
                                    "Please choose a different perspective or proceed to FinalAnswer. Do not call this tool again."
                                )
                                tm = ToolMessage(tool_call_id=tool_call_id, content=warning_msg)
                                messages_out.append(tm)
                                break

                    if not is_dup:
                        new_executed.append({"name": tool_name, "args": tool_args})

                elif tool_name == "ResolveConflict":
                    # Dedup Conflict Resolution to prevent infinite loops (Supervisor <-> Debater)
                    current_topic = tool_args.get("topic", "")
                    is_dup = False
                    for past_tool in executed:
                        if past_tool["name"] == "ResolveConflict":
                            past_topic = past_tool["args"].get("topic", "")
                            if current_topic == past_topic:
                                is_dup = True
                                from langchain_core.messages import ToolMessage
                                success_msg = (
                                    f"Result for '{past_topic}': [RETRIEVED FROM CACHE]\n"
                                    "Conflict has been analyzed. Please use the existing knowledge to formulate your Final Answer.\n"
                                    "Do NOT call this tool again for this topic."
                                )
                                tm = ToolMessage(tool_call_id=tool_call_id, content=success_msg)
                                messages_out.append(tm)
                                break

                    if not is_dup:
                        new_executed.append({"name": tool_name, "args": tool_args})

                else:
                    new_executed.append({"name": tool_name, "args": tool_args})

    result = {
        "messages": messages_out,
        "executed_tools": new_executed
    }
    if cache_updated:
        result["conflict_candidate_cache"] = new_cache
    if fallback_finalize:
        pending_candidates = state.get("conflict_candidates") or []
        pruned_candidates = _prune_conflict_candidates(pending_candidates)
        if pruned_candidates != pending_candidates:
            result["conflict_candidates"] = pruned_candidates
        if pending_candidates:
            result["investigation_log"] = [
                f"Forced finalize with {len(pending_candidates)} unresolved conflict candidates."
            ]
    if final_report:
        result["final_report"] = final_report
    return result
