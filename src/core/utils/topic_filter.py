import re
from typing import List, Set

# Minimal default list for backward compatibility; no fallback/auto-allow.
DEFAULT_TOKENS = []

# Common stop words to filter out
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "as", "is", "was", "are", "were", "been", "be", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might", "must",
    "shall", "can", "need", "this", "that", "these", "those", "it", "its", "they",
    "their", "them", "what", "which", "who", "whom", "when", "where", "why", "how",
    "all", "each", "every", "both", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "about", "into", "through", "during", "before", "after", "above", "below", "up",
    "down", "out", "off", "over", "under", "again", "further", "then", "once", "here",
    "there", "any", "also", "using", "based", "features", "comparison", "key", "main",
    "official", "verified", "date", "release", "please", "research", "provide", "detailed",
    "report", "information", "data", "find", "search", "look", "get", "know", "want",
}


def extract_tokens(text: str, extra_tokens: List[str] = None) -> List[str]:
    """
    Extract tokens from text for topic filtering.
    - Uses a regex for gpt-x or gpt-x.x patterns.
    - Also matches provided extra_tokens and DEFAULT_TOKENS.
    - Falls back to extracting meaningful words (>3 chars, not stop words).
    Returns a list of lowercase tokens.
    """
    tokens = []
    lower = (text or "").lower()

    # Regex capture for patterns like gpt-5, gpt5, gpt-4.1, gpt 4.1
    for m in re.findall(r"gpt[- ]?(\d(?:\.\d)?)", lower):
        normalized = f"gpt-{m}" if "." in m else f"gpt-{m}"  # normalize to gpt-<number>
        tokens.append(normalized)

    # Common tech terms and product names (hyphenated or compound)
    tech_patterns = [
        r"\b(langgraph|langchain|autogpt|babyagi|crewai|openai|anthropic|deepseek|gemini|claude)\b",
        r"\b(semantic[- ]?kernel|agent[- ]?framework|llm[- ]?agent)\b",
        r"\b(gpt-\d+[a-z]?|claude-\d+|gemini-\d+)\b",
    ]
    for pattern in tech_patterns:
        for m in re.findall(pattern, lower):
            if m and m not in tokens:
                tokens.append(m.replace(" ", "-"))

    for tok in (extra_tokens or []):
        if tok and tok.lower() in lower:
            tokens.append(tok.lower())

    for tok in DEFAULT_TOKENS:
        if tok in lower:
            tokens.append(tok)

    # If no specific patterns matched, extract meaningful words
    if not tokens:
        words = re.findall(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)*\b", lower)
        for word in words:
            if len(word) > 3 and word not in STOP_WORDS:
                tokens.append(word)
        # Limit to first 5 most relevant (longest words tend to be more specific)
        tokens = sorted(set(tokens), key=lambda x: -len(x))[:5]

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
