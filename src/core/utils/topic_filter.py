import re
from typing import List, Set

# Minimal default list for backward compatibility; no fallback/auto-allow.
DEFAULT_TOKENS = ["gpt-5", "gpt5", "gpt 5", "gpt-4", "gpt4", "gpt-4o", "gpt 4o", "gpt-4.1", "gpt 4.1"]


def extract_tokens(text: str, extra_tokens: List[str] = None) -> List[str]:
    """
    Extract tokens from text using explicit matches only (no fallback/auto-allow).
    - Uses a regex for gpt-x or gpt-x.x patterns.
    - Also matches provided extra_tokens and DEFAULT_TOKENS.
    Returns an empty list if nothing is found (strict).
    """
    tokens = []
    lower = (text or "").lower()

    # Regex capture for patterns like gpt-5, gpt5, gpt-4.1, gpt 4.1
    for m in re.findall(r"gpt[- ]?(\d(?:\.\d)?)", lower):
        normalized = f"gpt-{m}" if "." in m else f"gpt-{m}"  # normalize to gpt-<number>
        tokens.append(normalized)

    for tok in (extra_tokens or []):
        if tok and tok.lower() in lower:
            tokens.append(tok.lower())

    for tok in DEFAULT_TOKENS:
        if tok in lower:
            tokens.append(tok)

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


def matches_tokens(text: str, tokens: Set[str]) -> bool:
    if not tokens:
        return False  # strict: no tokens means nothing should pass
    lower = (text or "").lower()
    return any(tok in lower for tok in tokens)
