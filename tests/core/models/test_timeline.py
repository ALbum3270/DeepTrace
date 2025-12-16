"""
测试 Timeline 模型
"""
from datetime import datetime
from src.core.models.timeline import Timeline
from src.core.models.events import EventNode, EventStatus, OpenQuestion


class TestTimeline:
    """Timeline 模型测试"""
    
    def test_create_empty_timeline(self):
        """测试创建空时间线"""
        timeline = Timeline()
        
        assert timeline.title == "事件时间线"
        assert timeline.summary == ""
        assert isinstance(timeline.events, list)
        assert len(timeline.events) == 0
        assert isinstance(timeline.open_questions, list)
    
    def test_create_timeline_with_metadata(self):
        """测试创建带元数据的时间线"""
        timeline = Timeline(
            title="XXX产品翻车事件",
            summary="关于XXX产品的负面舆情发展"
        )
        
        assert timeline.title == "XXX产品翻车事件"
        assert timeline.summary == "关于XXX产品的负面舆情发展"
    
    def test_add_event(self):
        """测试添加事件节点"""
        timeline = Timeline()
        
        event1 = EventNode(title="事件1", description="描述1")
        event2 = EventNode(title="事件2", description="描述2")
        
        timeline.add_event(event1)
        timeline.add_event(event2)
        
        assert len(timeline.events) == 2
        assert timeline.events[0] == event1
        assert timeline.events[1] == event2
    
    def test_sorted_events(self):
        """测试事件排序"""
        timeline = Timeline()
        
        event1 = EventNode(
            title="最早事件",
            description="描述",
            time=datetime(2023, 10, 1, 10, 0)
        )
        event2 = EventNode(
            title="中间事件",
            description="描述",
            time=datetime(2023, 10, 2, 10, 0)
        )
        event3 = EventNode(
            title="无时间事件",
            description="描述",
            time=None
        )
        
        # 乱序添加
        timeline.add_event(event2)
        timeline.add_event(event3)
        timeline.add_event(event1)
        
        sorted_events = timeline.sorted_events()
        
        assert sorted_events[0] == event1
        assert sorted_events[1] == event2
        assert sorted_events[2] == event3  # 无时间的排最后
    
    def test_to_markdown_empty(self):
        """测试空时间线的 Markdown 输出"""
        timeline = Timeline(
            title="测试时间线",
            summary="这是一个测试"
        )
        
        markdown = timeline.to_markdown()
        
        assert "# 测试时间线" in markdown
        assert "这是一个测试" in markdown
        assert "暂无事件节点" in markdown
    
    def test_to_markdown_with_events(self):
        """测试包含事件的 Markdown 输出"""
        timeline = Timeline(title="事件时间线")
        
        event1 = EventNode(
            title="首个负面反馈",
            description="用户A发布负面体验",
            time=datetime(2023, 10, 1, 14, 30),
            actors=["用户A", "品牌方"],
            status=EventStatus.CONFIRMED,
            confidence=0.9,
            evidence_ids=["ev1", "ev2"]
        )
        
        event2 = EventNode(
            title="未知时间事件",
            description="某个事件",
            time=None,
            status=EventStatus.HYPOTHESIS,
            confidence=0.4
        )
        
        timeline.add_event(event1)
        timeline.add_event(event2)
        
        markdown = timeline.to_markdown()
        
        # 检查标题
        assert "# 事件时间线" in markdown
        
        # 检查事件1
        assert "首个负面反馈" in markdown
        assert "2023-10-01 14:30" in markdown
        assert "用户A发布负面体验" in markdown
        assert "用户A, 品牌方" in markdown
        assert "confirmed" in markdown
        assert "0.90" in markdown
        assert "证据数量**: 2" in markdown
        
        # 检查事件2
        assert "未知时间事件" in markdown
        assert "时间未知" in markdown
        assert "hypothesis" in markdown
        assert "0.40" in markdown
    
    def test_to_markdown_with_open_questions(self):
        """测试包含未解决问题的 Markdown 输出"""
        timeline = Timeline()
        
        timeline.open_questions.append(
            OpenQuestion(
                question="3月份是否有投诉？",
                priority=0.8
            )
        )
        timeline.open_questions.append(
            OpenQuestion(
                question="品牌方何时回应？",
                priority=0.6
            )
        )
        
        markdown = timeline.to_markdown()
        
        assert "未解决的问题" in markdown
        assert "3月份是否有投诉？" in markdown
        assert "0.80" in markdown
        assert "品牌方何时回应？" in markdown
    
    def test_timeline_serialization(self):
        """测试 Timeline 序列化"""
        timeline = Timeline(
            title="测试",
            summary="摘要"
        )
        
        event = EventNode(title="事件", description="描述")
        timeline.add_event(event)
        
        data = timeline.model_dump()
        
        assert data["title"] == "测试"
        assert data["summary"] == "摘要"
        assert len(data["events"]) == 1
        assert isinstance(data["events"][0], dict)
