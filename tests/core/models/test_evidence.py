"""
测试 Evidence 模型
"""
import pytest
from datetime import datetime
from src.core.models.evidence import Evidence, EvidenceSource, EvidenceType


class TestEvidence:
    """Evidence 模型测试"""
    
    def test_create_evidence_with_defaults(self):
        """测试使用默认值创建 Evidence"""
        evidence = Evidence(content="测试内容")
        
        assert evidence.id is not None
        assert evidence.content == "测试内容"
        assert evidence.type == EvidenceType.POST
        assert evidence.source == EvidenceSource.UNKNOWN
        assert evidence.url is None
        assert evidence.author is None
        assert evidence.publish_time is None
        assert evidence.created_at is not None
        assert isinstance(evidence.entities, list)
        assert len(evidence.entities) == 0
        assert isinstance(evidence.metadata, dict)
    
    def test_create_evidence_with_all_fields(self):
        """测试使用所有字段创建 Evidence"""
        pub_time = datetime(2023, 10, 1, 14, 30)
        
        evidence = Evidence(
            content="完整的证据内容",
            type=EvidenceType.COMMENT,
            source=EvidenceSource.XHS,
            url="https://example.com",
            author="测试用户",
            publish_time=pub_time,
            entities=["实体A", "实体B"],
            metadata={"likes": 100, "comments": 50}
        )
        
        assert evidence.content == "完整的证据内容"
        assert evidence.type == EvidenceType.COMMENT
        assert evidence.source == EvidenceSource.XHS
        assert evidence.url == "https://example.com"
        assert evidence.author == "测试用户"
        assert evidence.publish_time == pub_time
        assert len(evidence.entities) == 2
        assert evidence.metadata["likes"] == 100
    
    def test_to_text_basic(self):
        """测试 to_text 方法基本功能"""
        evidence = Evidence(
            content="这是一条测试内容",
            source=EvidenceSource.XHS,
            type=EvidenceType.POST,
            author="用户A",
            publish_time=datetime(2023, 10, 1, 14, 30)
        )
        
        text = evidence.to_text()
        
        assert "[来源: xhs]" in text
        assert "[类型: post]" in text
        assert "[时间: 2023-10-01 14:30]" in text
        assert "[作者: 用户A]" in text
        assert "这是一条测试内容" in text
    
    def test_to_text_truncation(self):
        """测试 to_text 方法的内容截断"""
        long_content = "A" * 600
        evidence = Evidence(content=long_content)
        
        text = evidence.to_text(max_length=100)
        
        assert "..." in text
        assert len(text) < len(long_content)
    
    def test_to_text_with_entities(self):
        """测试 to_text 包含实体信息"""
        evidence = Evidence(
            content="测试内容",
            entities=["品牌A", "产品B", "用户C"]
        )
        
        text = evidence.to_text()
        
        assert "关键实体:" in text
        assert "品牌A" in text
    
    def test_evidence_serialization(self):
        """测试 Evidence 序列化为 dict"""
        evidence = Evidence(
            content="测试",
            source=EvidenceSource.WEIBO,
            publish_time=datetime(2023, 10, 1, 12, 0)
        )
        
        data = evidence.model_dump()
        
        assert data["content"] == "测试"
        assert data["source"] == "weibo"
        assert isinstance(data["id"], str)


class TestEvidenceEnums:
    """测试 Evidence 相关的枚举"""
    
    def test_evidence_source_values(self):
        """测试 EvidenceSource 枚举值"""
        assert EvidenceSource.XHS.value == "xhs"
        assert EvidenceSource.WEIBO.value == "weibo"
        assert EvidenceSource.NEWS.value == "news"
        assert EvidenceSource.UNKNOWN.value == "unknown"
    
    def test_evidence_type_values(self):
        """测试 EvidenceType 枚举值"""
        assert EvidenceType.POST.value == "post"
        assert EvidenceType.COMMENT.value == "comment"
        assert EvidenceType.ARTICLE.value == "article"
        assert EvidenceType.OTHER.value == "other"
