"""
Fuzzy similarity for dedup diagnostics only.

v1: Never used to define canonical uniqueness. Only for logs, warnings,
operator review support.
"""

import difflib


def similarity_ratio(a: str, b: str) -> float:
    """
    Return a similarity ratio between 0 and 1.
    Uses difflib.SequenceMatcher for character-level similarity.
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def format_similarity_diagnostic(
    company_a: str,
    company_b: str,
    title_a: str,
    title_b: str,
    threshold: float = 0.85,
) -> dict | None:
    """
    Return a diagnostic dict if similarity exceeds threshold.
    For logging/operator review only. Does not affect dedup decisions.
    """
    company_ratio = similarity_ratio(company_a, company_b)
    title_ratio = similarity_ratio(title_a, title_b)
    if company_ratio >= threshold or title_ratio >= threshold:
        return {
            "company_similarity": round(company_ratio, 3),
            "title_similarity": round(title_ratio, 3),
            "company_a": company_a[:80],
            "company_b": company_b[:80],
            "title_a": title_a[:80],
            "title_b": title_b[:80],
        }
    return None
