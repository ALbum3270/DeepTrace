from ..state import GraphState
from ...config.settings import settings, EVIDENCE_DEPTH_MODES

# 根据配置动态选择 Fetcher
def _get_fetcher():
    """根据 FETCHER_MODE 配置选择合适的 Fetcher"""
    if settings.fetcher_mode not in {"auto", "serpapi"}:
        raise RuntimeError(f"Unsupported FETCHER_MODE={settings.fetcher_mode}, expected auto/serpapi")

    if settings.serpapi_key:
        from ...fetchers.serpapi_fetcher import SerpAPIFetcher
        print("[INFO] Using SerpAPIFetcher (SERPAPI_KEY detected)")
        return SerpAPIFetcher()

    raise RuntimeError("No SERPAPI_KEY configured; mock/offline fetchers are disabled.")

from ...fetchers.content_scraper import ContentScraper
import asyncio

# 实例化 fetcher（只执行一次）
fetcher = _get_fetcher()
scraper = ContentScraper(max_concurrent=3)

async def run_fetch_logic(state: GraphState, fetcher_instance) -> GraphState:
    """
    通用 Fetch 逻辑：使用指定 fetcher 获取证据，并进行深度抓取。
    支持动态 evidence_depth 配置。
    """
    # 优先使用 current_query (Planner 生成的)，否则使用 initial_query (用户输入的)
    query = state.get("current_query") or state.get("initial_query")
    
    if not query:
        return {
            "steps": ["fetch: no query provided, skip"]
        }
    
    # 获取 evidence_depth 配置
    depth_mode = state.get("evidence_depth", "balanced")
    depth_config = EVIDENCE_DEPTH_MODES.get(depth_mode, EVIDENCE_DEPTH_MODES["balanced"])
    
    # 1. 基础搜索 (Snippet)
    evidences = await fetcher_instance.fetch(query)
    
    # 应用硬限制
    evidences = evidences[:min(len(evidences), settings.MAX_EVIDENCE_PER_QUERY)]
    
    # 2. 深度抓取 (Full Content)
    # 根据 depth_config 决定深度抓取数量
    top_k = min(depth_config.deep_fetch, len(evidences))
    deep_fetch_tasks = []
    target_evidences = evidences[:top_k]
    
    if target_evidences:
        print(f"[FetchNode] Deep fetching top {len(target_evidences)} results (mode: {depth_mode})...")
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
        "steps": [f"fetch: q='{query}', got {len(evidences)} evidences (deep fetched {top_k}, mode: {depth_mode})"]
    }

async def fetch_node(state: GraphState) -> GraphState:
    """
    Generic Fetch Node: 使用默认/配置的 fetcher。
    """
    return await run_fetch_logic(state, fetcher)

