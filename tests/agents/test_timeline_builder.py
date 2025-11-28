"""
测试 Timeline Builder Agent
"""
import pytest
from datetime import datetime
from src.core.models.events import EventNode, EventStatus
from src.agents.timeline_builder import build_timeline

def test_build_timeline_sorted():
    # Create events out of order
    ev1 = EventNode(
        title="事件1",
        description="描述1",
        time=datetime(2023, 5, 20, 10, 0, 0),
        status=EventStatus.CONFIRMED,
        actors=["A"],
    )
    ev2 = EventNode(
        title="事件2",
        description="描述2",
        time=datetime(2022, 12, 1, 9, 30, 0),
        status=EventStatus.CONFIRMED,
        actors=["B"],
    )
    ev3 = EventNode(
        title="事件3",
        description="描述3",
        time=datetime(2023, 1, 15, 14, 45, 0),
        status=EventStatus.CONFIRMED,
        actors=["C"],
    )
    timeline = build_timeline([ev1, ev2, ev3])
    # Ensure events are sorted chronologically
    sorted_times = [e.time for e in timeline.sorted_events()]
    assert sorted_times == sorted(sorted_times)
    # Ensure original objects are returned (same ids)
    assert timeline.sorted_events()[0].title == "事件2"
    assert timeline.sorted_events()[1].title == "事件3"
    assert timeline.sorted_events()[2].title == "事件1"

def test_build_timeline_empty():
    timeline = build_timeline([])
    assert timeline.events == []
    assert timeline.open_questions == []
