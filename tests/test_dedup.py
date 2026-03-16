"""Tests for v1 deduplication: normalization, hash, exact vs fuzzy behavior."""

import pytest

from core.dedup import (
    canonicalize_apply_url,
    compute_dedup_hash,
    compute_dedup_hash_from_raw,
    format_similarity_diagnostic,
    normalize_company,
    normalize_location,
    normalize_title,
    similarity_ratio,
)


# --- Normalization ---


def test_normalize_title_strips_and_lowercases():
    assert normalize_title("  Senior Software Engineer  ") == "senior software engineer"
    assert normalize_title("Backend  Engineer") == "backend engineer"


def test_normalize_title_collapses_whitespace():
    assert normalize_title("Software   Engineer") == "software engineer"


def test_normalize_title_none_returns_empty():
    assert normalize_title(None) == ""


def test_normalize_company_strips_and_lowercases():
    assert normalize_company("  Acme Corp  ") == "acme corp"


def test_normalize_location_remote_variants():
    assert normalize_location("Remote") == "remote"
    assert normalize_location("REMOTE") == "remote"
    assert normalize_location("Anywhere") == "remote"
    assert normalize_location("Distributed") == "remote"


def test_normalize_location_preserves_location():
    assert normalize_location("San Francisco, CA") == "san francisco, ca"


def test_normalize_location_none_returns_empty():
    assert normalize_location(None) == ""


# --- Canonical apply URL ---


def test_canonicalize_apply_url_strips_params_and_fragment():
    url = "https://boards.greenhouse.io/acme/jobs/123?utm_source=linkedin#apply"
    assert canonicalize_apply_url(url) == "https://boards.greenhouse.io/acme/jobs/123"


def test_canonicalize_apply_url_strips_trailing_slash():
    assert canonicalize_apply_url("https://example.com/jobs/1/") == "https://example.com/jobs/1"


def test_canonicalize_apply_url_lowercases():
    assert canonicalize_apply_url("HTTPS://Example.COM/jobs/1") == "https://example.com/jobs/1"


def test_canonicalize_apply_url_none_returns_empty():
    assert canonicalize_apply_url(None) == ""


# --- Dedup hash ---


def test_dedup_hash_deterministic():
    h1 = compute_dedup_hash_from_raw(
        company="Acme Corp",
        title="Senior Engineer",
        location="San Francisco",
        apply_url="https://acme.com/jobs/1",
    )
    h2 = compute_dedup_hash_from_raw(
        company="acme corp",
        title="senior engineer",
        location="san francisco",
        apply_url="https://acme.com/jobs/1",
    )
    assert h1 == h2


def test_dedup_hash_different_inputs_different_hash():
    h1 = compute_dedup_hash_from_raw(
        company="Acme",
        title="Engineer",
        location="NYC",
        apply_url="https://acme.com/jobs/1",
    )
    h2 = compute_dedup_hash_from_raw(
        company="Acme",
        title="Engineer",
        location="SF",
        apply_url="https://acme.com/jobs/1",
    )
    assert h1 != h2


def test_dedup_hash_url_variants_same_hash():
    """Equivalent URLs (after canonicalization) produce same hash."""
    h1 = compute_dedup_hash_from_raw(
        company="Acme",
        title="Engineer",
        location="Remote",
        apply_url="https://acme.com/jobs/1",
    )
    h2 = compute_dedup_hash_from_raw(
        company="Acme",
        title="Engineer",
        location="Remote",
        apply_url="https://acme.com/jobs/1/?utm_source=twitter",
    )
    assert h1 == h2


def test_dedup_hash_exact_duplicate_same_hash():
    """Same normalized inputs = same hash."""
    base = {
        "company": "Acme Inc",
        "title": "Backend Engineer",
        "location": "New York, NY",
        "apply_url": "https://boards.greenhouse.io/acme/jobs/123",
    }
    h1 = compute_dedup_hash_from_raw(**base)
    h2 = compute_dedup_hash_from_raw(**base)
    assert h1 == h2


def test_dedup_hash_near_duplicate_different_hash():
    """Slightly different inputs (e.g. company spelling) = different hash.
    Fuzzy never merges; hash is strict.
    """
    h1 = compute_dedup_hash_from_raw(
        company="Acme Inc",
        title="Backend Engineer",
        location="NYC",
        apply_url="https://acme.com/jobs/1",
    )
    h2 = compute_dedup_hash_from_raw(
        company="Acme, Inc.",
        title="Backend Engineer",
        location="NYC",
        apply_url="https://acme.com/jobs/1",
    )
    assert h1 != h2


def test_dedup_hash_non_duplicate_different_hash():
    """Clearly different jobs = different hash."""
    h1 = compute_dedup_hash_from_raw(
        company="Acme",
        title="Engineer",
        location="NYC",
        apply_url="https://acme.com/jobs/1",
    )
    h2 = compute_dedup_hash_from_raw(
        company="Beta",
        title="Designer",
        location="SF",
        apply_url="https://beta.com/jobs/2",
    )
    assert h1 != h2


# --- Fuzzy (diagnostics only) ---


def test_similarity_ratio_identical():
    assert similarity_ratio("Acme Inc", "Acme Inc") == 1.0


def test_similarity_ratio_similar():
    r = similarity_ratio("Acme Inc", "Acme, Inc.")
    assert 0.8 < r < 1.0


def test_similarity_ratio_different():
    assert similarity_ratio("Acme", "Beta") < 0.5


def test_format_similarity_diagnostic_above_threshold():
    d = format_similarity_diagnostic(
        company_a="Acme Inc",
        company_b="Acme Inc",
        title_a="Engineer",
        title_b="Engineer",
        threshold=0.9,
    )
    assert d is not None
    assert d["company_similarity"] == 1.0
    assert d["title_similarity"] == 1.0


def test_format_similarity_diagnostic_below_threshold_returns_none():
    d = format_similarity_diagnostic(
        company_a="Acme",
        company_b="Beta",
        title_a="Engineer",
        title_b="Designer",
        threshold=0.9,
    )
    assert d is None


def test_fuzzy_never_defines_uniqueness():
    """Fuzzy similarity is for diagnostics only; two similar strings get different hashes."""
    h1 = compute_dedup_hash_from_raw(
        company="Acme Inc",
        title="Engineer",
        location="NYC",
        apply_url="https://acme.com/jobs/1",
    )
    h2 = compute_dedup_hash_from_raw(
        company="Acme, Inc.",  # Similar but not identical
        title="Engineer",
        location="NYC",
        apply_url="https://acme.com/jobs/1",
    )
    assert h1 != h2  # Hash is strict; fuzzy does not merge
