
import pytest
from unittest.mock import patch, MagicMock
from src.agents.swarm.state import ReportOutline, SectionPlan
from src.agents.swarm.critic import CritiqueResult
from src.agents.swarm.auditor import AuditResult
from src.agents.swarm.graph import create_swarm_graph

@patch("src.agents.swarm.graph.director")
@patch("src.agents.swarm.graph.writer")
@patch("src.agents.swarm.graph.critic")
@patch("src.agents.swarm.graph.auditor")
@patch("src.agents.swarm.graph.editor")
@pytest.mark.asyncio
async def test_full_graph_flow_with_audit_conflict(mock_editor, mock_auditor, mock_critic, mock_writer, mock_director):
    """
    Test flow where Auditor detects a conflict, ensuring it propagates to state.
    """
    # 1. Setup Mocks
    mock_director.create_outline.return_value = ReportOutline(
        title="T", introduction="I",
        sections=[SectionPlan(id="s1", title="S1", description="D1")],
        conclusion="C"
    )
    mock_writer.write_section.return_value = "Draft_S1"
    
    # Critic passes immediately
    mock_critic.verify_section.return_value = CritiqueResult(
        score=9.0, feedback="", nli_state="ENTAIL", revision_needed=False
    )
    
    # Auditor: DETECTS CONFLICT
    mock_auditor.check_consistency.return_value = AuditResult(
        passed=False, conflict_detected=True, conflict_details="Date Mismatch"
    )

    # Editor: Mocks assembly (we just check if it was called with correct args)
    mock_editor.assemble_report.return_value = "Final Report With Note"
    
    # 2. Run
    app = create_swarm_graph()
    inputs = {"topic": "Test", "events": [], "claims": [], "evidences": []}
    final_state = await app.ainvoke(inputs)
    
    # 3. Verify
    # Check Auditor was called
    assert mock_auditor.check_consistency.call_count == 1
    
    # Check State contains audit results (This is the key integration point)
    assert "s1" in final_state["audit_results"]
    assert final_state["audit_results"]["s1"].conflict_detected is True
    
    # Check Editor received the audit results
    # args: (outline, drafts, audit_results)
    call_args = mock_editor.assemble_report.call_args
    assert call_args is not None
    # args[0] is outline, args[1] is drafts, args[2] is audit_results
    assert call_args[0][2]["s1"].conflict_detected is True

@patch("src.agents.swarm.graph.director")
@patch("src.agents.swarm.graph.writer")
@patch("src.agents.swarm.graph.critic")
@patch("src.agents.swarm.graph.auditor")
@patch("src.agents.swarm.graph.editor")
@pytest.mark.asyncio
async def test_full_graph_circuit_breaker(mock_editor, mock_auditor, mock_critic, mock_writer, mock_director):
    """
    Test Circuit Breaker: If Critic ALWAYS fails, loop should break after MAX_REVISIONS.
    """
    # 1. Setup
    mock_director.create_outline.return_value = ReportOutline(
        title="T", introduction="I",
        sections=[SectionPlan(id="s1", title="S1", description="D1")],
        conclusion="C"
    )
    mock_writer.write_section.return_value = "Draft_Fail"
    
    # Critic: ALWAYS FAILS (Revision Needed = True)
    mock_critic.verify_section.return_value = CritiqueResult(
        score=1.0, feedback="Bad", nli_state="CONTRADICT", revision_needed=True
    )
    
    # Auditor/Editor mocks
    mock_auditor.check_consistency.return_value = AuditResult(passed=True, conflict_detected=False)
    mock_editor.assemble_report.return_value = "Final Report Forced"

    # 2. Run
    app = create_swarm_graph()
    inputs = {"topic": "Test", "events": [], "claims": [], "evidences": []}
    # This should NOT hang infinitely
    final_state = await app.ainvoke(inputs)
    
    # 3. Verify
    # Director called once
    mock_director.create_outline.assert_called_once()
    
    # Calculate expected Writer calls:
    # 1 (Initial) + MAX_REVISIONS (4) = 5 total calls
    
    assert mock_writer.write_section.call_count == 4
    assert mock_critic.verify_section.call_count == 4
    
    # Ensure we reached the end
    assert final_state["final_report"] == "Final Report Forced"
