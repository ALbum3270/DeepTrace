"""
事件节点模型：代表时间线上的一件事。
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import uuid4
from pydantic import BaseModel, Field


class EventStatus(str, Enum):
    """事件节点状态"""
    CONFIRMED = "confirmed"  # 有充分证据确认
    INFERRED = "inferred"  # 基于证据推断
    HYPOTHESIS = "hypothesis"  # 假设性（证据不足）


class EventNode(BaseModel):
    """事件节点数据结构"""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    time: Optional[datetime] = Field(None, description="事件发生时间（可为空）")
    title: str = Field(..., description="简短标题，如'首个负面反馈出现'")
    source: Optional[str] = Field(None, description="消息来源（如：新华社、微博用户@XXX、内部文件）")
    description: str = Field(..., description="详细描述")
    actors: List[str] = Field(default_factory=list, description="参与主体列表")
    tags: List[str] = Field(default_factory=list, description="标签，如 origin/explosion/brand_response")
    status: EventStatus = EventStatus.INFERRED
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="置信度 (0.0 ~ 1.0)")
    evidence_ids: List[str] = Field(default_factory=list, description="关联的证据ID列表")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    def __lt__(self, other: "EventNode") -> bool:
        """用于排序：按时间升序，无时间的排在最后"""
        if self.time is None and other.time is None:
            return False
        if self.time is None:
            return False
        if other.time is None:
            return True
        return self.time < other.time


class OpenQuestion(BaseModel):
    """未解决的问题/缺口"""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    question: str = Field(..., description="问题描述")
    context: str = Field(default="", description="提出问题的上下文")
    priority: float = Field(default=0.5, ge=0.0, le=1.0, description="优先级")
    related_event_ids: List[str] = Field(default_factory=list, description="相关事件节点ID")
    
    def __repr__(self) -> str:
        return f"OpenQuestion(priority={self.priority:.2f}, question='{self.question[:50]}...')"
