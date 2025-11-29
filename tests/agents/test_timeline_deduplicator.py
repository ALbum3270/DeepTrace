import sys
import os
sys.path.append(os.getcwd())

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.timeline_deduplicator import deduplicate_events
from src.core.models.events import EventNode

@pytest.mark.asyncio
async def test_deduplicate_events_logic():
    # Setup mock events
    event1 = EventNode(
        title="Event A",
        description="This is event A description.",
        time="2024-01-01 10:00",
        confidence=0.8,
        evidence_ids=["ev1"]
    )
    
    event2 = EventNode(
        title="Event A", # Same title, high similarity
        description="This is event A description but slightly different.",
        time="2024-01-01 10:05",
        confidence=0.9,
        evidence_ids=["ev2"]
    )
    
    event3 = EventNode(
        title="Event Omega",
        description="This is a completely different event about something else entirely.",
        time="2024-01-02 10:00",
        confidence=0.7,
        evidence_ids=["ev3"]
    )

    # Test Level 1 Deduplication (High Similarity > 0.85)
    # event1 and event2 have same title, similarity should be 1.0
    
    events = [event1, event2, event3]
    
    # We don't need to mock LLM if similarity is > 0.85 (Level 1 direct match)
    # But wait, logic says > 0.85 is direct match.
    # Let's verify calculate_similarity behavior first or trust standard library.
    
    deduplicated = await deduplicate_events(events)
    
    # Expect event1 and event2 to be merged. event3 remains.
    assert len(deduplicated) == 2
    
    merged_event = deduplicated[0]
    assert merged_event.title == "Event A"
    assert set(merged_event.evidence_ids) == {"ev1", "ev2"}
    assert merged_event.confidence == 0.9 # Max confidence
    
    # Test Level 2 Deduplication (0.6 < Similarity <= 0.85)
    event4 = EventNode(
        title="Event C Start",
        description="Event C started today.",
        time="2024-01-03 10:00",
        confidence=0.8,
        evidence_ids=["ev4"]
    )
    
    event5 = EventNode(
        title="Event C Begin", # Similar but not identical
        description="Event C has begun.",
        time="2024-01-03 10:00",
        confidence=0.8,
        evidence_ids=["ev5"]
    )
    
    # Mock LLM to return True
    with patch("src.agents.timeline_deduplicator.are_events_duplicate_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = True
        
        deduplicated_l2 = await deduplicate_events([event4, event5])
        
        assert len(deduplicated_l2) == 1
        assert set(deduplicated_l2[0].evidence_ids) == {"ev4", "ev5"}
        mock_llm.assert_called_once()
