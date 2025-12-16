"""
GraphState Initialization Utilities
统一的 GraphState 字段初始化，确保 set/list 类型的一致性。
"""
from typing import Set
from ..state import GraphState


def ensure_state_sets(state: GraphState) -> GraphState:
    """
    确保 GraphState 中所有 set 类型字段都已正确初始化为 set。
    防止序列化/反序列化后 set 变成 list 导致的类型错误。
    
    Args:
        state: GraphState 实例
        
    Returns:
        更新后的 GraphState
    """
    # Set fields that need to be initialized
    set_fields = [
        "seen_queries",
        "handled_claims",
        "processed_evidence_ids",
        "verified_claim_ids",
        "attempted_claim_ids",
        "executed_queries",
    ]
    
    for field in set_fields:
        if field in state:
            # If field exists but is not a set (e.g., after deserialization), convert it
            if not isinstance(state[field], set):
                state[field] = set(state[field]) if state[field] else set()
        else:
            # If field doesn't exist, initialize it
            state[field] = set()
    
    # List fields that should be initialized as empty lists
    list_fields = [
        "evidences",
        "events",
        "comment_scores",
        "comments",
        "claims",
        "search_queries",
        "breadth_pool",
        "depth_pool",
        "steps",
        "run_stats",
    ]
    
    for field in list_fields:
        if field not in state:
            state[field] = []
    
    # Integer fields with defaults
    int_fields = {
        "loop_step": 0,
        "max_loops": 3,
        "verification_loop_count": 0,
        "current_layer": 0,
        "current_layer_breadth_steps": 0,
        "current_layer_depth_steps": 0,
    }
    
    for field, default_value in int_fields.items():
        if field not in state:
            state[field] = default_value
    
    return state


def safe_set_get(state: GraphState, field: str, default: Set = None) -> Set:
    """
    安全地从 GraphState 中获取 set 类型字段。
    
    Args:
        state: GraphState 实例
        field: 字段名
        default: 默认值（如果为 None，则使用空 set）
        
    Returns:
        Set 类型的字段值
    """
    if default is None:
        default = set()
    
    value = state.get(field, default)
    
    # Ensure it's a set
    if not isinstance(value, set):
        return set(value) if value else default
    
    return value


def safe_set_update(state: GraphState, field: str, new_values: Set) -> GraphState:
    """
    安全地更新 GraphState 中的 set 类型字段（合并操作）。
    
    Args:
        state: GraphState 实例
        field: 字段名
        new_values: 要合并的新值
        
    Returns:
        更新后的 GraphState
    """
    existing = safe_set_get(state, field)
    state[field] = existing.union(new_values)
    return state
