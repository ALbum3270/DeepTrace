"""
Phase 1 schemas (DocumentSnapshot / IndexManifest / FactsIndex v2 / Gate1 report).
These are standalone models and not yet wired into the main graph.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DocumentSnapshot(BaseModel):
    doc_id: str
    final_url: Optional[str] = None
    cleaned_text: str
    text_digest: str
    normalization_version: str
    content_hash: Optional[str] = None
    doc_key_preview: Optional[str] = None
    doc_version_id_preview: Optional[str] = None
    extractor_version: Optional[str] = None
    doc_quality_flags: List[str] = Field(default_factory=list)
    sentence_splitter_backend: Optional[str] = None
    sentence_splitter_version: Optional[str] = None
    chunk_splitter_name: Optional[str] = None
    chunk_splitter_version: Optional[str] = None
    chunk_splitter_params: Dict[str, Any] = Field(default_factory=dict)


class ChunkMeta(BaseModel):
    chunk_id: str
    start: int
    end: int
    text_digest: str


class SentenceMeta(BaseModel):
    sentence_id: str
    chunk_id: str
    start: int
    end: int
    text_digest: str


class IndexManifest(BaseModel):
    run_id: str
    normalization_version: str
    chunk_splitter: Dict[str, Any]
    sentence_splitter: Dict[str, Any]
    text_digest_algo: str
    created_at: str


class EvidenceRef(BaseModel):
    doc_id: str
    chunk_id: Optional[str] = None
    sentence_ids: List[str] = Field(default_factory=list)
    offsets: Optional[List[int]] = None
    evidence_hint: Optional[str] = None  # optional locator hint; not used for Gate1 verification
    evidence_quote: Optional[str] = None  # must be programmatically extracted
    quote_hash: Optional[str] = None
    unlocatable_reason: Optional[str] = None


class EvidenceItem(BaseModel):
    event_id: str
    url: Optional[str] = None
    credibility_tier: Optional[str] = None
    doc_ref: Optional[EvidenceRef] = None


class FactsIndexV2(BaseModel):
    items: List[EvidenceItem] = Field(default_factory=list)
    normalization_version: Optional[str] = None


class Gate1Entry(BaseModel):
    event_id: str
    severity: str
    message: str
    role: Optional[str] = None  # e.g., key_claim


class Gate1Report(BaseModel):
    entries: List[Gate1Entry] = Field(default_factory=list)
    key_claim_locatable_rate: Optional[float] = None

