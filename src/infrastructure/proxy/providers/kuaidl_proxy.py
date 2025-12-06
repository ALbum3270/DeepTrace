import os
import re
import logging
from typing import Dict, List
import httpx
from pydantic import BaseModel, Field
from ..base_proxy import ProxyProvider
from ..types import IpInfoModel, ProviderNameEnum

logger = logging.getLogger(__name__)

class KuaidailiProxyModel(BaseModel):
    ip: str = Field("ip")
    port: int = Field("端口")
    expire_ts: int = Field("过期时间")

def parse_kuaidaili_proxy(proxy_info: str) -> KuaidailiProxyModel:
    proxies: List[str] = proxy_info.split(":")
    if len(proxies) != 2:
        raise Exception("not invalid kuaidaili proxy info")

    pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5}),(\d+)'
    match = re.search(pattern, proxy_info)
    if not match or not match.groups():
        raise Exception("not match kuaidaili proxy info")

    return KuaidailiProxyModel(
        ip=match.groups()[0],
        port=int(match.groups()[1]),
        expire_ts=int(match.groups()[2])
    )

class KuaiDaiLiProxy(ProxyProvider):
    def __init__(self, kdl_user_name: str, kdl_user_pwd: str, kdl_secret_id: str, kdl_signature: str):
        self.kdl_user_name = kdl_user_name
        self.kdl_user_pwd = kdl_user_pwd
        self.api_base = "https://dps.kdlapi.com/"
        self.secret_id = kdl_secret_id
        self.signature = kdl_signature
        self.proxy_brand_name = ProviderNameEnum.KUAI_DAILI_PROVIDER.value
        self.params = {
            "secret_id": self.secret_id,
            "signature": self.signature,
            "pt": 1,
            "format": "json",
            "sep": 1,
            "f_et": 1,
        }

    async def get_proxy(self, num: int) -> List[IpInfoModel]:
        uri = "/api/getdps/"
        # 简化版：不使用 Redis 缓存，直接请求
        self.params.update({"num": num})

        ip_infos: List[IpInfoModel] = []
        async with httpx.AsyncClient() as client:
            response = await client.get(self.api_base + uri, params=self.params)

            if response.status_code != 200:
                logger.error(f"[KuaiDaiLiProxy.get_proxies] status code not 200: {response.text}")
                raise Exception("get ip error from proxy provider")

            ip_response: Dict = response.json()
            if ip_response.get("code") != 0:
                logger.error(f"[KuaiDaiLiProxy.get_proxies] code not 0: {ip_response.get('msg')}")
                raise Exception(f"get ip error: {ip_response.get('msg')}")

            proxy_list: List[str] = ip_response.get("data", {}).get("proxy_list")
            for proxy in proxy_list:
                try:
                    proxy_model = parse_kuaidaili_proxy(proxy)
                    ip_info_model = IpInfoModel(
                        ip=proxy_model.ip,
                        port=proxy_model.port,
                        user=self.kdl_user_name,
                        password=self.kdl_user_pwd,
                        expired_time_ts=proxy_model.expire_ts,
                    )
                    ip_infos.append(ip_info_model)
                except Exception as e:
                    logger.error(f"Parse proxy error: {e}")

        return ip_infos

def new_kuai_daili_proxy() -> KuaiDaiLiProxy:
    return KuaiDaiLiProxy(
        kdl_secret_id=os.getenv("DEEPTRACE_PROXY_KDL_SECRET_ID", ""),
        kdl_signature=os.getenv("DEEPTRACE_PROXY_KDL_SIGNATURE", ""),
        kdl_user_name=os.getenv("DEEPTRACE_PROXY_KDL_USER_NAME", ""),
        kdl_user_pwd=os.getenv("DEEPTRACE_PROXY_KDL_USER_PWD", ""),
    )
