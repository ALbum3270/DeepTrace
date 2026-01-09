"""
Phase1 - BuildDocumentSnapshotNode
Takes cleaned_text and metadata to build a DocumentSnapshot payload.
"""

import hashlib
import datetime
from typing import Dict, Any

from langchain_core.runnables import RunnableConfig

from src.core.models.phase1 import DocumentSnapshot
from src.config.topic_settings import topic_settings  # placeholder if needed
import yaml
from pathlib import Path


def _load_normalization_version():
    spec_path = Path("config/normalization_spec.yaml")
    if spec_path.exists():
        try:
            data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
            return data.get("normalization_version", "unknown")
        except Exception:
            return "unknown"
    return "unknown"


def _digest(text: str, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    h.update((text or "").encode("utf-8"))
    return h.hexdigest()


async def build_document_snapshot_node(state: Dict[str, Any], config: RunnableConfig):
    cleaned_text = state.get("cleaned_text", "")
    doc_id = state.get("doc_id") or _digest(cleaned_text)[:12]
    final_url = state.get("final_url") or state.get("url") or ""
    extractor_version = state.get("extractor_version", "")
    doc_quality_flags = state.get("doc_quality_flags", [])

    normalization_version = _load_normalization_version()

    text_digest = _digest(cleaned_text)
    content_hash = text_digest
    doc_key_preview = _digest(final_url) if final_url else text_digest
    doc_version_id_preview = _digest(doc_key_preview + content_hash)

    snapshot = DocumentSnapshot(
        doc_id=doc_id,
        final_url=final_url,
        cleaned_text=cleaned_text,
        text_digest=text_digest,
        normalization_version=normalization_version,
        content_hash=content_hash,
        doc_key_preview=doc_key_preview,
        doc_version_id_preview=doc_version_id_preview,
        extractor_version=extractor_version,
        doc_quality_flags=doc_quality_flags,
        sentence_splitter_backend=state.get("sentence_splitter_backend"),
        sentence_splitter_version=state.get("sentence_splitter_version"),
        chunk_splitter_name=state.get("chunk_splitter_name"),
        chunk_splitter_version=state.get("chunk_splitter_version"),
        chunk_splitter_params=state.get("chunk_splitter_params") or {},
    )

    return {
        "document_snapshot": snapshot.dict(),
        "doc_id": doc_id,
        "text_digest": text_digest,
        "doc_key_preview": doc_key_preview,
        "doc_version_id_preview": doc_version_id_preview,
    }
