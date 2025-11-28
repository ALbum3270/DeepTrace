"""
时间线模型：事件节点的有序集合。
"""
from typing import List, Optional
from pydantic import BaseModel, Field

from .events import EventNode, OpenQuestion


class Timeline(BaseModel):
    """时间线数据结构"""
    
    title: str = Field(default="事件时间线", description="时间线标题")
    summary: str = Field(default="", description="时间线摘要")
    events: List[EventNode] = Field(default_factory=list, description="事件节点列表")
    open_questions: List[OpenQuestion] = Field(default_factory=list, description="未解决的问题列表")
    
    def add_event(self, event: EventNode) -> None:
        """
        添加事件节点（简单追加，不做合并）。
        
        Args:
            event: 要添加的事件节点
        """
        self.events.append(event)
    
    def sorted_events(self) -> List[EventNode]:
        """
        返回按时间排序的事件列表（无时间的排在最后）。
        
        Returns:
            排序后的事件节点列表
        """
        return sorted(self.events)
    
    def to_markdown(self) -> str:
        """
        生成 Markdown 格式的时间线。
        
        Returns:
            Markdown 字符串
        """
        lines = []
        
        # 标题和摘要
        lines.append(f"# {self.title}\n")
        if self.summary:
            lines.append(f"{self.summary}\n")
        
        lines.append("---\n")
        
        # 事件节点
        sorted_events = self.sorted_events()
        if not sorted_events:
            lines.append("*暂无事件节点*\n")
        else:
            for idx, event in enumerate(sorted_events, 1):
                # 时间标记
                if event.time:
                    time_str = event.time.strftime("%Y-%m-%d %H:%M")
                    lines.append(f"## {idx}. [{time_str}] {event.title}\n")
                else:
                    lines.append(f"## {idx}. [时间未知] {event.title}\n")
                
                # 描述
                lines.append(f"{event.description}\n")
                
                # 参与者
                if event.actors:
                    lines.append(f"**参与者**: {', '.join(event.actors)}\n")
                
                # 状态和置信度
                lines.append(f"**状态**: {event.status.value} | **置信度**: {event.confidence:.2f}\n")
                
                # 证据数
                lines.append(f"**证据数量**: {len(event.evidence_ids)}\n")
                
                lines.append("\n")
        
        # 未解决问题
        if self.open_questions:
            lines.append("---\n")
            lines.append("## 未解决的问题\n\n")
            for idx, q in enumerate(self.open_questions, 1):
                lines.append(f"{idx}. {q.question} (优先级: {q.priority:.2f})\n")
        
        return "".join(lines)
