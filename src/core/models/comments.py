"""
评论模型：评论数据与评论打分结构。
"""
from datetime import datetime
from typing import Optional, List
from uuid import uuid4
from pydantic import BaseModel, Field


class Comment(BaseModel):
    """评论数据结构"""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(..., description="评论内容")
    author: Optional[str] = Field(None, description="评论作者")
    role: str = Field("public_opinion", description="角色: public_opinion, direct_quote, controversy")
    publish_time: Optional[datetime] = Field(None, description="发布时间")
    parent_id: Optional[str] = Field(None, description="父评论ID（用于嵌套评论）")
    source_evidence_id: str = Field(..., description="所属帖子/文章的证据ID")
    source_url: Optional[str] = Field(None, description="来源URL")
    meta: dict = Field(default_factory=dict, description="元数据 (likes, etc.)")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class CommentScore(BaseModel):
    """
    评论打分结构（用于 CommentTriage Agent）。
    
    评分维度：
    - novelty: 新颖性（新实体、新时间点）
    - evidence: 证据性（截图、订单号、具体细节）
    - contradiction: 反驳性（与现有叙事冲突）
    - influence: 影响力（点赞数、作者权威性）
    - coordination: 协调性（是否呼应其他评论）
    """
    
    source_evidence_id: str = Field(..., description="关联的证据ID")
    comment_id: str = Field(..., description="关联的评论ID")
    novelty: float = Field(default=0.0, ge=0.0, le=1.0, description="新颖性")
    evidence: float = Field(default=0.0, ge=0.0, le=1.0, description="证据性")
    contradiction: float = Field(default=0.0, ge=0.0, le=1.0, description="反驳性")
    influence: float = Field(default=0.0, ge=0.0, le=1.0, description="影响力")
    coordination: float = Field(default=0.0, ge=0.0, le=1.0, description="协调性")
    
    total_score: float = Field(default=0.0, ge=0.0, le=1.0, description="综合得分")
    tags: List[str] = Field(default_factory=list, description="标签，如 new_entity/contradiction")
    reason: str = Field(default="", description="打分理由")
    rationale: str = Field(default="", description="LLM 给出的详细理由")
    
    def calculate_total(self, weights: Optional[dict] = None) -> float:
        """
        计算综合得分。
        
        Args:
            weights: 各维度权重，默认均等
            
        Returns:
            综合得分 (0.0 ~ 1.0)
        """
        if weights is None:
            weights = {
                "novelty": 0.3,
                "evidence": 0.3,
                "contradiction": 0.2,
                "influence": 0.1,
                "coordination": 0.1,
            }
        
        total = (
            self.novelty * weights.get("novelty", 0.3)
            + self.evidence * weights.get("evidence", 0.3)
            + self.contradiction * weights.get("contradiction", 0.2)
            + self.influence * weights.get("influence", 0.1)
            + self.coordination * weights.get("coordination", 0.1)
        )
        
        self.total_score = min(max(total, 0.0), 1.0)
        return self.total_score
