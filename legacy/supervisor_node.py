from ..state import GraphState
from ...agents.supervisor import supervise_query
from ...core.models.strategy import SearchStrategy

async def supervisor_node(state: GraphState) -> GraphState:
    """
    Supervisor Node: 分析初始查询，决定检索策略和抓取深度。
    """
    initial_query = state.get("initial_query", "")
    
    # Check if strategy is manually set (e.g. for testing)
    current_strategy = state.get("search_strategy")
    current_depth = state.get("evidence_depth")
    if current_strategy and current_strategy != SearchStrategy.GENERIC:
        return {
            "steps": [f"supervisor: skip (strategy manually set to {current_strategy}, depth={current_depth or 'balanced'})"]
        }
    
    if not initial_query:
        # Fallback
        return {
            "search_strategy": SearchStrategy.GENERIC,
            "platforms": ["generic"],
            "evidence_depth": "balanced",
            "steps": ["supervisor: no query, fallback to GENERIC"]
        }
        
    output = await supervise_query(initial_query)
    
    # If depth was manually set, keep it; otherwise use AI decision
    final_depth = current_depth or output.evidence_depth
    
    return {
        "search_strategy": output.strategy,
        "platforms": output.platforms,
        "weibo_comment_depth": output.weibo_comment_depth,
        "evidence_depth": final_depth,
        "steps": [f"supervisor: strategy={output.strategy.value}, depth={final_depth}, platforms={output.platforms}"]
    }

