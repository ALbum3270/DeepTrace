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

from ...fetchers.content_scraper import ContentScraper
import asyncio

# 实例化 fetcher（只执行一次）
fetcher = _get_fetcher()
scraper = ContentScraper(max_concurrent=3)

async def run_fetch_logic(state: GraphState, fetcher_instance) -> GraphState:
    """
    通用 Fetch 逻辑：使用指定 fetcher 获取证据，并进行深度抓取。
    """
    # 优先使用 current_query (Planner 生成的)，否则使用 initial_query (用户输入的)
    query = state.get("current_query") or state.get("initial_query")
    
    if not query:
        return {
            "steps": ["fetch: no query provided, skip"]
        }
        
    # 1. 基础搜索 (Snippet)
    evidences = await fetcher_instance.fetch(query)
    
    # 2. 深度抓取 (Full Content)
    # 只对前 5 条结果进行深度抓取，避免太慢
    top_k = 5
    deep_fetch_tasks = []
    target_evidences = evidences[:top_k]
    
    if target_evidences:
        print(f"[FetchNode] Deep fetching top {len(target_evidences)} results...")
        for ev in target_evidences:
            if ev.url:
                deep_fetch_tasks.append(scraper.scrape(ev.url))
            else:
                deep_fetch_tasks.append(asyncio.sleep(0)) # 占位
        
        # 并发执行抓取
        results = await asyncio.gather(*deep_fetch_tasks)
        
        # 回填结果
        success_count = 0
        for i, result in enumerate(results):
            evidence = target_evidences[i]
            if isinstance(result, dict):
                if result.get("main_text"):
                    evidence.full_content = result["main_text"]
                    evidence.content_source = "full"
                    evidence.fetch_status = "ok"
                    success_count += 1
                else:
                    # 抓取失败或无内容
                    evidence.fetch_status = "error" if result.get("error") else "empty"
                    # content_source 保持默认 "snippet"
                    
                # 如果有预留的评论 HTML，也可以在这里赋值
                # evidences[i].raw_comments_html = result.get("raw_comments_html")
        
        print(f"[FetchNode] Deep fetch completed. Success: {success_count}/{len(target_evidences)}")

    return {
        "evidences": evidences,
        "steps": [f"fetch: q='{query}', got {len(evidences)} evidences (deep fetched {min(len(evidences), top_k)})"]
    }

async def fetch_node(state: GraphState) -> GraphState:
    """
    Generic Fetch Node: 使用默认/配置的 fetcher。
    """
    return await run_fetch_logic(state, fetcher)
