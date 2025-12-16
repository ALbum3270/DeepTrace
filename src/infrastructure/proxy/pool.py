import os
import random
import logging
from typing import List, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from .base_proxy import ProxyProvider
from .types import IpInfoModel, ProviderNameEnum
from .providers.kuaidl_proxy import new_kuai_daili_proxy

logger = logging.getLogger(__name__)

class ProxyIpPool:
    def __init__(self, ip_pool_count: int, enable_validate_ip: bool, ip_provider: Optional[ProxyProvider]):
        self.valid_ip_url = "https://www.baidu.com" # Simple check
        self.ip_pool_count = ip_pool_count
        self.enable_validate_ip = enable_validate_ip
        self.proxy_list: List[IpInfoModel] = []
        self.ip_provider: Optional[ProxyProvider] = ip_provider

    async def load_proxies(self) -> None:
        if not self.ip_provider:
            return
        try:
            self.proxy_list = await self.ip_provider.get_proxy(self.ip_pool_count)
            logger.info(f"Loaded {len(self.proxy_list)} proxies")
        except Exception as e:
            logger.error(f"Failed to load proxies: {e}")

    async def _is_valid_proxy(self, proxy: IpInfoModel) -> bool:
        try:
            if proxy.user and proxy.password:
                proxy_url = f"http://{proxy.user}:{proxy.password}@{proxy.ip}:{proxy.port}"
            else:
                proxy_url = f"http://{proxy.ip}:{proxy.port}"
            
            async with httpx.AsyncClient(proxies=proxy_url, timeout=5.0) as client:
                response = await client.get(self.valid_ip_url)
            return response.status_code == 200
        except Exception:
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def get_proxy(self) -> Optional[IpInfoModel]:
        # Soft Close: If no provider, return None (direct connection)
        if not self.ip_provider:
            return None

        if len(self.proxy_list) == 0:
            await self._reload_proxies()

        if not self.proxy_list:
             # If reload failed, return None to allow fallback to direct
            logger.warning("No proxies available after reload, falling back to direct connection")
            return None

        proxy = random.choice(self.proxy_list)
        self.proxy_list.remove(proxy)
        
        if self.enable_validate_ip:
            if not await self._is_valid_proxy(proxy):
                logger.warning(f"Invalid proxy {proxy.ip}, retrying...")
                raise Exception("Current ip invalid")
        
        return proxy

    async def _reload_proxies(self):
        self.proxy_list = []
        await self.load_proxies()

async def create_ip_pool(ip_pool_count: int = 5, enable_validate_ip: bool = True) -> ProxyIpPool:
    provider_name = os.getenv("DEEPTRACE_PROXY_PROVIDER")
    provider = None
    
    if provider_name == ProviderNameEnum.KUAI_DAILI_PROVIDER.value:
        provider = new_kuai_daili_proxy()
        # Check if keys are actually present
        if not provider.secret_id:
             logger.warning("KuaiDaili config missing, disabling proxy.")
             provider = None
    
    pool = ProxyIpPool(
        ip_pool_count=ip_pool_count,
        enable_validate_ip=enable_validate_ip,
        ip_provider=provider,
    )
    
    if provider:
        await pool.load_proxies()
        
    return pool
