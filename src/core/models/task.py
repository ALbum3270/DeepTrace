from typing import Dict, Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

class BreadthTask(BaseModel):
    """
    广度任务：代表一个"需要去搜寻新信息"意图。
    关注：Relevance (相关性), GapCoverage (缺口覆盖), Novelty (新颖性)
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    layer: int = Field(..., description="所属层级")
    query: str = Field(..., description="生成的搜索查询")
    origin_claim_id: Optional[str] = Field(None, description="任务源自哪个 Claim (若有)")
    reason: Optional[str] = Field(None, description="任务创建/被选中的理由")
    
    estimated_cost: float = Field(1.0, description="预估执行成本")
    
    # VoI Factors (0.0 - 1.0)
    relevance: float = Field(0.0, description="与用户核心问题的相关性")
    gap_coverage: float = Field(0.0, description="对Timeline/Topic缺口的覆盖度")
    novelty: float = Field(0.0, description="与过往查询的差异度")
    
    voi_score: float = Field(0.0, description="综合任务价值分 = (Rel * Gap * Nov) / Cost")
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DepthTask(BaseModel):
    """
    深度任务：代表一个"需要验证关键声明"的意图。
    关注：structure_beta (重要性), current_alpha (当前可信度)
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    layer: int = Field(..., description="所属层级")
    claim_id: str = Field(..., description="待验证的 Claim ID")
    reason: Optional[str] = Field(None, description="任务创建/被选中的理由")
    
    estimated_cost: float = Field(2.0, description="预估执行成本 (验证通常更贵)")
    
    # VoI Factors
    beta_structural: float = Field(0.0, description="Claim 在叙事中的结构重要性 (0-1)")
    alpha_current: float = Field(0.0, description="Claim 当前的可信度 (0-1)")
    
    voi_score: float = Field(0.0, description="综合任务价值分 = Beta * (1 - Alpha) / Cost")
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
