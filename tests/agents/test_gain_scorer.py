import sys
import os
sys.path.append(os.getcwd())

import pytest
from src.agents.gain_scorer import calculate_gain_score
from src.core.models.timeline import Timeline
from src.core.models.events import EventNode
from src.core.models.comments import CommentScore

def test_gain_score_initial():
    """Test initial run (no previous stats)"""
    timeline = Timeline(events=[EventNode(title="E1", description="C1", evidence_ids=[])], open_questions=[])
    scores = []
    
    result = calculate_gain_score(timeline, scores, previous_stats=None)
    
    assert result.score == 100.0
    assert result.is_converged is False
    assert result.metrics["num_events"] == 1

def test_gain_score_significant_change():
    """Test significant change (new events and comments)"""
    # Previous: 1 event, 0 comments
    prev_stats = {"num_events": 1, "num_high_comments": 0, "avg_confidence": 0.5}
    
    # Current: 3 events, 2 high comments
    events = [
        EventNode(title="E1", description="C1", evidence_ids=[], confidence=0.8),
        EventNode(title="E2", description="C2", evidence_ids=[], confidence=0.9),
        EventNode(title="E3", description="C3", evidence_ids=[], confidence=0.7),
    ]
    timeline = Timeline(events=events, open_questions=[])
    
    scores = [
        CommentScore(comment_id="c1", evidence_id="e1", total_score=0.9, reason="Good"),
        CommentScore(comment_id="c2", evidence_id="e2", total_score=0.8, reason="Good"),
        CommentScore(comment_id="c3", evidence_id="e3", total_score=0.5, reason="Bad"),
    ]
    
    result = calculate_gain_score(timeline, scores, previous_stats=prev_stats)
    
    # Delta Events: 3 - 1 = 2
    # Delta Comments: 2 - 0 = 2
    # Avg Conf: (0.8+0.9+0.7)/3 = 0.8. Delta Conf: 0.8 - 0.5 = 0.3
    
    # Score = 1.0*2 + 0.5*2 + 5.0*0.3 = 2 + 1 + 1.5 = 4.5
    
    assert result.score == pytest.approx(4.5)
    assert result.is_converged is False
    assert result.metrics["num_events"] == 3

def test_gain_score_converged():
    """Test convergence (little to no change)"""
    # Previous: 3 events, 2 comments
    prev_stats = {"num_events": 3, "num_high_comments": 2, "avg_confidence": 0.8}
    
    # Current: Same
    events = [
        EventNode(title="E1", description="C1", evidence_ids=[], confidence=0.8),
        EventNode(title="E2", description="C2", evidence_ids=[], confidence=0.9),
        EventNode(title="E3", description="C3", evidence_ids=[], confidence=0.7),
    ]
    timeline = Timeline(events=events, open_questions=[])
    
    scores = [
        CommentScore(comment_id="c1", evidence_id="e1", total_score=0.9, reason="Good"),
        CommentScore(comment_id="c2", evidence_id="e2", total_score=0.8, reason="Good"),
    ]
    
    result = calculate_gain_score(timeline, scores, previous_stats=prev_stats)
    
    # Delta Events: 0
    # Delta Comments: 0
    # Delta Conf: 0
    
    # Score = 0
    
    assert result.score == pytest.approx(0.0)
    assert result.is_converged is True
