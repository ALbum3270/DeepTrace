from typing import List, Protocol
from ...core.models.evidence import Evidence

class BaseFetcher(Protocol):
    """
    所有 Fetcher 的基类协议。
    """
    async def fetch(self, query: str) -> List[Evidence]:
        """
        执行搜索并返回证据列表。
        """
        ...
