from typing import List, Dict, Any
from pydantic import BaseModel, Field
import math

from ..core.models.timeline import Timeline
from ..core.models.evidence import Evidence
from ..core.models.comments import CommentScore

class GainScoreResult(BaseModel):
    score: float = Field(..., description="信息增益分数")
    is_converged: bool = Field(..., description="是否收敛（增益低于阈值）")
    metrics: Dict[str, Any] = Field(..., description="当前各项指标")
    reason: str = Field(..., description="判断理由")

def calculate_gain_score(
    timeline: Timeline, 
    comment_scores: List[CommentScore],
    previous_stats: Dict[str, Any] = None
) -> GainScoreResult:
    """
    计算当前轮次的信息增益 (GainScore)。
    
    Formula:
    Gain = w1 * ΔEvents + w2 * ΔHighValueComments + w3 * ΔAvgConfidence
    
    Weights:
    w1 (Events) = 1.0
    w2 (Comments) = 0.5
    w3 (Confidence) = 5.0 (Confidence is 0-1, so scale up)
    """
    
    # 1. Calculate Current Metrics
    num_events = len(timeline.events)
    
    # Count high value comments (score >= 0.8)
    num_high_comments = sum(1 for s in comment_scores if s.total_score >= 0.8)
    
    # Calculate average confidence
    if timeline.events:
        avg_confidence = sum(e.confidence for e in timeline.events) / len(timeline.events)
    else:
        avg_confidence = 0.0
        
    current_metrics = {
        "num_events": num_events,
        "num_high_comments": num_high_comments,
        "avg_confidence": avg_confidence
    }
    
    # 2. If no previous stats, return initial high gain (to ensure at least one more loop if needed, or just 0 delta)
    if not previous_stats:
        return GainScoreResult(
            score=100.0, # High initial score
            is_converged=False,
            metrics=current_metrics,
            reason="Initial run, high gain assumed."
        )
        
    # 3. Calculate Deltas
    delta_events = max(0, num_events - previous_stats.get("num_events", 0))
    delta_comments = max(0, num_high_comments - previous_stats.get("num_high_comments", 0))
    delta_confidence = max(0.0, avg_confidence - previous_stats.get("avg_confidence", 0.0))
    
    # 4. Calculate Weighted Score
    w1, w2, w3 = 1.0, 0.5, 5.0
    
    score = (w1 * delta_events) + (w2 * delta_comments) + (w3 * delta_confidence)
    
    # 5. Determine Convergence
    # Threshold: If gain is very low (< 0.5), we consider it converged.
    # This means < 0.5 new event equivalent.
    threshold = 0.5
    is_converged = score < threshold
    
    reason = (
        f"Gain: {score:.2f} (Thresh: {threshold}). "
        f"ΔEvents: {delta_events}, ΔComments: {delta_comments}, ΔConf: {delta_confidence:.3f}"
    )
    
    return GainScoreResult(
        score=score,
        is_converged=is_converged,
        metrics=current_metrics,
        reason=reason
    )

def should_stop_retrieval(gain_result: GainScoreResult, loop_step: int, min_loops: int = 1) -> bool:
    """
    决定是否停止检索循环。
    
    Args:
        gain_result: 当前的信息增益结果
        loop_step: 当前循环次数 (0-indexed)
        min_loops: 最小循环次数 (默认 1，即至少跑完 loop 0 和 loop 1?) 
                   Wait, loop_step 0 is the first run.
                   If min_loops=1, we can stop after loop 0 if we check at the end of loop 0?
                   No, usually we want at least one feedback loop.
                   Let's say min_loops=1 means "allow stop after loop 1 starts" or "after loop 0 finishes"?
                   In planner_node, loop_step is passed AS IS (0 for first run).
                   If we want to force at least 1 re-planning, we should check loop_step > 0.
                   
    Returns:
        bool: True if should stop, False otherwise.
    """
    # 必须满足最小循环次数
    if loop_step < min_loops:
        return False
        
    # 如果增益收敛 (Score < Threshold)
    if gain_result.is_converged:
        return True
        
    return False
