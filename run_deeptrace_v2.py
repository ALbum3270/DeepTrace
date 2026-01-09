"""
DeepTrace V2: Official Execution Script
=======================================
Runs the full Orchestrator-Investigator Graph.
- Supervisor: GPT-4o / DeepSeek (via Compatibility)
- Worker: Tavily Search + Crawler + Context Compression
- Debater: Conflict Resolution

Output:
- final_report.md: The generated report.
- execution.log: Detailed trace.
"""

import asyncio
import os
import sys
import uuid
import logging
from datetime import datetime

# Phase1 Sidecar Toggle (set DEEPTRACE_PHASE1_SIDECAR=1 to enable)
PHASE1_SIDECAR_ENABLED = os.getenv("DEEPTRACE_PHASE1_SIDECAR", "0") == "1"

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler("execution.log", mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DeepTrace")

# Windows loop fix
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from langchain_core.messages import HumanMessage, SystemMessage
try:
    from langchain.chat_models import init_chat_model  # type: ignore
except ImportError:
    from langchain_openai import ChatOpenAI  # type: ignore
    def init_chat_model(model: str, temperature=0, model_provider=None, **kwargs):
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_base_url,
        )
from src.graph.graph_v2 import app_v2
from src.config.settings import settings
from src.core.utils.topic_filter import extract_tokens
from src.core.utils.llm_safety import safe_ainvoke

# Phase1 sidecar (conditional import)
if PHASE1_SIDECAR_ENABLED:
    from src.graph.nodes.phase1_sidecar import phase1_sidecar_node


def _resolve_suggestion_model() -> str:
    """
    Choose a small model for suggestion generation; fall back to a known OpenAI alias.
    """
    candidate = settings.model_name or ""
    # If provider prefix is present, keep it; otherwise use a lightweight default.
    if candidate and ":" in candidate:
        return candidate
    return "gpt-4o-mini"


async def _llm_suggest_directions(query: str, model_name: str) -> list[str]:
    """
    Ask a small LLM to propose 3 optional research directions (A/B/C) without changing the objective.
    """
    system = "You propose research focus options. Output exactly 3 options labeled A), B), C). Keep them short."
    user = f"""User query: "{query}"
Generate three alternative research directions (A/B/C). Each should be 5-15 words, focused and distinct.
Do NOT answer the query; only list the options."""
    
    llm = None
    actual_model = model_name
    # Check if using custom OpenAI-compatible endpoint (e.g., Dashscope for Qwen)
    if settings.openai_base_url and "openai.com" not in settings.openai_base_url:
        from langchain_openai import ChatOpenAI
        # Use settings.model_name for custom endpoints, not the passed model_name
        actual_model = settings.model_name or model_name
        try:
            llm = ChatOpenAI(
                model=actual_model,
                openai_api_key=settings.openai_api_key,
                openai_api_base=settings.openai_base_url,
                temperature=0,
            )
        except Exception:
            llm = None
    
    if llm is None:
        tried = []
        for candidate in [model_name, "gpt-4o-mini", "gpt-4o"]:
            if not candidate:
                continue
            tried.append(candidate)
            try:
                llm = init_chat_model(model=candidate, temperature=0)
                actual_model = candidate
                break
            except Exception:
                llm = None
                continue
        if llm is None:
            logger.warning(f"⚠️ Suggestion LLM init failed for {tried}; skipping directions.")
            return []
    try:
        resp = await safe_ainvoke(llm, [SystemMessage(content=system), HumanMessage(content=user)], model_name=actual_model)
        lines = [ln.strip() for ln in (resp.content or "").splitlines() if ln.strip()]
        options = []
        for ln in lines:
            # accept formats like "A) xxx" or "A. xxx"
            if ln[0:1].upper() in {"A", "B", "C"}:
                # strip leading label
                parts = ln.split(")", 1) if ")" in ln[:3] else ln.split(".", 1)
                if len(parts) == 2:
                    ln = parts[1].strip()
            options.append(ln)
            if len(options) >= 3:
                break
        # fallback: if parsing failed, return original lines or empty
        return options[:3]
    except Exception:
        return []


def _select_direction(query: str, directions: list[str]) -> str:
    """
    Interactive selection: A/B/C or 1/2/3 to choose a direction; Enter keeps original query.
    """
    if not directions:
        return query
    if not sys.stdin or not sys.stdin.isatty():
        return query
    labels = ["A", "B", "C"]
    logger.info("\n[💡 可选研究方向 - 默认继续用原始问题]")
    for idx, d in enumerate(directions, 0):
        label = labels[idx] if idx < len(labels) else f"{idx+1}"
        logger.info(f"   [{label}] {d}")
    logger.info(f"\n   [Enter] 使用原始查询: {query}")
    choice = input("请选择 [A/B/C] 或直接回车: ").strip().lower()
    if not choice:
        return query
    mapping = {"a": 0, "b": 1, "c": 2, "1": 0, "2": 1, "3": 2}
    if choice in mapping and mapping[choice] < len(directions):
        return directions[mapping[choice]]
    return query


async def run_deeptrace(query: str):
    logger.info(f"🚀 Starting DeepTrace V2 | Query: {query}")
    logger.info("==================================================")
    
    # Skip LLM-based clarification; keep the original query and simple token extraction.
    suggestion_model = _resolve_suggestion_model()
    directions = await _llm_suggest_directions(query, suggestion_model)
    clarified_query = _select_direction(query, directions)
    tokens = extract_tokens(clarified_query) or extract_tokens(query) or ["research"]
    logger.info(f"🔑 Required Tokens: {tokens}")

    initial_state = {
        "original_query": query,
        "run_id": str(uuid.uuid4()),
        "run_record_path": "",
        "objective": clarified_query,
        "clarification_done": True,
        "research_brief": f"Research goal: {clarified_query}",
        "enabled_policies_snapshot": {},
        "timeline": [],
        "evidences": [],  # Phase1 sidecar will consume this
        "research_notes": [],
        "investigation_log": [],
        "executed_tools": [],
        "conflict_candidates": [],
        "conflict_candidate_cache": [],
        "conflicts": [],
        "final_report": "",
        "messages": [HumanMessage(content=f"Please research this and provide a detailed report: {clarified_query}")],
        "required_tokens": tokens,
    }
    
    config = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 20}
    
    final_output = None
    accumulated_state = dict(initial_state)  # Track accumulated state for sidecar
    
    async for event in app_v2.astream(initial_state, config=config):
        for node_name, state_update in event.items():
            if state_update is None:
                continue
            logger.info(f"\n--- Node: {node_name} ---")
            
            # Accumulate state updates for Phase1 sidecar
            for key, val in state_update.items():
                if isinstance(val, list) and key in accumulated_state and isinstance(accumulated_state[key], list):
                    accumulated_state[key] = accumulated_state[key] + val
                else:
                    accumulated_state[key] = val
            
            # 1. Handle Messages (Supervisor/Debater output)
            if "messages" in state_update:
                last_msg = state_update["messages"][-1]
                
                # Check for Tool Calls
                if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                    for tc in last_msg.tool_calls:
                        logger.info(f"🤖 Supervisor Call: {tc['name']}")
                        # robust check for FinalAnswer (case-insensitive)
                        if tc['name'].lower() == "finalanswer":
                            final_output = tc["args"].get("content", "")
                            logger.info("✅ Final Answer Detected via ToolCall")
                            
                # Check for Content (Debater or Text Fallback)
                elif hasattr(last_msg, "content") and last_msg.content:
                    logger.info(f"📝 Message Content: {last_msg.content[:150]}...")
                    # Update final_output with latest content as fallback
                    if node_name == "supervisor":
                        final_output = last_msg.content

            # 1b. Handle Final Report from finalizer
            if "final_report" in state_update:
                final_output = state_update.get("final_report") or final_output

            # 2. Handle Worker Notes
            if "research_notes" in state_update:
                new_notes = state_update['research_notes']
                if new_notes:
                    logger.info(f"📚 Worker Note: {str(new_notes[0])[:150]}...")
                    
            # 3. Handle Logs
            if "investigation_log" in state_update:
                logs = state_update['investigation_log']
                if logs:
                    logger.warning(f"⚠️  Log: {logs[-1]}")

    # Save Report
    if final_output:
        filename = "final_report.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(final_output)
        logger.info(f"\n💾 REPORT SAVED: {filename} ({len(final_output)} chars)")
        logger.info("Content Preview:\n" + final_output[:500] + "...")
    else:
        logger.error("\n❌ No final report generated.")

    # ========== Phase1 Sidecar Hook ==========
    if PHASE1_SIDECAR_ENABLED:
        evidences = accumulated_state.get("evidences") or []
        timeline = accumulated_state.get("timeline") or []
        if evidences:
            logger.info(f"\n🔬 Phase1 Sidecar: Processing {len(evidences)} evidences, {len(timeline)} events...")
            try:
                sidecar_result = await phase1_sidecar_node(accumulated_state, config)
                logger.info(f"✅ Phase1 Sidecar completed: {sidecar_result.get('phase1_archive', 'N/A')}")
            except Exception as e:
                logger.warning(f"⚠️ Phase1 Sidecar failed: {e}")
        else:
            logger.info("\n⚠️ Phase1 Sidecar skipped: no evidences available")
    # ========================================

if __name__ == "__main__":
    # You can change the query here
    TARGET_QUERY = "OpenAI GPT-5 release"
    
    if not os.getenv("TAVILY_API_KEY"):
        logger.warning("⚠️  TAVILY_API_KEY missing. Search may fail.")
        
    asyncio.run(run_deeptrace(TARGET_QUERY))
