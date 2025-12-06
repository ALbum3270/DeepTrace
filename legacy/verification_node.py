import asyncio
from typing import List, Set
from ..state import GraphState
from ...agents.verification_planner import plan_verification
from ...config.settings import settings
from ...core.models.strategy import SearchStrategy

async def verification_planner_node(state: GraphState) -> GraphState:
    """
    Verification Planner Node: 
    1. Check loop limits.
    2. Identify unhandled, important, low-credibility claims.
    3. Generate verification queries.
    """
    claims = state.get("claims", [])
    handled_claims = state.get("handled_claims") or set()
    loop_count = state.get("verification_loop_count", 0)
    current_queue = state.get("verification_queue", [])
    
    # Safety Check: If queue is not empty, we shouldn't be planning yet? 
    # Actually, the router should ensure we only come here if queue is empty.
    
    if loop_count >= settings.MAX_BFS_DFS_CYCLES:
        return {
            "steps": ["verification_planner: Max cycles reached, stopping verification."]
        }

    # Filter claims that need verification and haven't been handled
    candidate_claims = []
    for c in claims:
        # Deduplication by content
        if c.content in handled_claims:
            continue
        candidate_claims.append(c)
        
    if not candidate_claims:
        return {
            "steps": ["verification_planner: No new unhandled claims."]
        }

    # Call Agent
    new_queries = await plan_verification(candidate_claims)
    
    # Mark candidate claims as handled (regardless of whether they generated queries, 
    # to prevent infinite planning loop for same claims)
    new_handled = set()
    for c in candidate_claims:
        new_handled.add(c.content)
    
    # Update State
    updated_queue = current_queue + new_queries
    
    return {
        "verification_queue": updated_queue,
        "handled_claims": handled_claims.union(new_handled),
        "verification_loop_count": loop_count + 1,
        "steps": [f"verification_planner: Generated {len(new_queries)} queries from {len(candidate_claims)} new claims (Cycle {loop_count+1})"]
    }

async def pop_verification_query_node(state: GraphState) -> GraphState:
    """
    Helper Node: Pop a query from verification_queue and set it as current_query.
    """
    queue = state.get("verification_queue", [])
    if not queue:
        return {
            "steps": ["pop_verification_query: Queue empty, nothing to do."]
        }
        
    next_query = queue[0]
    remaining_queue = queue[1:]
    
    return {
        "current_query": next_query,
        "verification_queue": remaining_queue,
        "search_strategy": SearchStrategy.GENERIC, # Force Generic for specific verification
        "steps": [f"pop_verification_query: Popped '{next_query}'"]
    }
