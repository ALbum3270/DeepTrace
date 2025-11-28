"""
测试 Comment 和 CommentScore 模型
"""
import pytest
from datetime import datetime
from src.core.models.comments import Comment, CommentScore


class TestComment:
    """Comment 模型测试"""
    
    def test_create_comment_minimal(self):
        """测试使用最少字段创建 Comment"""
        comment = Comment(
            content="这是一条评论",
            evidence_id="post-123"
        )
        
        assert comment.id is not None
        assert comment.content == "这是一条评论"
        assert comment.evidence_id == "post-123"
        assert comment.author is None
        assert comment.publish_time is None
        assert comment.parent_id is None
    
    def test_create_comment_full(self):
        """测试使用完整字段创建 Comment"""
        pub_time = datetime(2023, 10, 2, 9, 15)
        
        comment = Comment(
            content="回复评论",
            author="用户B",
            publish_time=pub_time,
            parent_id="comment-parent",
            evidence_id="post-123"
        )
        
        assert comment.content == "回复评论"
        assert comment.author == "用户B"
        assert comment.publish_time == pub_time
        assert comment.parent_id == "comment-parent"
    
    def test_comment_serialization(self):
        """测试 Comment 序列化"""
        comment = Comment(
            content="测试",
            evidence_id="post-1",
            publish_time=datetime(2023, 10, 1, 10, 0)
        )
        
        data = comment.model_dump()
        
        assert data["content"] == "测试"
        assert data["evidence_id"] == "post-1"
        assert isinstance(data["id"], str)


class TestCommentScore:
    """CommentScore 模型测试"""
    
    def test_create_comment_score(self):
        """测试创建 CommentScore"""
        score = CommentScore(
            comment_id="comment-123",
            novelty=0.8,
            evidence=0.6,
            contradiction=0.3,
            influence=0.5,
            coordination=0.7,
            tags=["new_entity", "cross_platform"],
            reason="提到了新的时间点和跨平台线索"
        )
        
        assert score.comment_id == "comment-123"
        assert score.novelty == 0.8
        assert score.evidence == 0.6
        assert score.total_score == 0.0  # 未计算时为0
        assert len(score.tags) == 2
        assert score.reason == "提到了新的时间点和跨平台线索"
    
    def test_score_validation(self):
        """测试分数边界验证"""
        # 正常范围
        score1 = CommentScore(comment_id="c1", novelty=0.0, evidence=0.0)
        assert score1.novelty == 0.0
        
        score2 = CommentScore(comment_id="c2", novelty=1.0, evidence=1.0)
        assert score2.evidence == 1.0
        
        # 超出范围
        with pytest.raises(Exception):
            CommentScore(comment_id="c3", novelty=1.5)
        
        with pytest.raises(Exception):
            CommentScore(comment_id="c4", evidence=-0.1)
    
    def test_calculate_total_default_weights(self):
        """测试使用默认权重计算总分"""
        score = CommentScore(
            comment_id="c1",
            novelty=0.8,
            evidence=0.6,
            contradiction=0.4,
            influence=0.5,
            coordination=0.3
        )
        
        total = score.calculate_total()
        
        # 默认权重：novelty=0.3, evidence=0.3, contradiction=0.2, influence=0.1, coordination=0.1
        expected = 0.8*0.3 + 0.6*0.3 + 0.4*0.2 + 0.5*0.1 + 0.3*0.1
        
        assert abs(total - expected) < 0.001
        assert score.total_score == total
        assert 0.0 <= total <= 1.0
    
    def test_calculate_total_custom_weights(self):
        """测试使用自定义权重计算总分"""
        score = CommentScore(
            comment_id="c1",
            novelty=1.0,
            evidence=0.0,
            contradiction=0.0,
            influence=0.0,
            coordination=0.0
        )
        
        # 只看 novelty，权重为1
        total = score.calculate_total(weights={
            "novelty": 1.0,
            "evidence": 0.0,
            "contradiction": 0.0,
            "influence": 0.0,
            "coordination": 0.0
        })
        
        assert abs(total - 1.0) < 0.001
    
    def test_calculate_total_boundary_clamping(self):
        """测试总分边界限制"""
        score = CommentScore(
            comment_id="c1",
            novelty=1.0,
            evidence=1.0,
            contradiction=1.0,
            influence=1.0,
            coordination=1.0
        )
        
        # 即使所有维度都是1.0，总分也应该被限制在 [0, 1]
        total = score.calculate_total()
        
        assert total <= 1.0
        assert total >= 0.0
    
    def test_comment_score_serialization(self):
        """测试 CommentScore 序列化"""
        score = CommentScore(
            comment_id="c1",
            novelty=0.8,
            evidence=0.6
        )
        score.calculate_total()
        
        data = score.model_dump()
        
        assert data["comment_id"] == "c1"
        assert data["novelty"] == 0.8
        assert data["total_score"] > 0
        assert isinstance(data["tags"], list)


class TestCommentScoreIntegration:
    """CommentScore 集成测试"""
    
    def test_realistic_scoring_scenario(self):
        """测试真实场景的评分"""
        # 场景：一条提到新线索的高价值评论
        score = CommentScore(
            comment_id="valuable-comment",
            novelty=0.9,      # 提到了之前没有的信息
            evidence=0.7,     # 包含具体细节
            contradiction=0.2, # 轻微质疑现有观点
            influence=0.6,    # 有一定影响力
            coordination=0.8, # 与其他评论呼应
            tags=["new_timeline", "evidence_link"],
            reason="提到早在3月就有类似投诉，并给出了微博链接"
        )
        
        total = score.calculate_total()
        
        # 这应该是一条高分评论
        assert total > 0.6
        assert len(score.tags) == 2
        
        # 场景：一条低价值的普通评论
        ordinary_score = CommentScore(
            comment_id="ordinary-comment",
            novelty=0.1,
            evidence=0.0,
            contradiction=0.0,
            influence=0.2,
            coordination=0.1,
            reason="只是简单表达赞同"
        )
        
        ordinary_total = ordinary_score.calculate_total()
        
        # 这应该是低分评论
        assert ordinary_total < 0.3
