from typing import List
from ...core.models.evidence import Evidence
from .base import BaseFetcher
from ...fetchers.serpapi_fetcher import SerpAPIFetcher

class XHSFetcher(BaseFetcher):
    """
    小红书平台 Fetcher (MVP: 基于 SerpAPI + site:xiaohongshu.com)
    """
    def __init__(self):
        self.serpapi = SerpAPIFetcher()

    async def fetch(self, query: str) -> List[Evidence]:
        # 构造 site:xiaohongshu.com 查询
        site_query = f"site:xiaohongshu.com {query}"
        
        print(f"[XHSFetcher] Searching: {site_query}")
        evidences = await self.serpapi.fetch(site_query)
        
        # 标记平台来源
        for ev in evidences:
            ev.source_type = "social_media"
            ev.metadata["platform"] = "xhs"
            
        return evidences
