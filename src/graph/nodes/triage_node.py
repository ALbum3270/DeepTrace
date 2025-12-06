import json
import logging
from typing import Dict, Any, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI

from ...core.models.task import BreadthTask, DepthTask
from ...config.settings import settings
from ...agents.prompts import TRIAGE_SYSTEM_PROMPT
from ...graph.state import GraphState

logger = logging.getLogger(__name__)

async def triage_candidates_node(state: GraphState) -> Dict[str, Any]:
    """
    Triage Node: 生成并筛选下一步的广度与深度任务。
    逻辑：
    1. 构建上下文 (Timeline, Claims, Executed Queries)
    2. 调用 LLM 生成候选 (Breadth & Depth Candidates)
    3. 计算 VoI 并过滤
    4. 更新 pools
    """
    logger.info("Starting Triage Process...")
    
    # 1. 准备上下文
    query = state.get("current_query", "")
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
    claim_map = {c.id: c for c in top_claims}
    
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
    
    # Process Breadth Candidates
    if "breadth_candidates" in result:
        for item in result["breadth_candidates"]:
            # VoI Calculation
            relevance = float(item.get("relevance", 0.0))
            gap = float(item.get("gap_coverage", 0.0))
            novelty = float(item.get("novelty", 0.0))
            cost = settings.COST_BREADTH_DEFAULT
            
            voi = (relevance * gap * novelty) / cost
            
            if voi >= settings.BREADTH_VOI_THRESHOLD:
                task = BreadthTask(
                    layer=current_layer + 1, # Next layer task
                    query=item["query"],
                    reason=item.get("reason"),
                    relevance=relevance,
                    gap_coverage=gap,
                    novelty=novelty,
                    voi_score=voi,
                    estimated_cost=cost
                )
                new_breadth_tasks.append(task)
                logger.info(f"Accepted Breadth Task: {task.query} (VoI: {voi:.2f})")

    # Process Depth Candidates
    if "depth_candidates" in result:
        for item in result["depth_candidates"]:
            # Map back to real claim ID (using index or matching content)
            # In prompt we printed "ID: {i}", assuming LLM returns that index or ID.
            # Wait, LLM might hallucinate ID. Safer to fuzzy match or use strict ID if passed.
            # Hack: We passed "ID: {i}" (index). Let's see if LLM returns "0", "1", etc.
            # Simplified: Let's assume LLM returns the full Content or we try to match ID.
            # For robustness, let's map logic index back to claim object
            
            # Refinement: The prompt logic above used `enumerate` index as ID. 
            # I should verify if `claim_id` in response is the index.
            try:
                # Use strict ID matching
                target_id = item["claim_id"]
                if target_id in claim_map:
                    target_claim = claim_map[target_id]
                    
                    # VoI Calculation
                    beta = float(item.get("beta_structural", target_claim.beta))
                    alpha = float(item.get("alpha_current", target_claim.alpha))
                    cost = settings.COST_DEPTH_DEFAULT
                    
                    voi = beta * (1.0 - alpha) / cost
                    
                    if voi >= settings.DEPTH_VOI_THRESHOLD:
                        task = DepthTask(
                            layer=current_layer, 
                            claim_id=target_claim.id, # Use real UUID
                            reason=item.get("reason"),
                            beta_structural=beta,
                            alpha_current=alpha,
                            voi_score=voi,
                            estimated_cost=cost
                        )
                        new_depth_tasks.append(task)
                        logger.info(f"Accepted Depth Task: {task.claim_id} (VoI: {voi:.2f})")
                else:
                    logger.warning(f"Claim ID not found in current context: {target_id}")
            except Exception as e:
                logger.warning(f"Error processing depth candidate: {e}")

    # Return state updates (append to pools)
    return {
        "breadth_pool": new_breadth_tasks,
        "depth_pool": new_depth_tasks
    }
