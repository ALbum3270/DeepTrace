"""
Evidence Store: 负责管理证据和评论的存储与检索（内存版）。
"""
from typing import Dict, List, Optional
from collections import defaultdict
from .models.evidence import Evidence
from .models.comments import Comment


class EvidenceStore:
    """
    基于内存的证据存储。
    
    Attributes:
        _evidence (Dict[str, Evidence]): 存储证据，Key为证据ID
        _comments (Dict[str, Comment]): 存储评论，Key为评论ID
        _comments_by_evidence (Dict[str, List[str]]): 索引，EvidenceID -> CommentID列表
    """
    
    def __init__(self):
        self._evidence: Dict[str, Evidence] = {}
        self._comments: Dict[str, Comment] = {}
        self._comments_by_evidence: Dict[str, List[str]] = defaultdict(list)
    
    def add_evidence(self, evidence: Evidence) -> None:
        """
        添加一条证据。
        
        Args:
            evidence: Evidence 对象
        """
        self._evidence[evidence.id] = evidence
    
    def get_evidence(self, evidence_id: str) -> Optional[Evidence]:
        """
        根据 ID 获取证据。
        
        Args:
            evidence_id: 证据 ID
            
        Returns:
            Evidence 对象，如果不存在则返回 None
        """
        return self._evidence.get(evidence_id)
    
    def list_evidence(self, skip: int = 0, limit: int = 100) -> List[Evidence]:
        """
        列出所有证据（支持分页）。
        
        Args:
            skip: 跳过前 N 条
            limit: 返回最多 N 条
            
        Returns:
            Evidence 列表
        """
        all_evidence = list(self._evidence.values())
        # 按创建时间倒序排列（后进先出），或者按需求调整
        # 这里简单按插入顺序（Python 3.7+ dict有序）
        return all_evidence[skip : skip + limit]
    
    def add_comment(self, comment: Comment) -> None:
        """
        添加一条评论。
        
        Args:
            comment: Comment 对象
        """
        self._comments[comment.id] = comment
        self._comments_by_evidence[comment.evidence_id].append(comment.id)
    
    def get_comment(self, comment_id: str) -> Optional[Comment]:
        """
        根据 ID 获取评论。
        
        Args:
            comment_id: 评论 ID
            
        Returns:
            Comment 对象，如果不存在则返回 None
        """
        return self._comments.get(comment_id)
    
    def get_comments_by_evidence(self, evidence_id: str) -> List[Comment]:
        """
        获取指定证据下的所有评论。
        
        Args:
            evidence_id: 证据 ID
            
        Returns:
            Comment 列表
        """
        comment_ids = self._comments_by_evidence.get(evidence_id, [])
        comments = []
        for cid in comment_ids:
            comment = self._comments.get(cid)
            if comment:
                comments.append(comment)
        return comments
    
    def clear(self) -> None:
        """清空存储（主要用于测试）"""
        self._evidence.clear()
        self._comments.clear()
        self._comments_by_evidence.clear()
