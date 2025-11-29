from langgraph.graph import StateGraph, END

from .state import GraphState
from .nodes.fetch_node import fetch_node
from .nodes.extract_node import extract_events_node, extract_comments_node
from .nodes.build_node import build_node
from .nodes.triage_node import triage_node
from .nodes.planner_node import planner_node
from .nodes.supervisor_node import supervisor_node
from .nodes.platform_fetch_nodes import weibo_fetch_node, xhs_fetch_node
from ..core.models.strategy import SearchStrategy

async def mixed_entry_node(state: GraphState) -> GraphState:
    """Mixed Strategy Entry Node: Pass-through for fan-out."""
    return {"steps": ["mixed_entry: fan-out to all fetchers"]}

def route_from_supervisor(state: GraphState) -> str:
    """
    根据 Supervisor 的输出决定路由。
    """
    strategy = state.get("search_strategy", SearchStrategy.GENERIC)
    
    if strategy == SearchStrategy.WEIBO:
        return "weibo_fetch"
    elif strategy == SearchStrategy.XHS:
        return "xhs_fetch"
    elif strategy == SearchStrategy.MIXED:
        return "mixed_entry"
    else:
        return "fetch" # GENERIC or fallback

def should_continue(state: GraphState) -> str:
    """
    决定下一步操作：继续 fetch 还是结束。
    """
    plan = state.get("retrieval_plan")
    loop_step = state.get("loop_step", 0)
    max_loops = state.get("max_loops", 0)
    
    # 无 plan 或已 finish 或超出 loop 限制 -> 结束
    if not plan or plan.finish:
        return "end"
        
    if max_loops and loop_step >= max_loops:
        return "end"
        
    # 有 query 且 loop 还没超限 -> 再 fetch 一轮
    if plan.queries:
        # 这里需要根据当前的 strategy 决定回跳到哪里
        # 简化起见，Planner 生成的后续 Query 目前统一回跳到 Generic Fetch
        # 或者我们可以让 Planner 也输出 strategy? 
        # MVP: 后续循环统一走 Generic Fetch (因为 Planner 主要是补全信息)
        return "fetch"
        
    # 默认结束
    return "end"


def create_graph():
    """
    创建并编译 DeepTrace 事件链分析图。
    """
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("mixed_entry", mixed_entry_node)
    
    workflow.add_node("fetch", fetch_node)
    workflow.add_node("weibo_fetch", weibo_fetch_node)
    workflow.add_node("xhs_fetch", xhs_fetch_node)
    
    workflow.add_node("extract_events", extract_events_node)
    workflow.add_node("extract_comments", extract_comments_node)
    workflow.add_node("triage", triage_node)
    workflow.add_node("build", build_node)
    workflow.add_node("planner", planner_node)

    # 定义边
    workflow.set_entry_point("supervisor")
    
    # Supervisor 路由
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "fetch": "fetch",
            "weibo_fetch": "weibo_fetch",
            "xhs_fetch": "xhs_fetch",
            "mixed_entry": "mixed_entry"
        }
    )
    
    # Mixed Entry Fan-out
    workflow.add_edge("mixed_entry", "fetch")
    workflow.add_edge("mixed_entry", "weibo_fetch")
    workflow.add_edge("mixed_entry", "xhs_fetch")
    
    # Fetchers -> Extract (Parallel)
    # Generic Fetch
    workflow.add_edge("fetch", "extract_events")
    workflow.add_edge("fetch", "extract_comments")
    
    # Weibo Fetch
    workflow.add_edge("weibo_fetch", "extract_events")
    workflow.add_edge("weibo_fetch", "extract_comments")
    
    # XHS Fetch
    workflow.add_edge("xhs_fetch", "extract_events")
    workflow.add_edge("xhs_fetch", "extract_comments")
    
    # 汇聚
    workflow.add_edge("extract_events", "build")
    workflow.add_edge("extract_comments", "triage")
    workflow.add_edge("triage", "build")
    
    workflow.add_edge("build", "planner")
    
    # 条件边 (Planner Loop)
    workflow.add_conditional_edges(
        "planner",
        should_continue,
        {
            "fetch": "fetch", # 目前循环回 Generic
            "end": END
        }
    )

    return workflow.compile()
