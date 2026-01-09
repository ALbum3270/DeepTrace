"""
Phase1 - ChunkAndSentenceIndexNode
Splits cleaned_text into chunks and sentences with fixed configs.
Outputs chunk_meta, sentence_meta, IndexManifest.
"""

import hashlib
import datetime
from typing import Dict, Any, List
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnableConfig

from src.core.models.phase1 import ChunkMeta, SentenceMeta, IndexManifest

DEFAULT_CHUNK_PARAMS = {
    "chunk_size": 800,
    "chunk_overlap": 100,
    "separators": ["\n\n", "\n", " ", ""],
}

def _digest(text: str, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    h.update((text or "").encode("utf-8"))
    return h.hexdigest()


def _rule_based_sentence_split(text: str) -> List[str]:
    # simple rule-based splitter; can be swapped for BlingFire backend
    import re
    sentences = re.split(r"(?<=[。！？!?])\s+|(?<=[\.\?!])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


async def chunk_and_sentence_index_node(state: Dict[str, Any], config: RunnableConfig):
    cleaned_text = state.get("cleaned_text") or ""
    doc_id = state.get("doc_id") or _digest(cleaned_text)[:12]

    # Chunking
    splitter_params = DEFAULT_CHUNK_PARAMS.copy()
    splitter = RecursiveCharacterTextSplitter(**splitter_params)
    chunks = splitter.split_text(cleaned_text)
    chunk_meta = []
    offset = 0
    for i, ch in enumerate(chunks):
        start = cleaned_text.find(ch, offset)
        end = start + len(ch)
        offset = end
        chunk_meta.append(
            ChunkMeta(
                chunk_id=f"{doc_id}_chunk_{i}",
                start=start,
                end=end,
                text_digest=_digest(ch),
            ).dict()
        )

    # Sentence splitting (rule-based by default)
    sentences = _rule_based_sentence_split(cleaned_text)
    sentence_meta = []
    cur = 0
    for idx, s in enumerate(sentences):
        start = cleaned_text.find(s, cur)
        end = start + len(s)
        cur = end
        sentence_meta.append(
            SentenceMeta(
                sentence_id=f"{doc_id}_sent_{idx}",
                chunk_id="",  # optionally link to chunk later
                start=start,
                end=end,
                text_digest=_digest(s),
            ).dict()
        )

    manifest = IndexManifest(
        run_id=state.get("run_id", "unknown"),
        normalization_version=state.get("normalization_version", "unknown"),
        chunk_splitter={"name": "recursive_character", "version": "fixed", "params": splitter_params},
        sentence_splitter={"backend": "rule_based", "version": "v1"},
        text_digest_algo="sha256",
        created_at=datetime.datetime.utcnow().isoformat(),
    )

    return {
        "chunk_meta": chunk_meta,
        "sentence_meta": sentence_meta,
        "index_manifest": manifest.dict(),
    }
