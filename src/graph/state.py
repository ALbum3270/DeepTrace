from typing import TypedDict, List, Annotated
import operator

from ..core.models.evidence import Evidence
from ..core.models.events import EventNode
from ..core.models.timeline import Timeline
from ..core.models.comments import CommentScore
from ..core.models.plan import RetrievalPlan, SearchQuery


class GraphState(TypedDict, total=False):
    """
    DeepTrace 图状态定义。
    使用 total=False 允许部分更新。
    使用 Annotated[List, operator.add] 实现列表增量聚合。
    """
    # Input
    initial_query: str
    current_query: str  # 当前这一轮 fetch 使用的 query

    # Intermediate (Accumulated)
    # 证据列表：多个节点可能产生证据，自动合并
    evidences: Annotated[List[Evidence], operator.add]
    # 事件列表：多个提取节点可能产生事件，自动合并
    events: Annotated[List[EventNode], operator.add]
    # 评论评分：多个 Triage 节点可能产生评分，自动合并
    comment_scores: Annotated[List[CommentScore], operator.add]
    
    # Planner 相关
    retrieval_plan: RetrievalPlan
    search_queries: Annotated[List[SearchQuery], operator.add]
    loop_step: int
    max_loops: int
    
    # 执行步骤记录：用于调试和展示执行轨迹
    steps: Annotated[List[str], operator.add]

    # Output
    timeline: Timeline

    # Error handling (optional)
    error: str
