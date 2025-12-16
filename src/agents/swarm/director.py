"""
Director Agent (Planner).
Role: Analyze clustered events and verified claims to generate a structured ReportOutline.
Contract 3 Enforcer: Must assign `conflict_policy` to sections with disputed claims.
"""
from typing import List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from ...llm.factory import init_json_llm
from .state import SwarmState, ReportOutline, SectionPlan

class DirectorAgent:
    """
    The Director orchestrates the report structure.
    It takes raw events and claims, and produces a JSON execution plan.
    """
    
    def __init__(self):
        self.llm = init_json_llm(temperature=0.2) # Low temp for structured plan
        self.parser = PydanticOutputParser(pydantic_object=ReportOutline)
        
    def create_outline(self, state: SwarmState) -> ReportOutline:
        """
        Main entry point for Director.
        """
        # 1. Prepare Context
        events_context = self._format_events(state["events"])
        claims_context = self._format_claims(state["claims"])
        topic = state["topic"]
        
        # 2. Build Prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_system_prompt()),
            ("user", f"Topic: {topic}\n\nEvents Timeline:\n{events_context}\n\nKey Claims:\n{claims_context}")
        ])
        
        # 3. Invoke LLM
        chain = prompt | self.llm | self.parser
        outline = chain.invoke({})
        
        return outline

    def _format_events(self, events: List[Any]) -> str:
        """Format events for LLM input, emphasizing clusters (if they were clustered)."""
        # If input is raw EventNodes, just list them. 
        # Ideally, we pass "EventClusters" here, but SwarmState currently takes List[EventNode].
        # We assume events are already sorted/processed.
        lines = []
        for i, e in enumerate(events):
            time_str = e.time.strftime("%Y-%m-%d") if e.time else "Unknown Date"
            lines.append(f"{i+1}. [{time_str}] {e.title}: {e.description} (ID: {e.id})")
        return "\n".join(lines)

    def _format_claims(self, claims: List[Any]) -> str:
        lines = []
        for i, c in enumerate(claims):
            status = c.status.upper() # VERIFIED / DISPUTED
            lines.append(f"C{i+1} [{status}] {c.content} (ID: {c.id})")
        return "\n".join(lines)

    def _get_system_prompt(self) -> str:
        return """You are the **Director**, the chief planner of an investigative report swarm.
Your goal is to create a detailed `ReportOutline` based on the provided Event Timeline and Key Claims.

**CRITICAL INSTRUCTIONS (Contract 3 - Conflict Policy)**:
1.  **Structure**: Create logical sections that tell the chronological story or analyze key themes.
2.  **Claim Assignment**: Assign relevant Claim IDs (`assigned_claim_ids`) to each section.
3.  **Conflict Handling**:
    - If a section involves **DISPUTED** claims or conflicting events:
    - You MUST set `conflict_policy="present_both"`.
    - You MUST list the disputed Claim IDs in `disputed_claim_ids`.
    - If evidence is completely contradictory with no resolution, set `conflict_policy="no_conclusion"`.
    - For normal factual sections, Use `conflict_policy="present_both"` (default safety) or strict fact mode. (Actually schema says present_both/no_conclusion literal, so default to present_both).

**Output Format**:
You must output a valid JSON object matching the `ReportOutline` schema.
{
  "title": "Report Title",
  "introduction": "Brief intro...",
  "sections": [
    {
      "id": "sec_1",
      "title": "The Beginning",
      "description": "Covering the start of the event...",
      "assigned_event_ids": ["uuid-1", "uuid-2"],
      "assigned_claim_ids": ["uuid-c1"],
      "disputed_claim_ids": [],
      "conflict_policy": "present_both" 
    }
  ],
  "conclusion": "Summary..."
}
"""
