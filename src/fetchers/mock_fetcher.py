"""
Mock Fetcher：用于测试和 MVP 演示的假数据源。
"""
import asyncio
from datetime import datetime, timedelta
from typing import List
from ..core.models.evidence import Evidence, EvidenceSource, EvidenceType
from .base import BaseFetcher, FetchQuery


class MockFetcher(BaseFetcher):
    """
    返回预定义的假数据。
    """
    
    def __init__(self):
        # 预定义一些数据池
        self._data_pool = {
            "default": [
                Evidence(
                    content="Mock数据：关于该事件的一般性描述...",
                    source=EvidenceSource.NEWS,
                    type=EvidenceType.ARTICLE,
                    author="某新闻网",
                    publish_time=datetime.now() - timedelta(days=5)
                )
            ],
            "翻车": [
                Evidence(
                    content="避雷！XXX精华用了之后全脸泛红，客服还说是排毒，太无语了。",
                    source=EvidenceSource.XHS,
                    type=EvidenceType.POST,
                    author="美妆博主A",
                    publish_time=datetime.now() - timedelta(days=10),
                    metadata={"likes": 1200, "comments": 300}
                ),
                Evidence(
                    content="回复@美妆博主A：我也是！查了一下成分好像有致敏源。",
                    source=EvidenceSource.XHS,
                    type=EvidenceType.COMMENT,
                    author="路人B",
                    publish_time=datetime.now() - timedelta(days=9),
                    metadata={"likes": 50}
                ),
                Evidence(
                    content="XXX品牌方发布声明，称产品符合国标，建议敏感肌慎用。",
                    source=EvidenceSource.WEIBO,
                    type=EvidenceType.POST,
                    author="XXX官方",
                    publish_time=datetime.now() - timedelta(days=2),
                    metadata={"reposts": 500}
                )
            ]
        }

    async def fetch(self, query: FetchQuery) -> List[Evidence]:
        """
        模拟网络请求并返回数据。
        """
        # 模拟网络延迟
        await asyncio.sleep(0.5)
        
        results = []
        
        # 简单的关键词匹配逻辑
        if "翻车" in query.keywords or "过敏" in query.keywords or "投诉" in query.keywords:
            results.extend(self._data_pool["翻车"])
        else:
            results.extend(self._data_pool["default"])
            
        # 模拟 limit
        return results[:query.limit]
