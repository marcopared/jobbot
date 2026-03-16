"""Shared word-boundary keyword matching (EPIC 5 hardening).

Avoids false positives like 'java' in 'javascript', 'go' in 'going'/'argo',
'sql' in 'postgresql'/'nosql'. Used by ATS extraction, classification, and scoring.
"""

import re


def word_boundary_pattern(keyword: str) -> re.Pattern[str]:
    """Build regex pattern for whole-word match. Handles multi-word and special chars."""
    escaped = re.escape(keyword)
    # Replace escaped spaces with flexible whitespace for multi-word (e.g. "google cloud")
    pattern = escaped.replace(r"\ ", r"\s+")
    return re.compile(rf"\b{pattern}\b", re.IGNORECASE)


def keyword_in_text(text: str, keyword: str) -> bool:
    """Return True if keyword appears as a whole word in text (case-insensitive)."""
    if not text or not keyword:
        return False
    pat = word_boundary_pattern(keyword)
    return pat.search(text.lower()) is not None


def keywords_in_text(text: str, keywords: set[str]) -> set[str]:
    """Return the subset of keywords that appear as whole words in text."""
    if not text or not keywords:
        return set()
    found: set[str] = set()
    for kw in keywords:
        if keyword_in_text(text, kw):
            found.add(kw)
    return found


def score_keywords_in_text(text: str, kw_weights: dict[str, float]) -> float:
    """Sum weights for keywords that appear as whole words. For classification/domain scoring."""
    if not text:
        return 0.0
    total = 0.0
    for kw, weight in kw_weights.items():
        if keyword_in_text(text, kw):
            total += weight
    return total
