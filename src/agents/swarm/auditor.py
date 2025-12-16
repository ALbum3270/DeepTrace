"""
Consistency Auditor (Layer 3).
Role: Check for cross-section contradictions (Entity & Date).
Hardware Point 7: "Cross-Section Entity/Date Check".
"""
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from ...llm.factory import init_json_llm

logger = logging.getLogger(__name__)

class AuditResult(BaseModel):
    """Output from Consistency Auditor."""
    passed: bool = Field(..., description="True if no contradictions found")
    conflict_detected: bool = Field(..., description="True if contradictions exist")
    conflict_details: Optional[str] = Field(None, description="Description of the conflict")
    suggested_fix: Optional[str] = Field(None, description="How to resolve the conflict")

class ConsistencyAuditor:
    """
    Audits the current draft against previous sections to ensure consistency.
    """
    
    def __init__(self):
        # Use JSON LLM
        self.llm = init_json_llm(temperature=0.0)
        self.parser = PydanticOutputParser(pydantic_object=AuditResult)
        
    def check_consistency(self, current_draft: str, previous_drafts: List[str]) -> AuditResult:
        """
        Compare current draft against all previous drafts.
        """
        if not previous_drafts:
            # No context to contradict
            return AuditResult(passed=True, conflict_detected=False)

        # Optimization: Concatenate previous drafts (might need truncation if too long)
        # For MVP, we assume manageable length or take last N sections.
        context = "\n\n".join([f"--- Previous Section ---\n{d}" for d in previous_drafts[-3:]])
        
        system_prompt = self._get_system_prompt()
        user_prompt = f"""
Previous Context:
{context}

Current Draft (to audit):
{current_draft}

Task: Check for Entity and Date inconsistencies.
"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt)
        ])
        
        chain = prompt | self.llm | self.parser
        return chain.invoke({})

    def _get_system_prompt(self) -> str:
        return """You are the **Consistency Auditor**.
Your goal is to ensure the report remains consistent across sections.

**Checklist (Hardware Point 7)**:
1.  **Date Consistency**: Does the timeline flow logically? 
    -   Example Conflict: Section 1 says "Event happened in 2023", Section 2 says "In 2021 (the event year)..." without explaining flashback.
2.  **Entity Consistency**: Are names/roles consistent?
    -   Example Conflict: Section 1 says "John Doe, CEO of X", Section 2 says "John Doe, the intern at X".

**Output Schema**:
Return JSON:
{
  "passed": bool,
  "conflict_detected": bool,
  "conflict_details": "Explain strict contradiction...",
  "suggested_fix": "Change X to Y..."
}

**Rule**:
- Only flag **Explicit Contradictions**.
- Do not flag new information as a conflict.
"""
