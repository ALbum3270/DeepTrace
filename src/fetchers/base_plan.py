"""
Fetcher 模块：负责从外部源获取数据。
包含基础接口定义和 Mock 实现。
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field
from ..core.models.evidence import Evidence


class FetchQuery(BaseModel):
    """抓取请求参数"""
    keywords: str = Field(..., description="搜索关键词")
    limit: int = Field(default=10, description="最大返回数量")
    platform: str = Field(default="all", description="目标平台 (xhs, weibo, news, all)")
    # 可扩展：时间范围等


class BaseFetcher(ABC):
    """Fetcher 基类接口"""
    
    @abstractmethod
    async def fetch(self, query: FetchQuery) -> List[Evidence]:
        """
        执行抓取。
        
        Args:
            query: 抓取参数
            
        Returns:
            Evidence 列表
        """
        pass


class MockFetcher(BaseFetcher):
    """
    Mock Fetcher：返回预定义的假数据，用于测试和 MVP 演示。
    """
    
    async def fetch(self, query: FetchQuery) -> List[Evidence]:
        # TODO: 根据 query 返回一些写死的 Evidence
        # 比如如果 query 包含 "翻车"，就返回几条负面笔记
        return []
