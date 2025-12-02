import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from src.core.models.events import EventNode, EventStatus
from src.agents.timeline_deduplicator import deduplicate_events

@pytest.mark.asyncio
async def test_dedup_mixed_fusion():
    """Test fusion of News and Social Media events."""
    
    # Event 1: Official News (Backbone)
    news_event = EventNode(
        title="Game Science Announces Black Myth Wukong Release Date",
        description="Game Science officially announced that Black Myth Wukong will be released on August 20, 2024. The game is highly anticipated.",
        time=datetime(2024, 6, 8, 10, 0),
        source="Sina News",
        confidence=0.9,
        evidence_ids=["ev_news_1"]
    )
    
    # Event 2: Social Media (Perspective) - Same event, different tone
    social_event = EventNode(
        title="Wukong Release Date Finally Here!",
        description="OMG finally! August 20th! I can't wait to play this masterpiece. The graphics look insane.",
        time=datetime(2024, 6, 8, 10, 30), # Close time
        source="Weibo User @GamerBoy",
        confidence=0.7,
        evidence_ids=["ev_social_1"]
    )
    
    events = [news_event, social_event]
    
    # Mock similarity to be > 0.6 to trigger LLM check
    # Mock LLM to return True
    with patch('src.agents.timeline_deduplicator.calculate_similarity', return_value=0.7), \
         patch('src.agents.timeline_deduplicator.are_events_duplicate_llm', return_value=True):
        
        merged_events, open_questions = await deduplicate_events(events)
    
    assert len(merged_events) == 1
    merged = merged_events[0]
    
    # Check Title (Should be News title)
    assert merged.title == news_event.title
    
    # Check Description (Should contain both)
    assert news_event.description in merged.description
    assert "【补充视角】" in merged.description
    assert social_event.description in merged.description
    
    # Check Evidence IDs
    assert "ev_news_1" in merged.evidence_ids
    assert "ev_social_1" in merged.evidence_ids
    
    # Check Source (Should be News)
    assert merged.source == news_event.source

@pytest.mark.asyncio
async def test_dedup_conflict_resolution():
    """Test conflict detection (Date mismatch)."""
    
    # Event A: Says date is Aug 20
    event_a = EventNode(
        title="Black Myth Wukong Release Date",
        description="Release date confirmed for August 20.",
        time=datetime(2024, 6, 8),
        source="Official Site",
        confidence=0.9
    )
    
    # Event B: Says date is Dec 25 (Conflict > 2 days)
    event_b = EventNode(
        title="Wukong Delayed to Christmas?",
        description="Rumors say Wukong release is delayed to December 25.",
        time=datetime(2024, 12, 25), # Huge difference
        source="Rumor Mill",
        confidence=0.6
    )
    
    events = [event_a, event_b]
    
    # Case 1: Delta > 2 days -> Should SKIP merge (regardless of similarity)
    # We don't even need to mock similarity because the time filter happens BEFORE similarity check
    merged_events, open_questions = await deduplicate_events(events)
    
    assert len(merged_events) == 2 # Should NOT merge
    assert len(open_questions) == 0 # No conflict generated because we skipped comparison
    
    # Case 2: Delta <= 2 days but > 1 day -> Should MERGE and FLAG
    
    event_c = EventNode(
        title="Black Myth Wukong Release Date",
        description="Release date is August 22.",
        time=datetime(2024, 6, 10), # Delta = 2 days
        source="US Blog",
        confidence=0.8
    )
    
    events_2 = [event_a, event_c]
    
    # Mock similarity to force merge path
    with patch('src.agents.timeline_deduplicator.calculate_similarity', return_value=0.9):
        merged_events_2, open_questions_2 = await deduplicate_events(events_2)
    
    # Should merge
    assert len(merged_events_2) == 1
    
    # Should generate OpenQuestion (delta > 1)
    assert len(open_questions_2) == 1
    assert "存在争议" in open_questions_2[0].question
