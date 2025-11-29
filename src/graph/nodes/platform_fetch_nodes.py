from ..state import GraphState
from .fetch_node import run_fetch_logic
from ...agents.fetchers.weibo_fetcher import WeiboFetcher
from ...agents.fetchers.xhs_fetcher import XHSFetcher

# 实例化 Fetcher (单例)
weibo_fetcher = WeiboFetcher()
xhs_fetcher = XHSFetcher()

async def weibo_fetch_node(state: GraphState) -> GraphState:
    """
    Weibo Fetch Node: 使用 WeiboFetcher 获取证据。
    """
    return await run_fetch_logic(state, weibo_fetcher)

async def xhs_fetch_node(state: GraphState) -> GraphState:
    """
    XHS Fetch Node: 使用 XHSFetcher 获取证据。
    """
    return await run_fetch_logic(state, xhs_fetcher)
