import os
import logging
from typing import List, Literal

from ...core.models.evidence import Evidence
from ...fetchers.serpapi_fetcher import SerpAPIFetcher
from .client import XiaoHongShuClient
from ...infrastructure.proxy.pool import create_ip_pool

logger = logging.getLogger(__name__)

class XHSFetcher:
    """
    XHS Fetcher with backend switching.
    """
    def __init__(self, backend: Literal["serpapi", "mindspider"] = "serpapi"):
        self.backend = backend
        self.serpapi = None
        self.mindspider_client = None

    async def _ensure_mindspider_client(self):
        if not self.mindspider_client:
            pool = await create_ip_pool(ip_pool_count=3, enable_validate_ip=True)
            # Need to load cookies from env or file
            cookie_str = os.getenv("DEEPTRACE_XHS_COOKIES", "")
            cookie_dict = {}
            if cookie_str:
                from ...infrastructure.utils.crawler_util import convert_str_cookie_to_dict
                cookie_dict = convert_str_cookie_to_dict(cookie_str)
            
            self.mindspider_client = XiaoHongShuClient(proxy_pool=pool, cookie_dict=cookie_dict)
            await self.mindspider_client.init_context()

    async def fetch(self, query: str) -> List[Evidence]:
        if self.backend == "mindspider":
            return await self._search_mindspider(query)
        else:
            return await self._search_serpapi(query)

    async def _search_serpapi(self, query: str) -> List[Evidence]:
        if not self.serpapi:
            self.serpapi = SerpAPIFetcher()
        site_query = f"site:xiaohongshu.com {query}"
        logger.info(f"[XHSFetcher] Searching SerpAPI: {site_query}")
        evidences = await self.serpapi.fetch(site_query)
        for ev in evidences:
            ev.source_type = "social_media"
            ev.metadata["platform"] = "xhs"
        return evidences

    async def _search_mindspider(self, query: str) -> List[Evidence]:
        logger.info(f"[XHSFetcher] Searching MindSpider: {query}")
        
        try:
            await self._ensure_mindspider_client()
            data = await self.mindspider_client.get_note_by_keyword(query)
            items = data.get("items", [])
            
            evidences = []
            for item in items:
                note = item.get("note_card", {})
                if not note:
                    continue
                    
                evidence = Evidence(
                    url=f"https://www.xiaohongshu.com/explore/{note.get('id')}",
                    title=note.get("display_title", "") or note.get("title", ""),
                    content=note.get("desc", ""),
                    source_type="social_media",
                    metadata={
                        "platform": "xhs",
                        "author": note.get("user", {}).get("nickname"),
                        "likes": note.get("interact_info", {}).get("liked_count"),
                        "type": note.get("type"),
                        "id": note.get("id"),
                        "xsec_token": item.get("xsec_token")
                    }
                )
                evidences.append(evidence)
            return evidences
            
        except Exception as e:
            logger.error(f"[XHSFetcher] MindSpider search failed: {e}")
            return []
