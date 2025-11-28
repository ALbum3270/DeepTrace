"""
测试 Fetcher 模块
"""
import pytest
import asyncio
from src.fetchers.base import FetchQuery
from src.fetchers.mock_fetcher import MockFetcher
from src.core.models.evidence import EvidenceSource


class TestMockFetcher:
    """测试 MockFetcher"""
    
    @pytest.mark.asyncio
    async def test_fetch_default(self):
        """测试默认返回"""
        fetcher = MockFetcher()
        query = FetchQuery(keywords="测试")
        
        results = await fetcher.fetch(query)
        
        assert len(results) > 0
        assert results[0].source == EvidenceSource.NEWS
    
    @pytest.mark.asyncio
    async def test_fetch_specific_keyword(self):
        """测试特定关键词返回"""
        fetcher = MockFetcher()
        query = FetchQuery(keywords="产品翻车了")
        
        results = await fetcher.fetch(query)
        
        assert len(results) >= 3
        # 检查是否包含小红书来源
        has_xhs = any(r.source == EvidenceSource.XHS for r in results)
        assert has_xhs
        
    @pytest.mark.asyncio
    async def test_fetch_limit(self):
        """测试 limit 参数"""
        fetcher = MockFetcher()
        query = FetchQuery(keywords="翻车", limit=1)
        
        results = await fetcher.fetch(query)
        
        assert len(results) == 1
