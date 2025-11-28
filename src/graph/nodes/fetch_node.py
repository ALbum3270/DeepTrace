from ..state import GraphState
from ...fetchers import MockFetcher

# 暂时直接实例化，后续可改为依赖注入
fetcher = MockFetcher()

async def fetch_node(state: GraphState) -> GraphState:
    """
    Fetch Node: 根据当前查询获取证据。
    """
    # 优先使用 current_query (Planner 生成的)，否则使用 initial_query (用户输入的)
    query = state.get("current_query") or state.get("initial_query")
    
    if not query:
        return {
            "steps": ["fetch: no query provided, skip"]
        }
        
    evidences = await fetcher.fetch(query)
    
    return {
        "evidences": evidences,
        "steps": [f"fetch: q='{query}', got {len(evidences)} evidences"]
    }
