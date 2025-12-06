import os
from ..state import GraphState
from .fetch_node import run_fetch_logic
from ...fetchers.weibo.fetcher import WeiboFetcher
from ...fetchers.xhs.fetcher import XHSFetcher

# 实例化 Fetcher (单例)
weibo_backend = os.getenv("WEIBO_BACKEND", "serpapi")
weibo_fetcher = WeiboFetcher(backend=weibo_backend)

xhs_backend = os.getenv("XHS_BACKEND", "serpapi")
xhs_fetcher = XHSFetcher(backend=xhs_backend)

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
