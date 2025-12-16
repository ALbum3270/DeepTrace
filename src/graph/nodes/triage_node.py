import logging
from typing import Dict, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI

from ...core.models.task import BreadthTask, DepthTask
from ...config.settings import settings
from ...agents.prompts import TRIAGE_SYSTEM_PROMPT
from ...graph.state import GraphState
from ...graph.utils.state_utils import safe_set_get
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def can_claim_trigger_task(claim, evidences_list: list) -> bool:
    """
    Phase 13: Check if claim's supporting evidence allows task triggering.
    Returns False if all supporting evidence is opinion_only (unless importance >= 0.9).
    """
    ev_map = {e.id: e for e in evidences_list}
    ev_id = getattr(claim, "source_evidence_id", None)
    
    if ev_id and ev_id in ev_map:
        ev = ev_map[ev_id]
        if getattr(ev, "can_trigger_task", True):
            return True
        # Evidence cannot trigger - check importance override
        if getattr(claim, "importance", 0) >= 0.9:
            return True  # Allow critical claims to still trigger verification
        return False
    
    # No linked evidence, allow by default
    return True

async def triage_candidates_node(state: GraphState) -> Dict[str, Any]:
    """
    Triage Node: 生成并筛选下一步的广度与深度任务。
    逻辑：
    1. 构建上下文 (Timeline, Claims, Executed Queries)
    2. 计算 VoI 并过滤 (Cost-Escalating Model)
       - Breadth: (Rel * Gap * Nov) / (BaseCost * (1 + 0.5*Layer))
       - Depth: (Important * Unverified) / (BaseCost * (1 + 0.5*Layer))
    3. 调用 LLM 生成候选 (Breadth Candidates)
    4. 更新 pools
    """
    logger.info("Starting Triage Process...")
    
    # 0. Global Settings
    current_layer = state.get("current_layer", 0)
    
    # --- Helper Functions for VoI ---
    def compute_breadth_voi(relevance: float, gap_coverage: float, novelty: float, layer: int) -> tuple[float, float]:
        """返回 (voi_score, estimated_cost)"""
        base_cost = settings.BREADTH_BASE_COST
        layer_cost = base_cost * (1.0 + settings.BREADTH_LAYER_COST_FACTOR * layer)
        
        # Benefit = Rel * Gap * Nov
        benefit = relevance * gap_coverage * novelty
        voi = benefit / max(layer_cost, 1e-3)
        return voi, layer_cost

    def compute_topic_score(text: str, query: str) -> float:
        """Simple topic relevance proxy: Text overlap + SequenceMatcher"""
        if not query: return 1.0
        # 1. Keyword Overlap (Jaccard on words)
        set1 = set(text.lower().split())
        set2 = set(query.lower().split())
        overlap = len(set1.intersection(set2)) / max(len(set2), 1) # Coverage of query terms
        
        # 2. Sequence Sim
        seq_sim = SequenceMatcher(None, text.lower(), query.lower()).ratio()
        
        # 3. Combined Score (Bias towards query coverage)
        return 0.7 * overlap + 0.3 * seq_sim

    def compute_depth_voi_for_claim(claim, layer: int, root_query: str) -> tuple[float, float]:
        """返回 (voi_score, estimated_cost)"""
        beta = claim.beta if claim.beta is not None else 0.0
        alpha = claim.alpha if claim.alpha is not None else 0.0
        
        # Topic Score
        topic_score = compute_topic_score(claim.content, root_query)
        
        base_cost = settings.DEPTH_BASE_COST
        layer_cost = base_cost * (1.0 + settings.DEPTH_LAYER_COST_FACTOR * layer)
        
        # Benefit = Beta * (1 - Alpha) * TopicScore
        benefit = (
            settings.VOI_WEIGHT_BETA * beta *
            settings.VOI_WEIGHT_UNCERTAINTY * (1.0 - alpha) *
            topic_score # Penalize off-topic claims
        )
        voi = benefit / max(layer_cost, 1e-3)
        return voi, layer_cost
    # --------------------------------
    
    # 1. 准备上下文
    query = state.get("current_query", "")
    initial_query = state.get("initial_query", query) # Use root query for topic anchor
    timeline = state.get("timeline")
    claims = state.get("claims", [])
    executed_queries = state.get("executed_queries", set())
    
    # 简化的上下文构建
    timeline_str = timeline.to_markdown() if timeline else "无时间线数据"
    
    # 仅展示未验证的 Claims
    unverified_claims = [c for c in claims if not c.is_verified]
    # Top 20 relevant claims to avoid context overflow
    top_claims = sorted(unverified_claims, key=lambda x: x.importance, reverse=True)[:20]
    
    # Create lookup map for Claims
    {c.id: c for c in top_claims}
    
    claims_text = "\n".join([
        f"- [ID: {c.id}] (Cred: {c.credibility_score}, Imp: {c.importance}) {c.content}" 
        for c in top_claims
    ])
    
    executed_queries_text = "\n".join(list(executed_queries)[:50]) # Limit history
    
    user_context = f"""
    用户查询: {query}
    
    已执行查询 (Executed Queries):
    {executed_queries_text}
    
    当前时间线摘要:
    {timeline_str}
    
    待验证关键声明 (Top Unverified Claims):
    {claims_text}
    """
    
    # 2. 调用 LLM
    llm = ChatOpenAI(
        model=settings.model_name,
        temperature=0.3, # Triage should be somewhat creative but logical
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", TRIAGE_SYSTEM_PROMPT),
        ("user", "{input}")
    ])
    
    chain = prompt | llm | JsonOutputParser()
    
    try:
        result = await chain.ainvoke({"input": user_context})
    except Exception as e:
        logger.error(f"Triage LLM failed: {e}")
        return {} # Fail safe
        
    # 3. 解析与 VoI 计算
    new_breadth_tasks = []
    new_depth_tasks = []
    
    current_layer = state.get("current_layer", 0)
    
    # 获取现有池子 (Read existing)
    existing_breadth = state.get("breadth_pool", [])
    existing_depth = state.get("depth_pool", [])
    
    # 建立已存在 Query 集合 (防止重复)
    known_queries = set()
    # 使用安全的 set 读取 (executed_queries)
    executed_queries = safe_set_get(state, "executed_queries")
    for q in executed_queries:
        known_queries.add(q.lower().strip())
    for t in existing_breadth:
        known_queries.add(t.query.lower().strip())
    
    # 已处理的 Claim ID (防止重复深度任务)
    verified_claim_ids = safe_set_get(state, "verified_claim_ids")
    attempted_claim_ids = safe_set_get(state, "attempted_claim_ids")
    existing_depth_claim_ids = {t.claim_id for t in existing_depth}
    
    # Phase 12: Build structural claim set from timeline conflicts
    timeline = state.get("timeline")
    structural_keywords = set()
    if timeline and hasattr(timeline, 'open_questions'):
        for q in timeline.open_questions:
            if hasattr(q, 'tags') and 'conflict' in q.tags:
                # Extract keywords from question/context for matching
                structural_keywords.update(q.question.lower().split())
                structural_keywords.update(q.context.lower().split())
    
    # ========== 刀 1: Process Breadth Candidates (去重 + Top-K) ==========
    breadth_unique = {}  # key: normalized query -> best task
    if "breadth_candidates" in result:
        for item in result["breadth_candidates"]:
            query_raw = item.get("query", "")
            query_norm = query_raw.lower().strip()
            
            # Skip executed/known
            if query_norm in known_queries:
                logger.info(f"Skipping duplicate/executed query: {query_raw}")
                continue
            
            # VoI Calculation (Updated Model)
            relevance = float(item.get("relevance", 0.0))
            gap = float(item.get("gap_coverage", 0.0))
            novelty = float(item.get("novelty", 0.0))
            
            voi, est_cost = compute_breadth_voi(relevance, gap, novelty, current_layer)
            
            if voi < settings.BREADTH_VOI_THRESHOLD:
                continue
            
            task = BreadthTask(
                layer=current_layer + 1,
                query=query_raw,
                reason=item.get("reason"),
                relevance=relevance,
                gap_coverage=gap,
                novelty=novelty,
                voi_score=voi,
                estimated_cost=est_cost
            )
            
            # Dedup: keep highest VoI for same query
            if query_norm not in breadth_unique or voi > breadth_unique[query_norm].voi_score:
                breadth_unique[query_norm] = task
    
    new_breadth_tasks = list(breadth_unique.values())
    
    # Top-K Filtering for Breadth
    if new_breadth_tasks:
        new_breadth_tasks.sort(key=lambda x: x.voi_score, reverse=True)
        limit = settings.MAX_TOP_K_BREADTH_TASKS
        if len(new_breadth_tasks) > limit:
            logger.info(f"Breadth Top-K: Keeping top {limit} of {len(new_breadth_tasks)} tasks")
            new_breadth_tasks = new_breadth_tasks[:limit]
        for t in new_breadth_tasks:
            logger.info(f"Accepted Breadth Task: {t.query} (VoI: {t.voi_score:.2f})")

    # ========== 刀 2: Proactive DepthTask Generation from Claims ==========
    # 直接扫描 Claims，而不仅仅依赖 LLM 输出
    depth_unique = {}  # key: claim_id -> best task
    for claim in claims:
        # Skip already verified, attempted, or already in pool
        if claim.id in verified_claim_ids:
            continue
        if claim.id in attempted_claim_ids:  # NEW: Skip already attempted
            continue
        if claim.id in existing_depth_claim_ids:
            continue
        
        # Phase 13: Skip claims backed only by opinion_only sources
        evidences = state.get("evidences", [])
        if not can_claim_trigger_task(claim, evidences):
            logger.debug(f"Skipping Depth for claim {claim.id[:8]}: opinion_only source, importance {getattr(claim, 'importance', 0):.2f}")
            continue
            
        # [NEW] Check alpha threshold (if claim is already strong, don't verify)
        if hasattr(claim, 'alpha') and claim.alpha >= settings.CREDIBILITY_VERIFIED_THRESHOLD:
            continue
        
        # VoI Calculation (Updated Model with Topic Score)
        voi, est_cost = compute_depth_voi_for_claim(claim, current_layer, initial_query)
        
        # Dynamic Threshold for Deeper Layers
        threshold = settings.DEPTH_VOI_THRESHOLD
        if current_layer >= 1:
            threshold = max(threshold, 0.2) # Stricter for deeper layers
        
        # Phase 12: Boost structural claims (those matching conflict keywords)
        claim_words = set(claim.content.lower().split())
        if structural_keywords and claim_words.intersection(structural_keywords):
            voi += 0.1  # Boost for structural/conflict-related claims
            logger.debug(f"Structural boost for claim {claim.id[:8]}: VoI {voi - 0.1:.2f} -> {voi:.2f}")
        
        if voi < threshold:
            continue
        
        task = DepthTask(
            layer=current_layer, # Keep in current layer scope
            claim_id=claim.id,
            reason=f"High β ({claim.beta:.2f}), Low α ({claim.alpha:.2f}): {claim.content[:50]}...",
            beta_structural=claim.beta,
            alpha_current=claim.alpha,
            voi_score=voi,
            estimated_cost=est_cost
        )
        
        # Dedup by claim_id (keep highest VoI)
        if claim.id not in depth_unique or voi > depth_unique[claim.id].voi_score:
            depth_unique[claim.id] = task
    
    new_depth_tasks = list(depth_unique.values())
    
    # Top-K Filtering for Depth
    if new_depth_tasks:
        new_depth_tasks.sort(key=lambda x: x.voi_score, reverse=True)
        limit = settings.MAX_TOP_K_DEPTH_TASKS
        if len(new_depth_tasks) > limit:
            logger.info(f"Depth Top-K: Keeping top {limit} of {len(new_depth_tasks)} tasks")
            new_depth_tasks = new_depth_tasks[:limit]
        for t in new_depth_tasks:
            logger.info(f"Accepted Depth Task: {t.claim_id} (VoI: {t.voi_score:.2f})")

    # Return state updates (append to pools)
    return {
        "breadth_pool": existing_breadth + new_breadth_tasks,
        "depth_pool": existing_depth + new_depth_tasks
    }
