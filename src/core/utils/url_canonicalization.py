"""
URL canonicalization utilities.

Phase2 contract: url_canonicalization_version="url_v1"
Rules (v1):
- lowercase scheme + host
- drop query + fragment
- strip trailing slash from path
"""

from urllib.parse import urlparse, urlunparse

URL_CANONICALIZATION_VERSION = "url_v1"


def canonicalize_url(url: str) -> str:
    try:
        parsed = urlparse(url or "")
        scheme = (parsed.scheme or "").lower()
        netloc = (parsed.netloc or "").lower()
        path = (parsed.path or "").rstrip("/")
        normalized = parsed._replace(scheme=scheme, netloc=netloc, path=path, query="", fragment="")
        return urlunparse(normalized)
    except Exception:
        return (url or "").rstrip("/")

