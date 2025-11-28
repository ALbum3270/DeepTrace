from ..state import GraphState
from ...agents.timeline_builder import build_timeline

async def build_node(state: GraphState) -> GraphState:
    """
    Build Node: 构建时间线。
    """
    events = state.get("events", [])
    
    # 调用 Timeline Builder Agent
    timeline = build_timeline(events)
    
    return {
        "timeline": timeline,
        "steps": [f"build: timeline built with {len(events)} events"]
    }
