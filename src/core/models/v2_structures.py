"""
V2 Data Structures for Extraction.
Defines the output schema for the LLM extraction step.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class ExtractedEvent(BaseModel):
    """A single timeline event extracted from text."""
    date: str = Field(description="Date of the event in YYYY-MM-DD, YYYY-MM, or YYYY format. Use 'Unknown' if not found.")
    title: str = Field(description="Short, neutral headline of the event (5-10 words).")
    description: str = Field(description="Detailed description of what happened (1-2 sentences).")
    source_url: str = Field(description="The source URL where this information was found.", default="Unknown")
    confidence: float = Field(description="0.0-1.0 confidence score based on source clarity.", default=0.5)


class SearchConfiguration(BaseModel):
    """Configuration for search execution."""
    queries: List[str] = Field(description="List of optimized search queries (3-5 max).")
    reasoning: str = Field(description="Why these queries were chosen.", default="")

class ExtractionResult(BaseModel):
    """Collection of extracted events."""
    events: List[ExtractedEvent] = Field(default_factory=list)


class ClarificationResult(BaseModel):
    """Clarification decision for the initial query."""
    needs_clarification: bool = Field(description="Whether the query is ambiguous.")
    clarified_objective: str = Field(description="Refined objective to use for research.")
    confirmation_message: str = Field(
        description="User-facing confirmation of the chosen scope."
    )
    questions: List[str] = Field(
        default_factory=list, description="Clarifying questions to ask the user."
    )
