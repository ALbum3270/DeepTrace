from typing import TypedDict, List, Annotated, Dict, Any, Set
import operator

from ..core.models.evidence import Evidence
from ..core.models.events import EventNode
from ..core.models.timeline import Timeline
from ..core.models.comments import CommentScore, Comment
from ..core.models.plan import RetrievalPlan, SearchQuery, WeiboCommentDepth
from ..core.models.strategy import SearchStrategy
from ..core.models.claim import Claim
from ..core.models.task import BreadthTask, DepthTask


class GraphState(TypedDict, total=False):
    """
    DeepTrace 图状态定义。
    使用 total=False 允许部分更新。
    使用 Annotated[List, operator.add] 实现列表增量聚合。
    """
    # Input
    initial_query: str
    current_query: str  # 当前这一轮 fetch 使用的 query
    
    # Supervisor Routing
    search_strategy: "SearchStrategy" # 路由控制
    platforms: List[str]            # 元数据：本次涉及的平台
    weibo_comment_depth: WeiboCommentDepth # 微博评论抓取深度
    evidence_depth: str  # 证据抓取深度: quick/balanced/deep

    # Intermediate (Accumulated)
    # 证据列表：多个节点可能产生证据，自动合并
    evidences: Annotated[List[Evidence], operator.add]
    # 事件列表：多个提取节点可能产生事件，自动合并
    events: Annotated[List[EventNode], operator.add]
    # 评论评分：多个 Triage 节点可能产生评分，自动合并
    comment_scores: Annotated[List[CommentScore], operator.add]
    # 原始评论：从 Extract 节点产生，自动合并
    comments: Annotated[List[Comment], operator.add]
    # 关键声明：从 Extract 节点产生，自动合并
    claims: Annotated[List[Claim], operator.add]
    
    # Planner 相关 (Legacy / Foundation)
    retrieval_plan: RetrievalPlan
    search_queries: Annotated[List[SearchQuery], operator.add]
    seen_queries: set[str] # 已执行过的查询集合（防环 - Legacy）
    loop_step: int
    max_loops: int
    
    # Verification Loop State (Legacy Phase 9)
    verification_queue: List[str]   # 待验证查询队列
    verification_loop_count: int    # 验证循环轮数
    handled_claims: set[str]        # 已处理/已生成验证查询的声明内容 (Dedup)
    processed_evidence_ids: set[str] # 已提取过信息的 Evidence ID 集合 (增量提取)
    
    # --- RAICT Lite Control (Phase 10) ---
    current_layer: int
    breadth_pool: List[BreadthTask]
    depth_pool: List[DepthTask]
    
    # History & Tracking
    verified_claim_ids: Set[str]    # 已验证过的 Claim ID
    executed_queries: Set[str]      # 已执行过的搜索 (用于 Novelty 计算 + 防环)
    
    # Layer Step Counters (reset per layer)
    current_layer_breadth_steps: int
    current_layer_depth_steps: int
    # -------------------------------------
    
    # 执行步骤记录：用于调试和展示执行轨迹
    steps: Annotated[List[str], operator.add]
    
    # 运行统计：用于 GainScore 计算
    run_stats: List[dict]

    # Output
    timeline: Timeline
    final_report: str

    # Error handling (optional)
    error: str
