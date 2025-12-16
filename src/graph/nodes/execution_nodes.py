
import logging
from typing import Dict, Any, List

from ...config.settings import settings
from ...graph.state import GraphState
from ...core.models.task import BreadthTask, DepthTask
# Import existing tools/agents
# We need to perform Search & Extract. 
# Reusing existing nodes might be complex if they expect different state.
# Let's try to call the functionalities directly or reuse logic.
# For simplicity in Lite, let's implement the core logic here or import from existing nodes.
# Existing: fetch_search_node, extract_event_node. 
# But they depend on `state['current_query']`.
# So this node can just SETUP the query and return, then we link to Fetch -> Extract -> Triage.
# BUT, we need to POP the task first.

logger = logging.getLogger(__name__)

def pop_breadth_task_node(state: GraphState) -> Dict[str, Any]:
    """
    Breadth 执行节点 (Pre-Fetch):
    1. 从 breadth_pool 中取出当前层 VoI 最高任务
    2. 更新 current_query
    3. 增加 current_layer_breadth_steps
    """
    current_layer = state.get("current_layer", 0)
    breadth_pool: List[BreadthTask] = state.get("breadth_pool", [])
    
    # Filter for current layer
    layer_tasks = [t for t in breadth_pool if t.layer == current_layer]
    
    if not layer_tasks:
        logger.warning(f"No breadth tasks for layer {current_layer}!")
        return {}
    
    # Sort by VoI (descending)
    layer_tasks.sort(key=lambda x: x.voi_score, reverse=True)
    selected_task = layer_tasks[0]
    
    # Remove from pool (using ID/reference)
    # Rebuild pool without selected
    new_pool = [t for t in breadth_pool if t.id != selected_task.id]
    
    logger.info(f"Executing Breadth Task: {selected_task.query} (VoI: {selected_task.voi_score:.2f})")
    
    return {
        "current_query": selected_task.query,
        "breadth_pool": new_pool,
        "current_layer_breadth_steps": state.get("current_layer_breadth_steps", 0) + 1,
        "executed_queries": {selected_task.query} # Add to set
    }

def pop_depth_task_node(state: GraphState) -> Dict[str, Any]:
    """
    Depth 执行节点 (Pre-Fetch):
    1. 从 depth_pool 中取出当前层 VoI 最高任务 (Claim)
    2. 生成验证查询 (Verification Planner)
    3. 更新 current_query (Pick best one)
    4. 增加 current_layer_depth_steps
    """
    # Note: Depth flow is tricky because it needs "Verification Planner" to turn Claim -> Query.
    # We can do it here.
    
    # But verification_planner_node expects 'verification_queue' logic usually.
    # Here we just want to run the planner for ONE claim.
    # Let's import the planner function directly if possible, or reimplement lightweight version.
    # Checking `src/agents/verification_planner.py`... 
    # It has `plan_verification(claim, client)`.
    
    # For now, let's assume we can import it.
    # If not, we might need a separate planner node in the graph, but that complicates the graph.
    # Let's try to do it inline (Lite approach).
    
    # NOTE: Since we cannot run async function easily inside a sync node unless we use async node def.
    # This file should use async def.
    pass 

async def execute_depth_setup_node(state: GraphState) -> Dict[str, Any]:
    current_layer = state.get("current_layer", 0)
    depth_pool: List[DepthTask] = state.get("depth_pool", [])
    
    # Filter for current layer
    layer_tasks = [t for t in depth_pool if t.layer == current_layer]
    
    if not layer_tasks:
        logger.warning(f"No depth tasks for layer {current_layer}!")
        return {}
        
    # Sort by VoI
    layer_tasks.sort(key=lambda x: x.voi_score, reverse=True)
    selected_task = layer_tasks[0]
    
    # Remove from pool
    new_pool = [t for t in depth_pool if t.id != selected_task.id]
    
    # Generate Query
    # We need to find the Claim content.
    # Helper to find claim ?? 
    # We should have stored Claim content? No, we stored Claim ID.
    # We need to look it up in `state['claims']`.
    
    claims = state.get("claims", [])
    target_claim = next((c for c in claims if c.id == selected_task.claim_id), None)
    
    query = ""
    if target_claim:
        logger.info(f"Verifying Claim: {target_claim.content[:30]}... (VoI: {selected_task.voi_score:.2f})")
        
        # Call Planner
        from langchain_openai import ChatOpenAI
        from ...agents.verification_planner import plan_verification
        
        llm = ChatOpenAI(
            model=settings.model_name,
            temperature=0,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        
        try:
            ver_result = await plan_verification(target_claim, llm)
            queries = ver_result.get("queries", [])
            if queries:
                query = queries[0] # Pick first for single execution
                logger.info(f"Generated Verification Query: {query}")
            else:
                logger.warning("No verification queries generated.")
                query = target_claim.content # Fallback
        except Exception as e:
            logger.error(f"Verification planning failed: {e}")
            query = target_claim.content
            
    else:
        logger.warning(f"Claim {selected_task.claim_id} not found!")
        query = "Missing Claim"

    return {
        "current_query": query,
        "depth_pool": new_pool,
        "current_layer_depth_steps": state.get("current_layer_depth_steps", 0) + 1,
        "executed_queries": {query}
    }
