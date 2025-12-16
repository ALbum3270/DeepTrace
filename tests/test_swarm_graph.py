
import pytest
from unittest.mock import MagicMock, patch
from src.agents.swarm.state import SwarmState, ReportOutline, SectionPlan
from src.agents.swarm.critic import CritiqueResult
# We need to test the logic functions in graph.py, not necessarily the compiled graph 
# because compiling requires full LangGraph setup which might be complex to mock.
# We will test the NODE functions and EDGE logic directly.
from src.agents.swarm.graph import (
    director_node, writer_node, critic_node, should_continue, next_section_node,
    MAX_REVISION_LOOPS_PER_SECTION, create_swarm_graph
)

def get_mock_state():
    return SwarmState(
        topic="T", events=[], claims=[], evidences=[],
        outline=ReportOutline(
            title="T", introduction="I",
            sections=[
                SectionPlan(id="s1", title="S1", description="D1"),
                SectionPlan(id="s2", title="S2", description="D2")
            ],
            conclusion="C"
        ),
        current_section_idx=0,
        draft_sections={},
        critique_feedback=None,
        revision_count=0,
        global_revision_count=0,
        final_report="",
        open_questions=[]
    )

def test_router_logic_revision_needed():
    """Test that router sends back to writer if revision needed and under budget"""
    state = get_mock_state()
    state["critique_feedback"] = "Fix it"
    state["revision_count"] = 0
    
    next_node = should_continue(state)
    assert next_node == "writer_node"

def test_router_logic_max_revisions_reached():
    """Test Circuit Breaker: Force next section if max revisions reached"""
    state = get_mock_state()
    state["critique_feedback"] = "Fix it"
    state["revision_count"] = MAX_REVISION_LOOPS_PER_SECTION # 4
    
    next_node = should_continue(state)
    assert next_node == "next_section"

def test_router_logic_pass():
    """Test normal progression"""
    state = get_mock_state()
    state["critique_feedback"] = None
    
    next_node = should_continue(state)
    assert next_node == "next_section"

def test_router_logic_finish():
    """Test finishing the report"""
    state = get_mock_state()
    state["current_section_idx"] = 1 # Last section (index 1 of 2)
    # The current logic checks "next_idx < len". 
    # If current is 1, next is 2. Len is 2. 2 < 2 is False.
    # So it should go to finalize.
    
    next_node = should_continue(state)
    assert next_node == "finalize"

@patch("src.agents.swarm.graph.director")
def test_director_node(mock_director):
    """Test Director Node output"""
    mock_director.create_outline.return_value = ReportOutline(
        title="Mock", introduction="", sections=[], conclusion=""
    )
    state = {"topic": "T", "events": [], "claims": []} # Minimal input
    update = director_node(state)
    assert "outline" in update
    assert update["current_section_idx"] == 0

@patch("src.agents.swarm.graph.writer")
def test_writer_node(mock_writer):
    """Test Writer Node output"""
    mock_writer.write_section.return_value = "Content"
    state = get_mock_state()
    
    update = writer_node(state)
    assert "draft_sections" in update
    assert update["draft_sections"]["s1"] == "Content"

@patch("src.agents.swarm.graph.critic")
def test_critic_node_pass(mock_critic):
    """Test Critic Node (Pass scenario)"""
    mock_critic.verify_section.return_value = CritiqueResult(
        score=9.0, feedback="", nli_state="ENTAIL", revision_needed=False
    )
    state = get_mock_state()
    state["draft_sections"] = {"s1": "Draft"}
    
    update = critic_node(state)
    assert update["critique_feedback"] is None
    assert update["revision_count"] == 0

@patch("src.agents.swarm.graph.critic")
def test_critic_node_fail(mock_critic):
    """Test Critic Node (Fail scenario)"""
    mock_critic.verify_section.return_value = CritiqueResult(
        score=5.0, feedback="Bad", nli_state="CONTRADICT", revision_needed=True
    )
    state = get_mock_state()
    state["draft_sections"] = {"s1": "Draft"}
    
    update = critic_node(state)
    assert update["critique_feedback"] == "Bad"
    assert update["revision_count"] == 1 # Incremented from 0

@patch("src.agents.swarm.graph.director")
@patch("src.agents.swarm.graph.writer")
@patch("src.agents.swarm.graph.critic")
def test_full_graph_flow_with_retry(mock_critic, mock_writer, mock_director):
    """
    Functional Test: Simulate a full graph run where:
    Section 1: Fails once (Critique) -> Writes Again -> Passes
    """
    # 1. Setup Mocks
    mock_director.create_outline.return_value = ReportOutline(
        title="T", introduction="I",
        sections=[SectionPlan(id="s1", title="S1", description="D1")],
        conclusion="C"
    )
    mock_writer.write_section.side_effect = ["Draft_V1", "Draft_V2"]
    
    # Critic Behavior: First call fails (Revise), Second call passes (Entail)
    mock_critic.verify_section.side_effect = [
        CritiqueResult(score=4.0, feedback="Fix it", nli_state="CONTRADICT", revision_needed=True),
        CritiqueResult(score=9.0, feedback="", nli_state="ENTAIL", revision_needed=False)
    ]
    
    # 2. Build Graph
    app = create_swarm_graph()
    
    # 3. Invoke
    inputs = {"topic": "Test", "events": [], "claims": [], "evidences": []}
    # Recursion limit needs to be enough for director + writer + critic + writer + critic + finalizer
    # Default is usually 25, which is plenty.
    final_state = app.invoke(inputs)
    
    # 4. Assertions
    # Check that we ended up with the final V2 draft
    assert final_state["draft_sections"]["s1"] == "Draft_V2"
    assert final_state["final_report"] is not None
    assert "Draft_V2" in final_state["final_report"]
    
    # Verify call counts
    assert mock_writer.write_section.call_count == 2
    assert mock_critic.verify_section.call_count == 2
