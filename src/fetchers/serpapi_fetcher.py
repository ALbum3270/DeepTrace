"""
SerpAPI Fetcher: 使用 SerpAPI 进行谷歌搜索。
"""
import asyncio
from typing import List, Optional
from serpapi import GoogleSearch

from ..config.settings import settings
from ..core.models.evidence import Evidence, EvidenceSource, EvidenceType
from .base import BaseFetcher


class SerpAPIFetcher(BaseFetcher):
    """基于 SerpAPI 的搜索 Fetcher"""
    
    def __init__(self):
        super().__init__()
        if not settings.serpapi_key:
            raise ValueError("SERPAPI_KEY is required for SerpAPIFetcher")
    
    async def fetch(self, query: str) -> List[Evidence]:
        """
        通过 SerpAPI 搜索并解析为 Evidence 列表。
        
        Args:
            query: 搜索关键词
            
        Returns:
            证据列表
        """
        params = {
            "api_key": settings.serpapi_key,
            "engine": settings.serpapi_engine,
            "q": query,
            "num": settings.serpapi_num_results,
            "hl": "zh-CN",  # 优先中文结果
            "gl": "cn",     # 地理位置中国
        }
        
        try:
            # 使用 run_in_executor 将同步 SerpAPI 调用转为异步
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: GoogleSearch(params).get_dict()
            )
            
            organic = result.get("organic_results", []) or []
            evidences: List[Evidence] = []
            
            for item in organic:
                ev = self._parse_result(item)
                if ev:
                    evidences.append(ev)
            
            print(f"[SerpAPIFetcher] Fetched {len(evidences)} results for query: {query}")
            return evidences
            
        except Exception as e:
            print(f"[ERROR] SerpAPI fetch failed: {e}")
            # 返回空列表而不是崩溃
            return []
    
    def _parse_result(self, item: dict) -> Optional[Evidence]:
        """
        将 SerpAPI 单条结果解析为 Evidence。
        
        Args:
            item: SerpAPI organic_result 项
            
        Returns:
            Evidence 实例或 None（无效）
        """
        link = item.get("link")
        snippet = item.get("snippet")
        title = item.get("title")
        
        # 基本字段校验
        if not link or not snippet:
            return None
        
        return Evidence(
            title=title or "",
            content=snippet,
            url=link,
            source=EvidenceSource.NEWS,  # 默认为 NEWS，后续可根据域名细分
            type=EvidenceType.ARTICLE,
            publish_time=None,  # SerpAPI 不一定提供，后续可抓取原文补充
            metadata={
                "serpapi_position": item.get("position"),
                "serpapi_source": "google",
                "serpapi_displayed_link": item.get("displayed_link"),
            },
        )
