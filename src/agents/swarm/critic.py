"""
Critic Agent (The Gatekeeper).
Role: Verify Writer's output against Evidence and Contracts.
Contract 2 Enforcer: NLI State Machine (ENTAIL / CONTRADICT / NEI).
Review Stages:
1.  Structure & Tone (Rules-based/Lite LLM)
2.  Evidence Verification (NLI)
"""
import logging
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from ...llm.factory import init_json_llm
from .state import SectionPlan

logger = logging.getLogger(__name__)

class CritiqueResult(BaseModel):
    """Structured output from Critic."""
    score: float = Field(..., description="Quality score (0.0-10.0)")
    feedback: str = Field(..., description="Detailed feedback for revision")
    nli_state: Literal["ENTAIL", "CONTRADICT", "NEI"] = Field(..., description="NLI Verification State")
    revision_needed: bool = Field(..., description="Whether revision is required")

class CriticAgent:
    """
    The Critic evaluates a section draft.
    It returns a CritiqueResult.
    """
    
    def __init__(self):
        # Use JSON LLM for structured critique
        self.llm = init_json_llm(temperature=0.0) 
        self.parser = PydanticOutputParser(pydantic_object=CritiqueResult)
        
    def verify_section(self, draft: str, section: SectionPlan, evidences: str) -> CritiqueResult:
        """
        Main verification pipeline.
        """
        # Stage 1: Fast Structural Checks (Local)
        # Check for empty content
        if not draft or len(draft) < 50:
            return CritiqueResult(
                score=0.0,
                feedback="Draft is too short or empty.",
                nli_state="NEI",
                revision_needed=True
            )
            
        # Check for citation pattern [Ev...]
        if "[Ev" not in draft:
             return CritiqueResult(
                score=2.0,
                feedback="Missing citations. Format: [Ev{id}]",
                nli_state="NEI",
                revision_needed=True
            )

        # Stage 2: NLI & Contract Check (LLM)
        check_prompt = self._get_system_prompt()
        user_prompt = f"""
Draft Content:
{draft}

Available Evidence:
{evidences}

Task: Verify if the Draft is fully supported by the Evidence.
"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", check_prompt),
            ("user", user_prompt)
        ])
        
        chain = prompt | self.llm | self.parser
        result = chain.invoke({})
        
        return result

    def _get_system_prompt(self) -> str:
        return """You are the **Citadel Critic**, the gatekeeper of truth.
Your job is to verify a report section against the provided Evidence.

**Evaluation Criteria**:
1.  **NLI Check (Contract 2)**:
    -   **ENTAIL**: Every factual claim in the draft is supported by the Evidence.
    -   **CONTRADICT**: The draft makes claims that explicitly contradict the Evidence.
    -   **NEI (Not Enough Info)**: The draft makes claims NOT found in the Evidence (Hallucination).

2.  **Citation Check**:
    -   Are citations correct? e.g. `[Ev1]` really supports the sentence?

3.  **Tone Check**:
    -   Is the tone objective and clinical?
    -   Did the writer use banned causal words ("caused", "led to") without strong proof?

**Output Schema**:
Return a JSON object:
{
  "score": float (0-10),
  "feedback": "Specific instructions for the writer...",
  "nli_state": "ENTAIL" | "CONTRADICT" | "NEI",
  "revision_needed": bool
}

**Rules**:
- If `nli_state` is CONTRADICT or NEI, `revision_needed` MUST be true.
- If score < 8.0, `revision_needed` MUST be true.
"""
