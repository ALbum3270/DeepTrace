from ..state import GraphState
from ...fetchers.mock_fetcher import MockFetcher
from ...config.settings import settings

# 根据配置动态选择 Fetcher
def _get_fetcher():
    """根据 FETCHER_MODE 配置选择合适的 Fetcher"""
    if settings.fetcher_mode == "mock":
        print("[INFO] Using MockFetcher (forced by FETCHER_MODE=mock)")
        return MockFetcher()
    
    elif settings.fetcher_mode == "serpapi":
        if not settings.serpapi_key:
            raise RuntimeError("FETCHER_MODE=serpapi but SERPAPI_KEY is empty")
        from ...fetchers.serpapi_fetcher import SerpAPIFetcher
        print("[INFO] Using SerpAPIFetcher (forced by FETCHER_MODE=serpapi)")
        return SerpAPIFetcher()
    
    else:  # auto mode
        if settings.serpapi_key:
            from ...fetchers.serpapi_fetcher import SerpAPIFetcher
            print("[INFO] Using SerpAPIFetcher (auto: SERPAPI_KEY detected)")
            return SerpAPIFetcher()
        else:
            print("[WARN] No SERPAPI_KEY, using MockFetcher (auto mode)")
            return MockFetcher()

# 实例化 fetcher（只执行一次）
fetcher = _get_fetcher()

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
