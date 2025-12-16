"""
Chief Editor (Layer 3).
Role: Assemble final report and handle unresolvable conflicts.
Hardware Point 5: "Unresolvable Conflict Handling".
"""
import logging
from typing import Dict, Optional
from .state import ReportOutline
from .auditor import AuditResult

logger = logging.getLogger(__name__)

class ChiefEditor:
    """
    Assembles the final report from drafted sections.
    Annotates unresolvable conflicts flagged by the Auditor.
    """
    
    def assemble_report(
        self, 
        outline: ReportOutline, 
        drafts: Dict[str, str], 
        audit_results: Optional[Dict[str, AuditResult]] = None
    ) -> str:
        """
        Combine Introduction, Sections, and Conclusion.
        Append Editor's Notes if audit failed.
        """
        parts = []
        
        # 1. Title & Header
        parts.append(f"# {outline.title}\n")
        
        # 2. Introduction
        if outline.introduction:
            parts.append(f"## Introduction\n{outline.introduction}\n")
            
        # 3. Sections
        for section in outline.sections:
            content = drafts.get(section.id, "(Section content missing)")
            parts.append(f"## {section.title}\n{content}\n")
            
            # Check for Audit Conflicts for this section (if structured that way)
            # OR check global conflicts.
            # Currently AuditResult might be global or per-section. 
            # The Auditor usually compares "Draft vs Previous". 
            # Let's assume audit_results is keyed by section_id or is a list.
            # For simplicity in Layer 3, we often check the LAST audit result for a section.
            
            if audit_results and section.id in audit_results:
                res = audit_results[section.id]
                if res.conflict_detected:
                     note = self._format_conflict_note(res)
                     parts.append(note)

        # 4. Conclusion
        if outline.conclusion:
            parts.append(f"## Conclusion\n{outline.conclusion}")
            
        return "\n".join(parts)

    def _format_conflict_note(self, res: AuditResult) -> str:
        """Format a warning block for the reader."""
        return f"""
> [!WARNING] Editor's Note: Consistency Check Failed
> The system detected a potential contradiction in this section regarding:
> *{res.conflict_details}*
> Please verify sources independently.
"""
