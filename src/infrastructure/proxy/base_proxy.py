from abc import ABC, abstractmethod
from typing import List
from .types import IpInfoModel

class ProxyProvider(ABC):
    @abstractmethod
    async def get_proxy(self, num: int) -> List[IpInfoModel]:
        """
        获取 IP 的抽象方法，不同的 HTTP 代理商需要实现该方法
        :param num: 提取的 IP 数量
        :return:
        """
        raise NotImplementedError
