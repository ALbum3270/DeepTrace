from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from uuid import uuid4

class Claim(BaseModel):
    """
    关键声明/事实模型
    """
    id: str = Field(default_factory=lambda: str(uuid4())) # Unique ID for tracking
    content: str                # 声明内容
    source_evidence_id: str     # 来源 Evidence ID
    
    # Core Metrics
    credibility_score: float    # 来源可信度 (0-100) -> Maps to Alpha = score/100
    importance: float           # 重要性 (0-100) -> Maps to Beta = score/100
    confidence: float = 0.0     # 综合置信度 (0-100)
    
    status: Literal["unverified", "verified", "disputed"] = "unverified"
    verification_queries: List[str] = []  # 为这个声明生成的验证查询

    @property
    def is_verified(self) -> bool:
        return self.status == "verified"

    @property
    def is_disputed(self) -> bool:
        return self.status == "disputed"
    
    @property
    def alpha(self) -> float:
        """Helper: Normalized Credibility (0.0 - 1.0)"""
        return self.credibility_score / 100.0

    @property
    def beta(self) -> float:
        """Helper: Normalized Importance (0.0 - 1.0)"""
        return self.importance / 100.0
