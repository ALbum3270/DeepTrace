
from src.agents.swarm.editor import ChiefEditor
from src.agents.swarm.state import ReportOutline, SectionPlan
from src.agents.swarm.auditor import AuditResult

def test_editor_clean_assembly():
    """Test standard assembly without conflicts"""
    editor = ChiefEditor()
    outline = ReportOutline(
        title="Test Report",
        introduction="Intro text.",
        sections=[SectionPlan(id="s1", title="Section 1", description="desc")],
        conclusion="Conclusion text."
    )
    drafts = {"s1": "Body of section 1."}
    
    report = editor.assemble_report(outline, drafts)
    
    assert "# Test Report" in report
    assert "## Introduction" in report
    assert "Body of section 1." in report
    assert "## Conclusion" in report
    assert "Editor's Note" not in report

def test_editor_conflict_annotation():
    """Test appending warning note for disputed sections"""
    editor = ChiefEditor()
    outline = ReportOutline(
        title="Conflict Report",
        introduction="",
        sections=[SectionPlan(id="s1", title="S1", description="")],
        conclusion=""
    )
    drafts = {"s1": "Content."}
    audit_results = {
        "s1": AuditResult(
            passed=False, 
            conflict_detected=True, 
            conflict_details="Date mismatch: 2023 vs 2024"
        )
    }
    
    report = editor.assemble_report(outline, drafts, audit_results)
    
    assert "Content." in report
    assert "Editor's Note: Consistency Check Failed" in report
    assert "Date mismatch: 2023 vs 2024" in report

def test_editor_missing_section():
    """Test handling of missing section drafts"""
    editor = ChiefEditor()
    outline = ReportOutline(
        title="Incomplete", introduction="",
        sections=[SectionPlan(id="s1", title="S1", description="")],
        conclusion=""
    )
    drafts = {} # Empty
    
    report = editor.assemble_report(outline, drafts)
    assert "(Section content missing)" in report

def test_editor_mixed_scenario():
    """Test mixed scenario: Section 1 passed, Section 2 disputed"""
    editor = ChiefEditor()
    outline = ReportOutline(
        title="Mixed Report", introduction="",
        sections=[
            SectionPlan(id="s1", title="S1", description=""),
            SectionPlan(id="s2", title="S2", description="")
        ],
        conclusion=""
    )
    drafts = {
        "s1": "Clean content.",
        "s2": "Disputed content."
    }
    audit_results = {
        "s1": AuditResult(passed=True, conflict_detected=False),
        "s2": AuditResult(passed=False, conflict_detected=True, conflict_details="Entity Clash")
    }
    
    report = editor.assemble_report(outline, drafts, audit_results)
    
    # Check S1 is clean
    assert "Clean content." in report
    # Check S1 has NO warning (naive string check might fail if warning is global, 
    # but our logic appends warning immediately after section)
    # Let's check relative positions or just presence count
    
    # Check S2 has warning
    assert "Disputed content." in report
    assert "Editor's Note: Consistency Check Failed" in report
    assert "Entity Clash" in report
    
    # Ensure warning appears only once (for s2)
    assert report.count("Editor's Note") == 1
