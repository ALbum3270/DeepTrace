"""
证据模型：代表一条帖子、评论或新闻。
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from uuid import uuid4
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .comments import Comment


class EvidenceSource(str, Enum):
    """证据来源平台"""
    XHS = "xhs"  # 小红书
    WEIBO = "weibo"  # 微博
    NEWS = "news"  # 新闻
    UNKNOWN = "unknown"


class EvidenceType(str, Enum):
    """证据类型"""
    POST = "post"  # 帖子/笔记
    COMMENT = "comment"  # 评论
    ARTICLE = "article"  # 文章/新闻
    OTHER = "other"


class Evidence(BaseModel):
    """证据数据结构"""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: Optional[str] = Field(None, description="标题（用于搜索结果）")
    type: EvidenceType = EvidenceType.POST
    content: str = Field(..., description="证据正文内容")
    source: EvidenceSource = EvidenceSource.UNKNOWN
    url: Optional[str] = Field(None, description="原始链接")
    author: Optional[str] = Field(None, description="作者/发布者")
    publish_time: Optional[datetime] = Field(None, description="平台发布时间")
    created_at: datetime = Field(default_factory=datetime.now, description="证据进入系统的时间")
    
    # 扩展字段
    entities: List[str] = Field(default_factory=list, description="NER 识别的实体缓存")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="平台特有字段（点赞数、评论数等）")
    comments: List["Comment"] = Field(default_factory=list, description="关联的评论列表")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    def to_text(self, max_length: int = 500) -> str:
        """
        生成用于 LLM 输入的文本摘要。
        
        Args:
            max_length: 内容截断长度
            
        Returns:
            格式化的文本摘要
        """
        parts = []
        
        # 来源
        parts.append(f"[来源: {self.source.value}]")
        
        # 类型
        parts.append(f"[类型: {self.type.value}]")
        
        # 发布时间
        if self.publish_time:
            time_str = self.publish_time.strftime("%Y-%m-%d %H:%M")
            parts.append(f"[时间: {time_str}]")
        
        # 作者
        if self.author:
            parts.append(f"[作者: {self.author}]")
        
        # 内容（截断）
        content = self.content[:max_length]
        if len(self.content) > max_length:
            content += "..."
        
        parts.append(f"\n内容: {content}")
        
        # 实体（如果有）
        if self.entities:
            parts.append(f"\n关键实体: {', '.join(self.entities[:5])}")
        
        return " ".join(parts)
