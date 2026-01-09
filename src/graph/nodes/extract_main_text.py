"""
Phase1 - ExtractMainTextNode
Extracts and cleans main text from raw HTML using multiple backends (trafilatura primary, jusText/readability as fallback).
Outputs cleaned_text plus extractor_version/doc_quality_flags for downstream DocumentSnapshot.
"""

from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

# We avoid adding heavy deps dynamically; simple adapters here
def _try_trafilatura(html: str):
    try:
        import trafilatura
        return trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    except Exception:
        return ""

def _try_justext(html: str):
    try:
        import justext
        from lxml import html as lxml_html
        paragraphs = justext.justext(html, justext.get_stoplist("English"))
        return "\n".join(p.text for p in paragraphs if not p.is_boilerplate)
    except Exception:
        return ""

def _try_readability(html: str):
    try:
        from readability import Document
        doc = Document(html)
        return doc.summary(html_partial=False) or ""
    except Exception:
        return ""


def _try_naive(html: str):
    try:
        # minimal fallback: strip tags
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""


def _choose_text(html: str):
    """
    Try backends in order; return cleaned text and extractor_version, doc_quality_flags.
    """
    flags = []
    text = _try_trafilatura(html)
    version = "trafilatura"
    if not text:
        text = _try_justext(html)
        version = "jusText"
        if not text:
            text = _try_readability(html)
            version = "readability"
            if not text:
                text = _try_naive(html)
                version = "naive"
                if not text:
                    flags.append("extract_failed")
    if text:
        text = text.strip()
    if not text:
        flags.append("empty_cleaned_text")
    return text, version, flags


async def extract_main_text_node(state: Dict[str, Any], config: RunnableConfig):
    """
    Input: state['raw_html']
    Output: cleaned_text, extractor_version, doc_quality_flags
    """
    raw_html = state.get("raw_html") or ""
    if not raw_html:
        return {"cleaned_text": "", "extractor_version": "none", "doc_quality_flags": ["no_input_html"]}

    cleaned_text, extractor_version, flags = _choose_text(raw_html)

    return {
        "cleaned_text": cleaned_text,
        "extractor_version": extractor_version,
        "doc_quality_flags": flags,
    }
