import asyncio
import math
import os
import re
import logging
from typing import List, Literal, Dict

from ...core.models.evidence import Evidence
from ...fetchers.serpapi_fetcher import SerpAPIFetcher
from .client import WeiboClient, SearchType
from ...infrastructure.proxy.pool import create_ip_pool
from ...config.settings import settings

logger = logging.getLogger(__name__)

class WeiboFetcher:
    """
    Weibo Fetcher with backend switching.
    """
    def __init__(self, backend: Literal["serpapi", "mindspider"] = "serpapi"):
        self.backend = backend
        self.serpapi = None
        self.mindspider_client = None

    async def _ensure_mindspider_client(self):
        if not self.mindspider_client:
            pool = await create_ip_pool(ip_pool_count=3, enable_validate_ip=True)
            
            # Load cookies from env
            cookie_str = os.getenv("DEEPTRACE_WEIBO_COOKIES", "")
            cookie_dict = {}
            if cookie_str:
                from ...infrastructure.utils.crawler_util import convert_str_cookie_to_dict
                cookie_dict = convert_str_cookie_to_dict(cookie_str)
                
            self.mindspider_client = WeiboClient(proxy_pool=pool, cookie_dict=cookie_dict)

    async def fetch(self, query: str) -> List[Evidence]:
        if self.backend == "mindspider":
            return await self._search_mindspider(query)
        else:
            return await self._search_serpapi(query)

    async def _search_serpapi(self, query: str) -> List[Evidence]:
        if not self.serpapi:
            self.serpapi = SerpAPIFetcher()
        site_query = f"site:weibo.com OR site:weibo.cn {query}"
        logger.info(f"[WeiboFetcher] Searching SerpAPI: {site_query}")
        evidences = await self.serpapi.fetch(site_query)
        # Enforce global limit for SerpAPI
        evidences = evidences[:settings.MAX_SERPAPI_RESULTS]
        for ev in evidences:
            ev.source_type = "social_media"
            ev.metadata["platform"] = "weibo"
        return evidences

    def _parse_cards(self, cards: List[Dict]) -> List[Evidence]:
        """Parse raw API cards into Evidence objects."""
        evidences = []
        for card in cards:
            # card_type 9 is usually a blog post
            if card.get("card_type") == 9:
                mblog = card.get("mblog", {})
                if not mblog:
                    continue
                    
                text = mblog.get("text", "")
                # Clean HTML tags from text
                text = re.sub(r'<[^>]+>', '', text)
                
                url = mblog.get("scheme", "")
                if not url and mblog.get("id"):
                    url = f"https://m.weibo.cn/detail/{mblog['id']}"
                
                evidence = Evidence(
                    url=url,
                    title=text[:50] + "...",
                    content=text,
                    source_type="social_media",
                    metadata={
                        "platform": "weibo",
                        "author": mblog.get("user", {}).get("screen_name"),
                        "publish_time": mblog.get("created_at"),
                        "likes": mblog.get("attitudes_count", 0),
                        "comments": mblog.get("comments_count", 0),
                        "reposts": mblog.get("reposts_count", 0),
                        "id": mblog.get("id"),
                        "mid": mblog.get("mid")
                    }
                )
                evidences.append(evidence)
        return evidences

    def _calculate_score(self, ev: Evidence) -> float:
        """
        Calculate score based on engagement metrics.
        Formula: 0.6*log(likes+1) + 0.3*log(reposts+1) + 0.1*log(comments+1)
        """
        likes = ev.metadata.get("likes", 0) or 0
        reposts = ev.metadata.get("reposts", 0) or 0
        comments = ev.metadata.get("comments", 0) or 0
        
        score = (0.6 * math.log(likes + 1)) + \
                (0.3 * math.log(reposts + 1)) + \
                (0.1 * math.log(comments + 1))
        return score

    async def _search_mindspider(self, query: str) -> List[Evidence]:
        await self._ensure_mindspider_client()
        logger.info(f"[WeiboFetcher] Searching MindSpider: {query} (Mode: {settings.WEIBO_SEARCH_MODE})")
        
        try:
            # Parallel fetch: Popular + Realtime
            task_popular = self.mindspider_client.get_note_by_keyword(query, search_type=SearchType.POPULAR)
            task_realtime = self.mindspider_client.get_note_by_keyword(query, search_type=SearchType.REALTIME)
            
            results = await asyncio.gather(task_popular, task_realtime, return_exceptions=True)
            
            raw_popular = results[0] if not isinstance(results[0], Exception) else {}
            raw_realtime = results[1] if not isinstance(results[1], Exception) else {}
            
            if isinstance(results[0], Exception):
                logger.error(f"[WeiboFetcher] Popular search failed: {results[0]}")
            if isinstance(results[1], Exception):
                logger.error(f"[WeiboFetcher] Realtime search failed: {results[1]}")

            # Parse results
            ev_popular = self._parse_cards(raw_popular.get("cards", []))
            ev_realtime = self._parse_cards(raw_realtime.get("cards", []))
            
            # Deduplicate by mid
            seen_mids = set()
            unique_popular = []
            for ev in ev_popular:
                mid = ev.metadata.get("mid")
                if mid and mid not in seen_mids:
                    seen_mids.add(mid)
                    unique_popular.append(ev)
            
            unique_realtime = []
            for ev in ev_realtime:
                mid = ev.metadata.get("mid")
                if mid and mid not in seen_mids:
                    seen_mids.add(mid)
                    unique_realtime.append(ev)
            
            # Score Popular candidates
            # (Realtime candidates are selected by recency/order, so we keep them as is)
            for ev in unique_popular:
                ev.metadata["score"] = self._calculate_score(ev)
            
            # Sort Popular by score descending
            unique_popular.sort(key=lambda x: x.metadata["score"], reverse=True)
            
            # Mixing Logic based on Mode
            mode = settings.WEIBO_SEARCH_MODE
            if mode == "quick":
                target_popular = 3
                target_realtime = 1
            elif mode == "deep":
                target_popular = 8
                target_realtime = 5
            else: # balanced (default)
                target_popular = 5
                target_realtime = 3
                
            final_evidences = unique_popular[:target_popular] + unique_realtime[:target_realtime]
            
            # Enforce global hard limit
            final_evidences = final_evidences[:settings.MAX_WEIBO_POSTS_PER_QUERY]
            
            logger.info(f"[WeiboFetcher] Selected {len(final_evidences)} posts "
                        f"(Popular: {len(unique_popular[:target_popular])}, "
                        f"Realtime: {len(unique_realtime[:target_realtime])})")
            
            return final_evidences
            
        except Exception as e:
            logger.error(f"[WeiboFetcher] MindSpider search failed: {e}", exc_info=True)
            return []
