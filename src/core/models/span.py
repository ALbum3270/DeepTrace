from pydantic import BaseModel, Field
from typing import Optional

class EvidenceSpan(BaseModel):
    """
    Immutable reference to a specific text span within an Evidence.
    Format: [Ev{evidence_id}#c{chunk_index}@{content_hash}]
    """
    evidence_id: str
    chunk_index: int
    content: str
    content_hash: str # Short hash (e.g. first 6 chars of sha256)
    start_char: int = 0
    end_char: int = 0
    
    @property
    def citation_id(self) -> str:
        """Returns the immutable citation ID string."""
        return f"[Ev{self.evidence_id}#c{self.chunk_index}@{self.content_hash}]"

    def __repr__(self) -> str:
        return self.citation_id
