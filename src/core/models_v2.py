"""
Supervisor Command Schemas.
Defines the structure of tools/commands the Supervisor can invoke.
"""

from typing import Optional, List
from pydantic import BaseModel, Field

class ConductResearch(BaseModel):
    """
    Delegate a specific research topic to a specialized Worker.
    Use this when you need more information to answer the user's objective.
    """
    topic: str = Field(description="The specific research topic or query to investigate.")
    reasoning: str = Field(description="Why this research is necessary given the current state.")
    mode: str = Field(description="Research mode: breadth or depth.", default="breadth")

class FinalAnswer(BaseModel):
    """
    Provide the final answer to the user's objective.
    Use this when you have sufficient information or cannot proceed further.
    """
    content: str = Field(description="The comprehensive answer or report addressing the user's goal.")
    citation_summary: Optional[str] = Field(description="Summary of key sources used.", default=None)

class ResolveConflict(BaseModel):
    """
    Delegate a conflict to the Debater for adjudication.
    Use this when you find contradictory information from different sources.
    """
    topic: str = Field(description="The specific subject of the conflict (e.g. 'Python 4.0 Release Date')")
    claims: List[str] = Field(description="List of conflicting statements found (e.g. ['Source A says 2024', 'Source B says Never']).")
    source_ids: List[str] = Field(description="IDs or Names of sources supporting each claim (e.g. ['[1]', '[2]']).")


class BreadthResearch(BaseModel):
    """Explore a wider surface area for the topic."""
    topic: str = Field(description="High-level topic to explore broadly.")
    reasoning: str = Field(description="Why breadth exploration is needed.")


class DepthResearch(BaseModel):
    """Go deep on a specific sub-question."""
    topic: str = Field(description="Focused sub-question to investigate deeply.")
    reasoning: str = Field(description="Why depth investigation is needed.")
