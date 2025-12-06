from ..state import GraphState
from ...agents.retrieval_planner import plan_retrieval
from ...config.settings import settings


async def planner_node(state: GraphState) -> GraphState:
    """
    Planner Node: 分析当前状态，生成下一步检索计划。
    """
    timeline = state.get("timeline")
    evidences = state.get("evidences", [])
    loop_step = state.get("loop_step", 0)
    seen_queries = state.get("seen_queries") or set()
    
    # 如果没有时间线，无法规划（理论上不应发生，因为 build 在前）
    if not timeline:
        return {
            "steps": ["planner: no timeline, skip"]
        }
        
    # Check Max Loops
    if loop_step >= settings.MAX_RETRIEVAL_ROUNDS:
        return {
            "retrieval_plan": None, # Signal to stop? Or just empty plan
            "steps": [f"planner: Max rounds reached ({settings.MAX_RETRIEVAL_ROUNDS}), stopping."],
            # Force finish by not setting a new current_query
        }

    # 调用 Agent 生成计划
    plan = await plan_retrieval(timeline, evidences, seen_queries)
    
    # Update seen_queries with new queries from plan
    if plan.queries:
        for q in plan.queries:
            seen_queries.add(q.query.strip().lower())
    
    # --- Gain Score Logic ---
    from ...agents.gain_scorer import calculate_gain_score, should_stop_retrieval
    
    run_stats = state.get("run_stats", [])
    previous_stats = run_stats[-1] if run_stats else None
    comment_scores = state.get("comment_scores", [])
    
    gain_result = calculate_gain_score(timeline, comment_scores, previous_stats)
    
    # Update run_stats (Append current metrics)
    new_stats_entry = gain_result.metrics
    
    # Check stop condition
    if should_stop_retrieval(gain_result, loop_step):
        plan.finish = True
        plan.thought_process += f" [System] Auto-stop triggered: {gain_result.reason}"
    
    new_state = {
        "retrieval_plan": plan,
        "search_queries": plan.queries, # 追加到历史查询列表
        "seen_queries": seen_queries,   # Update seen set
        "steps": [
            f"planner: loop={loop_step}, finish={plan.finish}, got {len(plan.queries)} queries",
            f"planner: GainScore={gain_result.score:.2f} ({gain_result.reason})"
        ],
        "loop_step": loop_step + 1,
        "run_stats": [new_stats_entry] # Append to stats
    }
    
    # 如果有新查询，选择一个更新 current_query
    # MVP: 简单选择第一个查询
    if plan.queries and not plan.finish:
        next_query = plan.queries[0]
        new_state["current_query"] = next_query.query
        new_state["steps"].append(f"planner: next query='{next_query.query}' (reason: {next_query.rationale})")
        
    return new_state
