"""
检索规划模型：定义检索计划和查询语句。
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from .evidence import EvidenceSource


class SearchQuery(BaseModel):
    """单条搜索查询"""
    query: str = Field(..., description="搜索关键词")
    rationale: str = Field(..., description="搜索理由")
    target_source: Optional[EvidenceSource] = Field(None, description="目标来源平台")
    related_open_question_id: Optional[str] = Field(None, description="关联的 OpenQuestion ID")


class RetrievalPlan(BaseModel):
    """检索计划"""
    queries: List[SearchQuery] = Field(default_factory=list, description="生成的查询列表")
    thought_process: str = Field(..., description="生成计划的思考过程")
    finish: bool = Field(False, description="是否结束检索（认为信息已充足）")
