import asyncio
import json
import random
import re
import copy
import logging
from typing import Dict, List, Optional, Union
from urllib.parse import parse_qs, unquote, urlencode

import httpx

from ...infrastructure.proxy.pool import create_ip_pool, ProxyIpPool
from ...infrastructure.utils import crawler_util, time_util

logger = logging.getLogger(__name__)

class DataFetchError(Exception):
    pass

class SearchType:
    DEFAULT = "1"
    REALTIME = "61"
    POPULAR = "60"
    VIDEO = "64"

class WeiboClient:
    def __init__(
        self,
        timeout=10,
        proxy_pool: Optional[ProxyIpPool] = None,
        cookie_dict: Dict[str, str] = None,
    ):
        self.proxy_pool = proxy_pool
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
            "MWeibo-Pwa": "1",
            "Referer": "https://m.weibo.cn/",
            "Connection": "close",
            "Accept-Encoding": "gzip, deflate, br",
        }
        self._host = "https://m.weibo.cn"
        self.cookie_dict = cookie_dict or {}
        if self.cookie_dict:
             # Simple cookie string construction
             # Filter out 'SSOLoginState' which is known to cause 432 errors
             cookie_parts = []
             for k, v in self.cookie_dict.items():
                 if k == "SSOLoginState":
                     continue
                 cookie_parts.append(f"{k}={v}")
             self.headers["Cookie"] = "; ".join(cookie_parts)
             
             # Handle XSRF-TOKEN
             xsrf_token = self.cookie_dict.get("XSRF-TOKEN")
             if xsrf_token:
                 self.headers["x-xsrf-token"] = xsrf_token

    async def request(self, method, url, **kwargs) -> Union[httpx.Response, Dict]:
        # Rate limiting: Random delay between 1-3 seconds
        await asyncio.sleep(random.uniform(1, 3))
        
        enable_return_response = kwargs.pop("return_response", False)
        
        # Get proxy from pool
        proxy_info = None
        proxies = None
        
        # Try loading tunnel proxy first
        # Try loading tunnel proxy first
        from ...core.proxy import build_proxies_for_channel
        # Use Channel 1 (5-minute rotation) to maintain session stability
        tunnel_proxies = build_proxies_for_channel(ch=1)
        
        if tunnel_proxies:
            # httpx 0.28+ 'proxy' argument expects a string or Proxy object, not a dict.
            # Since our tunnel config usually has same proxy for http/https, we pick one.
            if isinstance(tunnel_proxies, dict):
                proxies = tunnel_proxies.get("http://") or tunnel_proxies.get("https://")
            else:
                proxies = tunnel_proxies
            logger.info(f"[WeiboClient] Using Tunnel Proxy: {proxies}")
        elif self.proxy_pool:
            try:
                proxy_info = await self.proxy_pool.get_proxy()
                if proxy_info:
                    if proxy_info.user and proxy_info.password:
                        proxies = f"http://{proxy_info.user}:{proxy_info.password}@{proxy_info.ip}:{proxy_info.port}"
                    else:
                        proxies = f"http://{proxy_info.ip}:{proxy_info.port}"
                    logger.info(f"[WeiboClient] Using Pool Proxy: {proxies}")
            except Exception as e:
                logger.warning(f"Failed to get proxy: {e}")

        headers = kwargs.pop("headers", self.headers)
        async with httpx.AsyncClient(proxy=proxies, verify=False) as client:
            try:
                response = await client.request(method, url, timeout=self.timeout, headers=headers, **kwargs)
            except Exception as e:
                logger.error(f"Request failed: {e}")
                raise DataFetchError(f"Request failed: {e}")

        if enable_return_response:
            return response

        if response.status_code != 200:
            logger.error(f"[WeiboClient] Non-200 response: status={response.status_code}")
            logger.error(f"[WeiboClient] Body Preview: {response.text[:1000]}")
            # Raise exception to stop processing, but now we have logs
            raise DataFetchError(f"HTTP {response.status_code}: {response.text[:200]}")

        try:
            data: Dict = response.json()
        except json.JSONDecodeError:
             logger.error(f"[WeiboClient] JSON decode error. Status: {response.status_code}")
             logger.error(f"[WeiboClient] Body Preview: {response.text[:1000]}")
             raise DataFetchError(f"JSON decode error. Status: {response.status_code}")

        ok_code = data.get("ok")
        if ok_code == 0:
            logger.error(f"[WeiboClient.request] request {method}:{url} err, res:{data}")
            raise DataFetchError(data.get("msg", "response error"))
        elif ok_code != 1:
             # Some APIs return different structures, handle gracefully or raise
            logger.warning(f"[WeiboClient.request] request {method}:{url} warning, res:{data}")
            # raise DataFetchError(data.get("msg", "unknown error"))
            return data # Return data anyway for some endpoints
        else:
            return data.get("data", {})

    async def get(self, uri: str, params=None, headers=None, **kwargs) -> Union[httpx.Response, Dict]:
        final_uri = uri
        if isinstance(params, dict):
            final_uri = (f"{uri}?{urlencode(params)}")

        if headers is None:
            headers = self.headers
        return await self.request(method="GET", url=f"{self._host}{final_uri}", headers=headers, **kwargs)

    async def get_note_by_keyword(
        self,
        keyword: str,
        page: int = 1,
        search_type: str = SearchType.DEFAULT,
    ) -> Dict:
        uri = "/api/container/getIndex"
        containerid = f"100103type={search_type}&q={keyword}"
        params = {
            "containerid": containerid,
            "page_type": "searchall",
            "page": page,
        }
        return await self.get(uri, params)

    async def get_note_comments(self, mid_id: str, max_id: int, max_id_type: int = 0) -> Dict:
        uri = "/comments/hotflow"
        params = {
            "id": mid_id,
            "mid": mid_id,
            "max_id_type": max_id_type,
        }
        if max_id > 0:
            params.update({"max_id": max_id})
        referer_url = f"https://m.weibo.cn/detail/{mid_id}"
        headers = copy.copy(self.headers)
        headers["Referer"] = referer_url

        return await self.get(uri, params, headers=headers)

    async def get_note_info_by_id(self, note_id: str) -> Dict:
        url = f"{self._host}/detail/{note_id}"
        # For detail page, we need return_response=True to parse HTML
        response = await self.request("GET", url, return_response=True)
        if response.status_code != 200:
            raise DataFetchError(f"get weibo detail err: {response.text}")
        
        match = re.search(r'var \$render_data = (\[.*?\])\[0\]', response.text, re.DOTALL)
        if match:
            render_data_json = match.group(1)
            render_data_dict = json.loads(render_data_json)
            note_detail = render_data_dict[0].get("status")
            note_item = {"mblog": note_detail}
            return note_item
        else:
            logger.info(f"[WeiboClient.get_note_info_by_id] 未找到$render_data的值")
            return dict()

    async def fetch_comments_api(self, mid_id: str, max_pages: int = 1, max_comments: int = 20) -> List[Dict]:
        """
        Iteratively fetch comments for a post using the API.
        """
        all_comments = []
        max_id = 0
        max_id_type = 0
        
        for page in range(max_pages):
            if len(all_comments) >= max_comments:
                break
                
            try:
                logger.info(f"[WeiboClient] Fetching comments for {mid_id}, page {page+1}...")
                res = await self.get_note_comments(mid_id, max_id, max_id_type)
                
                # Handle unwrapped data (success) vs wrapped data
                data_block = None
                if isinstance(res, dict) and "ok" not in res:
                    data_block = res
                elif res.get("ok") == 1:
                    data_block = res.get("data", {})
                
                if not data_block:
                    logger.warning(f"[WeiboClient] Comment fetch failed/empty: {res}")
                    break
                    
                comments = data_block.get("data", [])
                if not comments:
                    logger.info("[WeiboClient] No more comments found.")
                    break
                    
                all_comments.extend(comments)
                
                max_id = data_block.get("max_id", 0)
                max_id_type = data_block.get("max_id_type", 0)
                
                if max_id == 0:
                    logger.info("[WeiboClient] Reached last page.")
                    break
                    
                # Polite delay between pages
                await asyncio.sleep(random.uniform(1, 2))
                
            except Exception as e:
                logger.error(f"[WeiboClient] Error fetching comments page {page}: {e}")
                break
                
        return all_comments[:max_comments]
