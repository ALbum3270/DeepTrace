from langgraph.graph import StateGraph, END

from .state import GraphState
from .nodes.fetch_node import fetch_node
from .nodes.extract_node import extract_node
from .nodes.build_node import build_node
from .nodes.triage_node import triage_node
from .nodes.planner_node import planner_node


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
        return "fetch"
        
    # 默认结束
    return "end"


def create_graph():
    """
    创建并编译 DeepTrace 事件链分析图。
    """
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("fetch", fetch_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("triage", triage_node)
    workflow.add_node("build", build_node)
    workflow.add_node("planner", planner_node)

    # 定义边
    workflow.set_entry_point("fetch")
    workflow.add_edge("fetch", "extract")
    workflow.add_edge("extract", "triage")
    workflow.add_edge("triage", "build")
    workflow.add_edge("build", "planner")
    
    # 条件边
    workflow.add_conditional_edges(
        "planner",
        should_continue,
        {
            "fetch": "fetch",
            "end": END
        }
    )

    return workflow.compile()
