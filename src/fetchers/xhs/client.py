import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlencode, urlparse, parse_qs
import time

from tenacity import retry, stop_after_attempt, wait_fixed

# Lazy imports
try:
    from xhshow import Xhshow
except ImportError:
    Xhshow = None

try:
    from playwright.async_api import BrowserContext, Page
except ImportError:
    BrowserContext = Any
    Page = Any

from ...infrastructure.proxy.pool import ProxyIpPool
from ...infrastructure.utils import crawler_util, time_util
from ...infrastructure.browser.manager import browser_manager

from .exception import DataFetchError, IPBlockError
from .field import SearchNoteType, SearchSortType
from .help import get_search_id, sign
from .extractor import XiaoHongShuExtractor

logger = logging.getLogger(__name__)

class XiaoHongShuClient:
    def __init__(
        self,
        timeout=10,
        proxy_pool: Optional[ProxyIpPool] = None,
        cookie_dict: Dict[str, str] = None,
    ):
        self.proxy_pool = proxy_pool
        self.timeout = timeout
        self.headers = {
            "User-Agent": crawler_util.get_user_agent(),
            "Content-Type": "application/json",
        }
        self._host = "https://edith.xiaohongshu.com"
        self._domain = "https://www.xiaohongshu.com"
        self.IP_ERROR_STR = "网络连接异常，请检查网络设置或重启试试"
        self.IP_ERROR_CODE = 300012
        self.cookie_dict = cookie_dict or {}
        self._extractor = XiaoHongShuExtractor()
        if Xhshow:
            self._xhshow_client = Xhshow()
        else:
            self._xhshow_client = None
            logger.warning("Xhshow library not found, XHS client will not work.")
        self.playwright_context: Optional[BrowserContext] = None
        self.playwright_page: Optional[Page] = None

    async def init_context(self):
        if not self.playwright_context:
            self.playwright_context = await browser_manager.get_context()
            self.playwright_page = await self.playwright_context.new_page()
            # Set cookies if we have them
            if self.cookie_dict:
                cookies = []
                for k, v in self.cookie_dict.items():
                    cookies.append({"name": k, "value": v, "domain": ".xiaohongshu.com", "path": "/"})
                await self.playwright_context.add_cookies(cookies)

    async def _pre_headers(self, url: str, data=None) -> Dict:
        a1_value = self.cookie_dict.get("a1", "")
        
        if data is None:
            parsed = urlparse(url)
            params = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query).items()}
            full_url = f"{self._host}{url}"
            if not self._xhshow_client:
                raise ImportError("Xhshow library not found")
            x_s = self._xhshow_client.sign_xs_get(uri=full_url, a1_value=a1_value, params=params)
        else:
            full_url = f"{self._host}{url}"
            x_s = self._xhshow_client.sign_xs_post(uri=full_url, a1_value=a1_value, payload=data)

        b1_value = ""
        try:
            if self.playwright_page:
                local_storage = await self.playwright_page.evaluate("() => window.localStorage")
                b1_value = local_storage.get("b1", "")
        except Exception as e:
            logger.warning(f"Failed to get b1 from localStorage: {e}")

        signs = sign(
            a1=a1_value,
            b1=b1_value,
            x_s=x_s,
            x_t=str(int(time.time() * 1000)),
        )

        headers = {
            "X-S": signs["x-s"],
            "X-T": signs["x-t"],
            "x-S-Common": signs["x-s-common"],
            "X-B3-Traceid": signs["x-b3-traceid"],
        }
        self.headers.update(headers)
        return self.headers

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def request(self, method, url, **kwargs) -> Union[str, Any]:
        return_response = kwargs.pop("return_response", False)
        
        # Proxy handling
        proxies = None
        if self.proxy_pool:
            try:
                proxy_info = await self.proxy_pool.get_proxy()
                if proxy_info:
                    if proxy_info.user and proxy_info.password:
                        proxies = f"http://{proxy_info.user}:{proxy_info.password}@{proxy_info.ip}:{proxy_info.port}"
                    else:
                        proxies = f"http://{proxy_info.ip}:{proxy_info.port}"
            except Exception:
                pass

        if isinstance(proxies, dict):
             proxies = proxies.get("http://") or proxies.get("https://")
             
        async with httpx.AsyncClient(proxy=proxies, verify=False) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)

        if response.status_code in [471, 461]:
            msg = f"Captcha triggered: {response.status_code}"
            logger.error(msg)
            raise Exception(msg)

        if return_response:
            return response.text
            
        try:
            data: Dict = response.json()
        except json.JSONDecodeError:
             logger.error(f"JSON decode error: {response.text[:100]}")
             raise DataFetchError("JSON decode error")

        if data.get("success"):
            return data.get("data", data.get("success", {}))
        elif data.get("code") == self.IP_ERROR_CODE:
            raise IPBlockError(self.IP_ERROR_STR)
        else:
            err_msg = data.get("msg", None) or f"{response.text}"
            raise DataFetchError(err_msg)

    async def get(self, uri: str, params=None) -> Dict:
        final_uri = uri
        if isinstance(params, dict):
            final_uri = f"{uri}?{urlencode(params)}"
        headers = await self._pre_headers(final_uri)
        return await self.request(
            method="GET", url=f"{self._host}{final_uri}", headers=headers
        )

    async def post(self, uri: str, data: dict, **kwargs) -> Dict:
        headers = await self._pre_headers(uri, data)
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return await self.request(
            method="POST",
            url=f"{self._host}{uri}",
            data=json_str,
            headers=headers,
            **kwargs,
        )

    async def get_note_by_keyword(
        self,
        keyword: str,
        search_id: str = None,
        page: int = 1,
        page_size: int = 20,
        sort: SearchSortType = SearchSortType.GENERAL,
        note_type: SearchNoteType = SearchNoteType.ALL,
    ) -> Dict:
        if not search_id:
            search_id = get_search_id()
            
        uri = "/api/sns/web/v1/search/notes"
        data = {
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "search_id": search_id,
            "sort": sort.value,
            "note_type": note_type.value,
        }
        return await self.post(uri, data)

    async def get_note_by_id_from_html(
        self,
        note_id: str,
        xsec_source: str = "",
        xsec_token: str = "",
    ) -> Optional[Dict]:
        url = (
            "https://www.xiaohongshu.com/explore/"
            + note_id
            + f"?xsec_token={xsec_token}&xsec_source={xsec_source}"
        )
        # For HTML request, we might not need API signing headers, but we need User-Agent
        html = await self.request(
            method="GET", url=url, return_response=True, headers={"User-Agent": self.headers["User-Agent"]}
        )
        return self._extractor.extract_note_detail_from_html(note_id, html)
