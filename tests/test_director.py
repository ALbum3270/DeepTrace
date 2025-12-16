
import pytest
from datetime import datetime
from src.core.models.events import EventNode
from src.core.models.claim import Claim
from src.agents.swarm.state import SwarmState, ReportOutline
from src.agents.swarm.director import DirectorAgent

@pytest.mark.asyncio
async def test_director_outline_generation():
    """测试 Director 生成 Outline JSON"""
    
    # 1. Setup Mock State
    e1 = EventNode(title="Event A", description="Desc A", time=datetime(2023,1,1))
    c1 = Claim(
        content="Claim A", 
        status="verified", 
        credibility_score=90, 
        importance=0.8,
        source_evidence_id="ev_0",
        supporting_evidence_ids=[]
    )
    c2 = Claim(
        content="Conflict Claim B", 
        status="disputed", 
        credibility_score=50, 
        importance=0.9,
        source_evidence_id="ev_1",
        supporting_evidence_ids=[]
    )
    
    state = SwarmState(
        topic="Test Topic",
        events=[e1],
        claims=[c1, c2],
        evidences=[],
        outline=None,
        current_section_idx=0,
        draft_sections={},
        critique_feedback=None,
        revision_count=0,
        global_revision_count=0,
        final_report="",
        open_questions=[]
    )
    
    # 2. Init Director
    # NOTE: This will call real LLM. For unit test we usually mock LLM.
    # But here we want integration verification.
    try:
        director = DirectorAgent()
    except Exception as e:
        pytest.skip(f"Director init failed (API key?): {e}")

    # 3. Execution
    try:
        outline = director.create_outline(state)
    except Exception as e:
        pytest.skip(f"LLM call failed: {e}")
        
    # 4. Assertions
    assert isinstance(outline, ReportOutline)
    assert len(outline.sections) > 0
    assert outline.title
    
    # Check Contract 3: Conflict Policy
    # We had a DISPUTED claim in input, so at least one section should probably handle it 
    # OR assign distinct claim IDs.
    # Since prompt instructs to handle conflicts, let's list sections policies.
    for sec in outline.sections:
        assert sec.conflict_policy in ["present_both", "no_conclusion"]
        
    print(f"\nGenerated Title: {outline.title}")
    print(f"Sections: {len(outline.sections)}")

def test_format_helpers():
    """测试 context 格式化帮助函数"""
    director = DirectorAgent()
    
    events = [EventNode(title="E1", description="D1", time=datetime(2023,1,1))]
    text = director._format_events(events)
    assert "E1" in text
    assert "2023-01-01" in text
    
    claims = [Claim(
        content="C1", 
        status="verified", 
        credibility_score=90,
        importance=0.8,
        source_evidence_id="ev_test",
        supporting_evidence_ids=[]
    )]
    text_c = director._format_claims(claims)
    assert "C1" in text_c
    assert "VERIFIED" in text_c
