"""
Fetcher 基础接口定义。
"""
from abc import ABC, abstractmethod
from typing import List
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
