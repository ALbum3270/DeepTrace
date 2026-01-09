"""
DeepTrace V2 Main Graph.
Assembles the Supervisor, Worker Subgraph, and Debater Tool into the master workflow.
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

from src.graph.state_v2 import GlobalState, WorkerState
from src.graph.nodes.clarify import clarify_node
from src.graph.nodes.supervisor import supervisor_node
from src.graph.nodes.finalizer import finalizer_node
from src.graph.nodes.debater_postprocess import debater_postprocess
from src.graph.nodes.timeline_merge import timeline_merge_node
from src.graph.nodes.archive_node import archive_run_node
from src.graph.subgraphs.worker import worker_app
from src.core.tools.debater import debater_tool
from src.core.tools.thinking import think_tool
from langchain_core.messages import ToolMessage

MAX_CONFLICT_CANDIDATES = 200


def _candidate_identity(candidate: dict) -> str:
    candidate_id = (candidate.get("candidate_id") or "").strip().lower()
    if candidate_id:
        return candidate_id
    date = (candidate.get("date") or "").strip().lower()
    topic = (candidate.get("topic") or "").strip().lower()
    if date or topic:
        return f"{date}|{topic}".strip("|")
    claims = candidate.get("claims") or []
    sources = candidate.get("source_ids") or []
    if claims or sources:
        return f"{'|'.join(claims)}|{'|'.join(sources)}".strip().lower()
    return ""


def _conflict_key(topic: str, claims: list, source_ids: list) -> tuple:
    return (
        (topic or "").strip().lower(),
        tuple(sorted(set(source_ids or []))),
        tuple(sorted(set(claims or []))),
    )

# Hard limit for graph iterations to prevent runaway loops
MAX_GRAPH_ITERATIONS = 8

# Router Logic
def route_supervisor(state: GlobalState) -> Literal[
    "worker",
    "debater",
    "thinking",
    "timeline_merge",
    "finalizer",
    "final_answer",
    "supervisor",
]:
    """
    Decides the next node based on the Supervisor's Tool Call.
    Priority: FinalAnswer > Research tools > ResolveConflict > think_tool
    
    Hard stop: If executed_tools count exceeds MAX_GRAPH_ITERATIONS, force finalize.
    """
    # Hard stop check: force finalize if too many iterations
    executed_tools = state.get("executed_tools", [])
    if len(executed_tools) >= MAX_GRAPH_ITERATIONS:
        import logging
        logging.getLogger("DeepTrace").warning(
            f"⚠️ Hard stop: {len(executed_tools)} tool calls reached limit ({MAX_GRAPH_ITERATIONS}). Forcing finalize."
        )
        return "timeline_merge"
    messages = state.get("messages", [])
    if not messages:
        return "timeline_merge"
        
    last_message = messages[-1]
    
    # If the last message is a ToolMessage (e.g. from Dedup), decide whether to finalize
    if last_message.type == "tool":
         content = getattr(last_message, "content", "") or ""
         lower_content = content.lower()
         # After a cached/dedup tool result, run supervisor once more to finalize
         if "retrieved from cache" in lower_content or "do not call this tool again" in lower_content:
             return "supervisor"
         return "supervisor"
    
    # Check for Tool Calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        tool_names = {tc.get("name") for tc in last_message.tool_calls if tc.get("name")}
        lower_tool_names = {n.lower() for n in tool_names if isinstance(n, str)}
        has_research = any(n in ("ConductResearch", "BreadthResearch", "DepthResearch") for n in tool_names)
        
        # Priority 1: FinalAnswer - always finalize first
        if "FinalAnswer" in tool_names:
            return "timeline_merge"
        
        # Priority 2: Research tools - these are the main work
        if has_research:
            # If think_tool is mixed with research calls, still route to worker to avoid ToolNode errors
            return "worker"
        
        # Priority 3: Conflict resolution
        if "ResolveConflict" in tool_names:
            return "debater"
        
        # Priority 4: Thinking (only if no other actionable tools)
        if "think_tool" in lower_tool_names:
            return "thinking"
            
    # Default fallback (safety net)
    return "timeline_merge"

# Adapter: Convert GlobalState -> WorkerState
def enter_worker(state: GlobalState) -> WorkerState:
    """
    Prepare input for the Worker Subgraph.
    Extracts the 'topic' from the Supervisor's tool call.
    """
    last_message = state["messages"][-1]
    tool_call = last_message.tool_calls[0] # Assumes validated by router
    topic = tool_call["args"].get("topic", "")
    required_tokens = state.get("required_tokens") or []
    # Enforce topic to include required tokens; otherwise fallback to original objective
    if required_tokens and not any(tok in topic.lower() for tok in required_tokens):
        topic = state.get("objective", topic)
    
    return {
        "topic": topic,
        "messages": [], # Reset worker history
        "research_notes": "", # Reset output
        "timeline": [],
        "conflict_candidates": [],
        "required_tokens": required_tokens,
    }

# Adapter: Merge WorkerState -> GlobalState
def exit_worker(state: WorkerState) -> dict:
    """
    Merge the Worker's output (Research Notes) back into Global State.
    """
    notes = state.get("research_notes", "")
    timeline = state.get("timeline", [])
    conflict_candidates = state.get("conflict_candidates", [])
    update = {
        "research_notes": [notes] if notes else [],
    }
    if timeline:
        update["timeline"] = timeline
    if conflict_candidates:
        update["conflict_candidates"] = conflict_candidates
    return update

# Wrapper Node for Worker Subgraph
async def worker_node(state: GlobalState, config) -> dict:
    """Wrapper to bridge GlobalState <-> WorkerState."""
    try:
        last_message = state["messages"][-1]
        tool_calls = [tc for tc in last_message.tool_calls if tc.get("name") in ("ConductResearch", "BreadthResearch", "DepthResearch")]
        if not tool_calls:
            return {"investigation_log": ["Worker called without ConductResearch tool calls."]}

        required_tokens = state.get("required_tokens") or []
        existing_candidates = state.get("conflict_candidates") or []
        processed_candidate_ids = set(state.get("conflict_candidate_cache") or [])
        resolved_conflicts = state.get("conflicts") or []
        resolved_keys = {
            _conflict_key(
                conf.get("topic"),
                conf.get("claims") or [],
                conf.get("source_ids") or [],
            )
            for conf in resolved_conflicts
            if conf
        }

        async def _run_worker(tc):
            topic = tc.get("args", {}).get("topic", "")
            if required_tokens and not any(tok in topic.lower() for tok in required_tokens):
                topic = state.get("objective", topic)
            worker_input = {
                "topic": topic,
                "messages": [],
                "research_notes": "",
                "timeline": [],
                "conflict_candidates": [],
                "required_tokens": required_tokens,
            }
            return await worker_app.ainvoke(worker_input, config)

        import asyncio
        worker_outputs = await asyncio.gather(
            *[_run_worker(tc) for tc in tool_calls], return_exceptions=True
        )

        result = {
            "research_notes": [],
            "timeline": [],
            "messages": [],
            "investigation_log": [],
        }
        new_candidates = []

        for tc, worker_output in zip(tool_calls, worker_outputs):
            topic = tc.get("args", {}).get("topic", "")
            if isinstance(worker_output, Exception):
                err_msg = f"Worker failed for topic '{topic}': {worker_output}"
                result["investigation_log"].append(err_msg)
                tool_call_id = tc.get("id")
                if tool_call_id:
                    result["messages"].append(
                        ToolMessage(tool_call_id=tool_call_id, content=err_msg)
                    )
                continue

            notes = worker_output.get("research_notes", "")
            if notes:
                result["research_notes"].append(notes)
            if worker_output.get("timeline"):
                result["timeline"].extend(worker_output["timeline"])
            if worker_output.get("conflict_candidates"):
                for candidate in worker_output["conflict_candidates"]:
                    if not candidate:
                        continue
                    candidate_id = candidate.get("candidate_id")
                    if candidate_id and candidate_id in processed_candidate_ids:
                        continue
                    key = _conflict_key(
                        candidate.get("topic"),
                        candidate.get("claims") or [],
                        candidate.get("source_ids") or [],
                    )
                    if key in resolved_keys:
                        continue
                    new_candidates.append(candidate)

            tool_call_id = tc.get("id")
            if tool_call_id:
                tm_content = notes if isinstance(notes, str) else str(notes)
                tm_content = tm_content or "Worker completed with no notes."
                result["messages"].append(
                    ToolMessage(tool_call_id=tool_call_id, content=tm_content)
                )

        # Drop empty fields to avoid accidental state churn
        if not result["research_notes"]:
            result.pop("research_notes")
        if not result["timeline"]:
            result.pop("timeline")
        if not result["messages"]:
            result.pop("messages")
        if not result["investigation_log"]:
            result.pop("investigation_log")

        if existing_candidates or new_candidates:
            merged_candidates = []
            seen = set()
            for candidate in list(existing_candidates) + list(new_candidates):
                if not candidate:
                    continue
                identity = _candidate_identity(candidate)
                if identity:
                    if identity in seen:
                        continue
                    seen.add(identity)
                merged_candidates.append(candidate)
            if len(merged_candidates) > MAX_CONFLICT_CANDIDATES:
                merged_candidates = merged_candidates[-MAX_CONFLICT_CANDIDATES:]
            if merged_candidates != existing_candidates:
                result["conflict_candidates"] = merged_candidates
        elif "conflict_candidates" in result:
            result.pop("conflict_candidates")

        return result
    except Exception as e:
        return {"investigation_log": [f"Worker failed: {str(e)}"]}

def build_graph_v2():
    """Compiles the DeepTrace V2 Graph."""
    workflow = StateGraph(GlobalState)
    
    # 1. Add Nodes
    workflow.add_node("clarify", clarify_node)
    workflow.add_node("supervisor", supervisor_node)
    
    # Worker Subgraph (Wrapped)
    workflow.add_node("worker", worker_node)
    
    # Debater Tool Node (Executes the tool logic)
    # ToolNode automatically executes the tool call in the last message
    # and returns a ToolMessage.
    workflow.add_node("debater", ToolNode([debater_tool]))
    workflow.add_node("thinking", ToolNode([think_tool]))
    workflow.add_node("debater_postprocess", debater_postprocess)
    workflow.add_node("timeline_merge", timeline_merge_node)
    workflow.add_node("finalizer", finalizer_node)
    workflow.add_node("archive", archive_run_node)

    # 2. Add Edges
    workflow.add_edge(START, "clarify")
    workflow.add_edge("clarify", "supervisor")
    
    # Conditional Edge from Supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "worker": "worker",
            "debater": "debater",
            "thinking": "thinking",
            "timeline_merge": "timeline_merge",
            "finalizer": "finalizer",
            "final_answer": END,
            "supervisor": "supervisor"  # Allow self-loop (for dedup/errors)
        }
    )
    
    # Loop back from nodes to Supervisor
    workflow.add_edge("worker", "supervisor")
    workflow.add_edge("timeline_merge", "finalizer")
    workflow.add_edge("finalizer", "archive")
    workflow.add_edge("debater", "debater_postprocess")
    workflow.add_edge("debater_postprocess", "supervisor")
    workflow.add_edge("thinking", "supervisor")
    workflow.add_edge("archive", END)
    
    # 3. Compile
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)

# Singleton
app_v2 = build_graph_v2()
