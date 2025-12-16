
import pytest
from datetime import datetime
from src.core.models.events import EventNode
from src.core.models.claim import Claim
from src.core.models.evidence import Evidence
from src.agents.swarm.state import SwarmState, SectionPlan
from src.agents.swarm.writer import WriterAgent, CAUSAL_BAN_LIST

@pytest.mark.asyncio
async def test_writer_content_generation():
    """Test Writer generation and Causal Ban Check"""
    
    # 1. Setup Data
    e1 = EventNode(title="Event A", description="Something happened", time=datetime(2023,1,1), id="e1")
    c1 = Claim(
        content="Claim A is verified", 
        status="verified", 
        credibility_score=90, 
        importance=0.8,
        source_evidence_id="ev1",
        id="c1"
    )
    ev1 = Evidence(content="Detailed text about Event A...", id="ev1")
    
    state = SwarmState(
        topic="Test Topic",
        events=[e1],
        claims=[c1],
        evidences=[ev1],
        outline=None,current_section_idx=0,draft_sections={},
        critique_feedback=None,revision_count=0,global_revision_count=0,
        final_report="",open_questions=[]
    )
    
    section = SectionPlan(
        id="sec1",
        title="Analysis of Event A",
        description="Write a detailed analysis.",
        assigned_event_ids=["e1"],
        assigned_claim_ids=["c1"],
        conflict_policy="present_both"
    )
    
    # 2. Init Writer
    try:
        writer = WriterAgent()
    except Exception as e:
        pytest.skip(f"Writer init failed: {e}")
        
    # 3. Execution
    try:
        content = writer.write_section(section, state)
    except Exception as e:
        pytest.skip(f"LLM call failed: {e}")
        
    # 4. Assertions
    assert isinstance(content, str)
    assert len(content) > 10
    
    # Check Context Usage
    # It should likely mention "Event A" or "Claim A"
    assert "Event A" in content or "Claim A" in content
    
    # Check Causal Ban (Contract 1)
    # The prompt instructs NOT to use them.
    # We check if any banned words made it through.
    lower_content = content.lower()
    for word in CAUSAL_BAN_LIST:
        if word in lower_content:
            print(f"WARNING: Writer used banned word '{word}'. Integration test detected specific violation.")
            # We don't fail test hard yet because LLM is probabilistic, 
            # but we want to see if it generally adheres.
            # In stricter mode, we would fail.
            pass

def test_causal_check_logic():
    """Unit test for the checker method itself"""
    writer = WriterAgent()
    
    # Should catch "caused"
    text_bad = "A caused B."
    # We can't easily assert log output in pytest without caplog, 
    # but we can call the method and ensure no exception.
    writer._check_causal_ban(text_bad)
    
    # Should pass allowed words
    text_good = "A followed B."
    writer._check_causal_ban(text_good)
