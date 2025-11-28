"""
测试 EvidenceStore
"""
import pytest
from src.core.evidence_store import EvidenceStore
from src.core.models.evidence import Evidence
from src.core.models.comments import Comment


class TestEvidenceStore:
    """EvidenceStore 测试"""
    
    @pytest.fixture
    def store(self):
        """每个测试前创建一个新的 store"""
        return EvidenceStore()
    
    def test_add_and_get_evidence(self, store):
        """测试添加和获取证据"""
        evidence = Evidence(content="测试证据")
        store.add_evidence(evidence)
        
        retrieved = store.get_evidence(evidence.id)
        assert retrieved is not None
        assert retrieved.id == evidence.id
        assert retrieved.content == "测试证据"
        
        # 获取不存在的证据
        assert store.get_evidence("non-existent") is None
    
    def test_list_evidence(self, store):
        """测试列出证据"""
        ev1 = Evidence(content="证据1")
        ev2 = Evidence(content="证据2")
        ev3 = Evidence(content="证据3")
        
        store.add_evidence(ev1)
        store.add_evidence(ev2)
        store.add_evidence(ev3)
        
        all_ev = store.list_evidence()
        assert len(all_ev) == 3
        
        # 测试分页
        paged = store.list_evidence(skip=1, limit=1)
        assert len(paged) == 1
        assert paged[0].content == "证据2"
    
    def test_add_and_get_comment(self, store):
        """测试添加和获取评论"""
        ev = Evidence(content="父证据")
        store.add_evidence(ev)
        
        comment = Comment(content="测试评论", evidence_id=ev.id)
        store.add_comment(comment)
        
        # 通过 ID 获取
        retrieved = store.get_comment(comment.id)
        assert retrieved is not None
        assert retrieved.content == "测试评论"
        
        # 通过 Evidence ID 获取
        comments = store.get_comments_by_evidence(ev.id)
        assert len(comments) == 1
        assert comments[0].id == comment.id
        
        # 获取不存在的评论
        assert store.get_comment("non-existent") is None
        assert len(store.get_comments_by_evidence("non-existent-ev")) == 0
    
    def test_clear(self, store):
        """测试清空存储"""
        store.add_evidence(Evidence(content="ev"))
        store.add_comment(Comment(content="cm", evidence_id="ev"))
        
        assert len(store.list_evidence()) == 1
        
        store.clear()
        
        assert len(store.list_evidence()) == 0
        assert store.get_evidence("ev") is None
