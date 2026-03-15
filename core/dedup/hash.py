"""
Deterministic dedup_hash generation for v1 deduplication.

Hash inputs: normalized_company, normalized_title, normalized_location,
canonical_apply_url (when available).
"""

import hashlib

from core.dedup.normalization import (
    canonicalize_apply_url,
    normalize_company,
    normalize_location,
    normalize_title,
)


def compute_dedup_hash(
    *,
    normalized_company: str,
    normalized_title: str,
    normalized_location: str,
    apply_url: str | None = None,
) -> str:
    """
    Compute deterministic dedup_hash from normalized fields.

    Per SPEC §9: composite hash of normalized_company + normalized_title +
    normalized_location, plus canonical apply URL when available.

    Args:
        normalized_company: Already normalized (lowercase, collapsed whitespace).
        normalized_title: Already normalized.
        normalized_location: Already normalized.
        apply_url: Raw apply URL; will be canonicalized if provided.
    """
    loc = normalized_location if normalized_location else ""
    canonical_url = canonicalize_apply_url(apply_url) if apply_url else ""
    composite = (
        (normalized_company or "")
        + "|"
        + (normalized_title or "")
        + "|"
        + loc
        + "|"
        + canonical_url
    )
    return hashlib.sha256(composite.encode()).hexdigest()


def compute_dedup_hash_from_raw(
    *,
    company: str | None,
    title: str | None,
    location: str | None,
    apply_url: str | None = None,
) -> str:
    """
    Convenience: normalize and compute hash from raw values.
    Use when caller has not already normalized.
    """
    return compute_dedup_hash(
        normalized_company=normalize_company(company),
        normalized_title=normalize_title(title),
        normalized_location=normalize_location(location),
        apply_url=apply_url,
    )
