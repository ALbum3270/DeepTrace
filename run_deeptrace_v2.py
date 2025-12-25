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

from langchain_core.messages import HumanMessage
from src.graph.graph_v2 import app_v2
from src.config.settings import settings
from src.core.utils.topic_filter import extract_tokens
from src.graph.nodes.clarify import interactive_clarify

async def run_deeptrace(query: str):
    logger.info(f"🚀 Starting DeepTrace V2 | Query: {query}")
    logger.info("==================================================")
    
    clarified_query, tokens, clarify_logs = await interactive_clarify(
        query, {"configurable": {"clarify_model": settings.model_name or "gpt-4o"}}
    )
    if clarified_query != query:
        logger.info(f"✓ Clarified Query: {clarified_query}")
    for entry in clarify_logs:
        logger.info(f"📋 Clarify: {entry}")

    initial_state = {
        "original_query": query,
        "objective": clarified_query,
        "clarification_done": True,
        "research_brief": f"Research goal: {clarified_query}",
        "timeline": [],
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
    
    config = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 50}
    
    final_output = None
    
    async for event in app_v2.astream(initial_state, config=config):
        for node_name, state_update in event.items():
            if state_update is None:
                continue
            logger.info(f"\n--- Node: {node_name} ---")
            
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

if __name__ == "__main__":
    # You can change the query here
    # TARGET_QUERY = "DeepSeek V3 vs DeepSeek R1 参数对比 (Parameter Comparison)"
    TARGET_QUERY = "OpenAI GPT-5 official release date and key features verified"
    
    if not os.getenv("TAVILY_API_KEY"):
        logger.warning("⚠️  TAVILY_API_KEY missing. Search may fail.")
        
    asyncio.run(run_deeptrace(TARGET_QUERY))
