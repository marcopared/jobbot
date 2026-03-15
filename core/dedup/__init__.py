"""
Deduplication utilities for v1 ingestion.

- Normalization: deterministic lowercase forms for title, company, location, apply URL
- Hash: deterministic dedup_hash from normalized fields
- Similarity: fuzzy diagnostics only; never used for merge decisions
"""

from core.dedup.hash import compute_dedup_hash, compute_dedup_hash_from_raw
from core.dedup.normalization import (
    canonicalize_apply_url,
    normalize_company,
    normalize_location,
    normalize_title,
)
from core.dedup.similarity import format_similarity_diagnostic, similarity_ratio

__all__ = [
    "canonicalize_apply_url",
    "compute_dedup_hash",
    "compute_dedup_hash_from_raw",
    "format_similarity_diagnostic",
    "normalize_company",
    "normalize_location",
    "normalize_title",
    "similarity_ratio",
]
