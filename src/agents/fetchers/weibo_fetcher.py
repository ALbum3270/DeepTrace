from typing import List
from ...core.models.evidence import Evidence
from .base import BaseFetcher
from ...fetchers.serpapi_fetcher import SerpAPIFetcher

class WeiboFetcher(BaseFetcher):
    """
    微博平台 Fetcher (MVP: 基于 SerpAPI + site:weibo.com)
    """
    def __init__(self):
        self.serpapi = SerpAPIFetcher()

    async def fetch(self, query: str) -> List[Evidence]:
        # 构造 site:weibo.com 查询
        # 也可以包含 weibo.cn
        site_query = f"site:weibo.com OR site:weibo.cn {query}"
        
        print(f"[WeiboFetcher] Searching: {site_query}")
        evidences = await self.serpapi.fetch(site_query)
        
        # 标记平台来源
        for ev in evidences:
            ev.source_type = "social_media"
            ev.metadata["platform"] = "weibo"
            # 可以在这里做更多针对微博的 metadata 处理
            
        return evidences
