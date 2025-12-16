import sys
import os
sys.path.append(os.getcwd())

from src.agents.gain_scorer import should_stop_retrieval, GainScoreResult

def test_judge_node_should_continue_high_gain():
    """
    Case 1: GainScore 很高 (未收敛) -> 应该继续 (返回 False)
    """
    # Mock result: High score, not converged
    gain_result = GainScoreResult(
        score=10.0,
        is_converged=False,
        metrics={},
        reason="High gain"
    )
    
    # Loop step doesn't matter much if not converged, but let's say loop 1
    should_stop = should_stop_retrieval(gain_result, loop_step=1, min_loops=1)
    
    assert should_stop is False

def test_judge_node_should_stop_converged():
    """
    Case 2: GainScore < Threshold (已收敛) 且 Loop >= Min -> 应该停止 (返回 True)
    """
    # Mock result: Low score, converged
    gain_result = GainScoreResult(
        score=0.1,
        is_converged=True,
        metrics={},
        reason="Low gain"
    )
    
    # Loop 1 (>= min_loops 1)
    should_stop = should_stop_retrieval(gain_result, loop_step=1, min_loops=1)
    
    assert should_stop is True

def test_judge_node_should_continue_min_loops_not_met():
    """
    Case 3: GainScore < Threshold (已收敛) 但 Loop < Min -> 应该继续 (返回 False)
    """
    # Mock result: Low score, converged
    gain_result = GainScoreResult(
        score=0.1,
        is_converged=True,
        metrics={},
        reason="Low gain"
    )
    
    # Loop 0 (< min_loops 1)
    should_stop = should_stop_retrieval(gain_result, loop_step=0, min_loops=1)
    
    assert should_stop is False
