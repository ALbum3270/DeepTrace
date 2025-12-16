"""
简单的测试脚本，验证核心模型是否正确工作。

运行：python -m src.core.models.test_models
"""
from datetime import datetime
from src.core.models import (
    Evidence, EvidenceSource, EvidenceType,
    EventNode, EventStatus,
    Timeline,
    Comment, CommentScore
)


def test_evidence():
    """测试 Evidence 模型"""
    print("=" * 50)
    print("测试 Evidence 模型")
    print("=" * 50)
    
    evidence = Evidence(
        type=EvidenceType.POST,
        content="这款产品用了三天就坏了，客服也不回复，太失望了！",
        source=EvidenceSource.XHS,
        author="用户A",
        publish_time=datetime(2023, 10, 1, 14, 30),
        entities=["产品", "客服"]
    )
    
    print(f"Evidence ID: {evidence.id}")
    print(f"类型: {evidence.type.value}")
    print(f"来源: {evidence.source.value}")
    print("\n摘要输出:")
    print(evidence.to_text(max_length=100))
    print()


def test_event_node():
    """测试 EventNode 模型"""
    print("=" * 50)
    print("测试 EventNode 模型")
    print("=" * 50)
    
    event = EventNode(
        time=datetime(2023, 10, 1, 14, 30),
        title="首个负面反馈出现",
        description="用户A在小红书发布负面使用体验，提到产品质量问题和客服不回复。",
        actors=["用户A", "品牌客服"],
        tags=["origin", "product_issue"],
        status=EventStatus.CONFIRMED,
        confidence=0.85,
        evidence_ids=["evidence-123"]
    )
    
    print(f"Event ID: {event.id}")
    print(f"标题: {event.title}")
    print(f"状态: {event.status.value}")
    print(f"置信度: {event.confidence}")
    print(f"参与者: {', '.join(event.actors)}")
    print()


def test_timeline():
    """测试 Timeline 模型"""
    print("=" * 50)
    print("测试 Timeline 模型")
    print("=" * 50)
    
    timeline = Timeline(
        title="XXX 产品翻车事件时间线",
        summary="关于 XXX 产品在小红书上的负面舆情发展过程。"
    )
    
    # 添加事件
    event1 = EventNode(
        time=datetime(2023, 10, 1, 14, 30),
        title="首个负面反馈",
        description="用户A发布负面体验",
        status=EventStatus.CONFIRMED,
        confidence=0.9
    )
    
    event2 = EventNode(
        time=datetime(2023, 10, 3, 10, 0),
        title="舆论扩散",
        description="多名用户跟进表示遇到类似问题",
        status=EventStatus.CONFIRMED,
        confidence=0.8
    )
    
    event3 = EventNode(
        time=None,
        title="待确认事件",
        description="某个时间点可能发生的事情",
        status=EventStatus.HYPOTHESIS,
        confidence=0.4
    )
    
    timeline.add_event(event1)
    timeline.add_event(event3)  # 故意乱序
    timeline.add_event(event2)
    
    print(f"时间线标题: {timeline.title}")
    print(f"事件数量: {len(timeline.events)}")
    print("\n排序后的事件:")
    for idx, event in enumerate(timeline.sorted_events(), 1):
        time_str = event.time.strftime("%Y-%m-%d") if event.time else "未知"
        print(f"  {idx}. [{time_str}] {event.title} (置信度: {event.confidence})")
    
    print("\n生成 Markdown:")
    print(timeline.to_markdown())


def test_comment():
    """测试 Comment 和 CommentScore 模型"""
    print("=" * 50)
    print("测试 Comment 和 CommentScore 模型")
    print("=" * 50)
    
    comment = Comment(
        content="我也遇到了！而且早在今年3月就有人在微博投诉过，品牌方根本不管。",
        author="用户B",
        publish_time=datetime(2023, 10, 2, 9, 15),
        evidence_id="post-123"
    )
    
    print(f"Comment ID: {comment.id}")
    print(f"内容: {comment.content}")
    
    # 打分
    score = CommentScore(
        comment_id=comment.id,
        novelty=0.8,  # 提到了"3月就有投诉"
        evidence=0.6,  # 提到了微博
        contradiction=0.3,
        influence=0.5,
        coordination=0.7,
        tags=["new_timeline", "cross_platform"],
        reason="提到了新的时间点（3月）和跨平台线索（微博）"
    )
    
    total = score.calculate_total()
    print("\n评分:")
    print(f"  新颖性: {score.novelty}")
    print(f"  证据性: {score.evidence}")
    print(f"  综合得分: {total:.2f}")
    print(f"  理由: {score.reason}")
    print()


if __name__ == "__main__":
    test_evidence()
    test_event_node()
    test_timeline()
    test_comment()
    
    print("=" * 50)
    print("所有测试完成！✅")
    print("=" * 50)
