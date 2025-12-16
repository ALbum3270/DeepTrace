from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from uuid import uuid4
from enum import Enum

class TruthStatus(str, Enum):
    # Verified by Fact Source (Official/Authoritative) + No structural conflict
    CONFIRMED = "confirmed"      
    # Strong evidence (Mixed/Mainstream) OR Fact Source with minor conflict
    # Must be phrased as "According to media/reports..."
    LIKELY = "likely"            
    # Conflicting evidence exists, cannot determine truth. 
    # Must be phrased as "Conflicting reports..."
    UNRESOLVED = "unresolved"    
    # Proven false by stronger evidence (e.g. Official denial)
    REJECTED = "rejected"        
    # Insufficient info to judge
    UNKNOWN = "unknown"

class Claim(BaseModel):
    """
    关键声明/事实模型
    """
    id: str = Field(default_factory=lambda: str(uuid4())) # Unique ID for tracking
    content: str                # 声明内容 (LLM归纳)
    canonical_text: str = ""    # 来源原文摘要 (用于安全渲染，避免 LLM 幻觉)
    source_evidence_id: str     # 首次发现的 Evidence ID
    supporting_evidence_ids: List[str] = Field(default_factory=list)  # Phase 16: 所有支持此 Claim 的 Evidence IDs
    
    # Core Metrics
    credibility_score: float    # 来源可信度 (0-100) -> Maps to Alpha = score/100
    importance: float           # 重要性 (0-100) -> Maps to Beta = score/100
    confidence: float = 0.0     # 综合置信度 (0-100)
    
    status: Literal["unverified", "verified", "disputed"] = "unverified"
    verification_queries: List[str] = []  # 为这个声明生成的验证查询
    
    # Phase 14: Strict Truth Status
    truth_status: TruthStatus = TruthStatus.UNKNOWN
    is_cluster_winner: bool = Field(False, description="Is this the 'winning' claim in a conflict cluster?")

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

