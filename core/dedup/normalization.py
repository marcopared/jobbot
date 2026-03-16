"""
Normalization helpers for v1 deduplication.

Produces deterministic, lowercase forms used in dedup_hash and exact URL matching.
"""

import re
from urllib.parse import urlparse


# Patterns for collapsing whitespace
_WHITESPACE_RE = re.compile(r"\s+")


def _collapse_whitespace(s: str) -> str:
    """Replace runs of whitespace with a single space and strip."""
    return _WHITESPACE_RE.sub(" ", s).strip()


def normalize_title(raw: str | None) -> str:
    """
    Normalize job title for dedup.
    Collapses internal whitespace, strips, lowercases.
    """
    if raw is None:
        return ""
    t = _collapse_whitespace(str(raw).strip())
    return t.lower()


def normalize_company(raw: str | None) -> str:
    """
    Normalize company name for dedup.
    Collapses internal whitespace, strips, lowercases.
    """
    if raw is None:
        return ""
    c = _collapse_whitespace(str(raw).strip())
    return c.lower()


def normalize_location(raw: str | None) -> str:
    """
    Normalize location for dedup.
    Collapses whitespace, strips, lowercases.
    Canonicalizes common "Remote" variants to "remote".
    """
    if raw is None:
        return ""
    loc = _collapse_whitespace(str(raw).strip())
    loc_lower = loc.lower()
    if loc_lower in ("remote", "anywhere", "distributed"):
        return "remote"
    return loc_lower


def canonicalize_apply_url(url: str | None) -> str:
    """
    Canonical form of apply URL for dedup and exact matching.
    Strips query params, fragment, trailing slash. Lowercases.
    Returns empty string for None or invalid URL.
    """
    if url is None or not str(url).strip():
        return ""
    s = str(url).strip()
    try:
        parsed = urlparse(s)
        scheme = (parsed.scheme or "https").lower()
        netloc = (parsed.netloc or "").lower()
        path = (parsed.path or "/").rstrip("/") or "/"
        return f"{scheme}://{netloc}{path}"
    except Exception:
        return ""
