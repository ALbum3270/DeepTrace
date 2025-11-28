"""
测试 EventNode 和 OpenQuestion 模型
"""
import pytest
from datetime import datetime
from src.core.models.events import EventNode, EventStatus, OpenQuestion


class TestEventNode:
    """EventNode 模型测试"""
    
    def test_create_event_node_minimal(self):
        """测试使用最少字段创建 EventNode"""
        event = EventNode(
            title="测试事件",
            description="这是一个测试事件"
        )
        
        assert event.id is not None
        assert event.title == "测试事件"
        assert event.description == "这是一个测试事件"
        assert event.time is None
        assert event.status == EventStatus.INFERRED
        assert event.confidence == 0.5
        assert isinstance(event.actors, list)
        assert isinstance(event.tags, list)
        assert isinstance(event.evidence_ids, list)
    
    def test_create_event_node_full(self):
        """测试使用完整字段创建 EventNode"""
        event_time = datetime(2023, 10, 1, 14, 30)
        
        event = EventNode(
            time=event_time,
            title="负面反馈出现",
            description="用户发布负面评价",
            actors=["用户A", "品牌方"],
            tags=["origin", "negative"],
            status=EventStatus.CONFIRMED,
            confidence=0.9,
            evidence_ids=["ev1", "ev2"]
        )
        
        assert event.time == event_time
        assert event.title == "负面反馈出现"
        assert len(event.actors) == 2
        assert "origin" in event.tags
        assert event.status == EventStatus.CONFIRMED
        assert event.confidence == 0.9
        assert len(event.evidence_ids) == 2
    
    def test_confidence_validation(self):
        """测试置信度边界验证"""
        # 正常范围
        event1 = EventNode(title="测试", description="测试", confidence=0.0)
        assert event1.confidence == 0.0
        
        event2 = EventNode(title="测试", description="测试", confidence=1.0)
        assert event2.confidence == 1.0
        
        # 超出范围应该抛出错误
        with pytest.raises(Exception):
            EventNode(title="测试", description="测试", confidence=1.5)
        
        with pytest.raises(Exception):
            EventNode(title="测试", description="测试", confidence=-0.1)
    
    def test_event_node_sorting(self):
        """测试 EventNode 排序逻辑"""
        event1 = EventNode(
            title="事件1",
            description="描述",
            time=datetime(2023, 10, 1, 10, 0)
        )
        event2 = EventNode(
            title="事件2",
            description="描述",
            time=datetime(2023, 10, 1, 12, 0)
        )
        event3 = EventNode(
            title="事件3",
            description="描述",
            time=None  # 无时间
        )
        
        events = [event3, event2, event1]
        sorted_events = sorted(events)
        
        # 有时间的按时间排序，无时间的排在最后
        assert sorted_events[0] == event1
        assert sorted_events[1] == event2
        assert sorted_events[2] == event3
    
    def test_event_serialization(self):
        """测试 EventNode 序列化"""
        event = EventNode(
            title="测试",
            description="描述",
            time=datetime(2023, 10, 1, 10, 0),
            status=EventStatus.CONFIRMED
        )
        
        data = event.model_dump()
        
        assert data["title"] == "测试"
        assert data["status"] == "confirmed"
        assert isinstance(data["id"], str)


class TestOpenQuestion:
    """OpenQuestion 模型测试"""
    
    def test_create_open_question(self):
        """测试创建 OpenQuestion"""
        question = OpenQuestion(
            question="3月份是否有类似投诉？",
            context="评论中提到早在3月就有投诉",
            priority=0.8,
            related_event_ids=["event1"]
        )
        
        assert question.id is not None
        assert question.question == "3月份是否有类似投诉？"
        assert question.priority == 0.8
        assert len(question.related_event_ids) == 1
    
    def test_priority_validation(self):
        """测试优先级边界验证"""
        # 正常范围
        q1 = OpenQuestion(question="测试", priority=0.0)
        assert q1.priority == 0.0
        
        q2 = OpenQuestion(question="测试", priority=1.0)
        assert q2.priority == 1.0
        
        # 超出范围
        with pytest.raises(Exception):
            OpenQuestion(question="测试", priority=1.5)
    
    def test_open_question_repr(self):
        """测试 OpenQuestion 的字符串表示"""
        question = OpenQuestion(
            question="这是一个很长的问题，用来测试字符串截断功能" * 5,
            priority=0.7
        )
        
        repr_str = repr(question)
        
        assert "OpenQuestion" in repr_str
        assert "priority=0.70" in repr_str


class TestEventStatus:
    """测试 EventStatus 枚举"""
    
    def test_event_status_values(self):
        """测试 EventStatus 枚举值"""
        assert EventStatus.CONFIRMED.value == "confirmed"
        assert EventStatus.INFERRED.value == "inferred"
        assert EventStatus.HYPOTHESIS.value == "hypothesis"
