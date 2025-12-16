"""
Mock Fetcher：用于测试和 MVP 演示的假数据源。
"""
from datetime import datetime, timedelta
from typing import List
from ..core.models.evidence import Evidence, EvidenceSource, EvidenceType
from ..core.models.comments import Comment
from .base import BaseFetcher


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
                    metadata={"likes": 1200, "comments": 300},
                    comments=[
                        Comment(source_evidence_id="mock_ev_1", content="我也是！查了一下成分好像有致敏源。", author="路人B", publish_time=datetime.now() - timedelta(days=9)),
                        Comment(source_evidence_id="mock_ev_1", content="蹲一个后续，本来想买的。", author="路人C", publish_time=datetime.now() - timedelta(days=9)),
                        Comment(source_evidence_id="mock_ev_1", content="集美们，这个成分表第三位是水杨酸，敏感肌慎入啊！", author="成分党D", publish_time=datetime.now() - timedelta(days=8)), # 高价值评论
                        Comment(source_evidence_id="mock_ev_1", content="纯路人，感觉博主在黑。", author="黑粉E", publish_time=datetime.now() - timedelta(days=8)), # 噪音
                    ]
                ),
                Evidence(
                    content="XXX品牌方发布声明，称产品符合国标，建议敏感肌慎用。",
                    source=EvidenceSource.WEIBO,
                    type=EvidenceType.POST,
                    author="XXX官方",
                    publish_time=datetime.now() - timedelta(days=2),
                    metadata={"reposts": 500},
                    comments=[
                        Comment(source_evidence_id="mock_ev_2", content="支持国货！", author="粉丝F", publish_time=datetime.now() - timedelta(days=2)), # 噪音
                        Comment(source_evidence_id="mock_ev_2", content="符合国标不代表不致敏，希望能公开致敏测试报告。", author="理智粉G", publish_time=datetime.now() - timedelta(days=2)), # 高价值
                    ]
                )
            ]
        }

    async def fetch(self, query: str) -> List[Evidence]:
        """
        模拟抓取过程。
        
        Args:
            query: 搜索关键词
            
        Returns:
            Evidence 列表
        """
        print(f"[MockFetcher] Fetching for query: {query}")
        
        # 模拟网络延迟
        # await asyncio.sleep(0.5)
        
        results = []
        
        # 简单的关键词匹配逻辑
        if "翻车" in query or "过敏" in query or "投诉" in query:
            results.extend(self._data_pool["翻车"])
        else:
            results.extend(self._data_pool["default"])
            
        # 模拟 limit
        return results[:5]
