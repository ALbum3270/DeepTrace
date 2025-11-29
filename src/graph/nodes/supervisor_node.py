from ..state import GraphState
from ...agents.supervisor import supervise_query
from ...core.models.strategy import SearchStrategy

async def supervisor_node(state: GraphState) -> GraphState:
    """
    Supervisor Node: 分析初始查询，决定检索策略。
    """
    initial_query = state.get("initial_query", "")
    
    if not initial_query:
        # Fallback
        return {
            "search_strategy": SearchStrategy.GENERIC,
            "platforms": ["generic"],
            "steps": ["supervisor: no query, fallback to GENERIC"]
        }
        
    output = await supervise_query(initial_query)
    
    return {
        "search_strategy": output.strategy,
        "platforms": output.platforms,
        "steps": [f"supervisor: strategy={output.strategy.value}, platforms={output.platforms}, reason='{output.reason}'"]
    }
