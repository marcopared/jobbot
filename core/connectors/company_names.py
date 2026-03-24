"""Helpers for extracting canonical employer names from provider payloads."""

from typing import Any


def _first_non_empty_str(*values: Any) -> str | None:
    """Return the first non-empty string-ish value."""
    for value in values:
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def _company_from_nested_dict(payload: dict[str, Any], key: str) -> str | None:
    """Return a nested company name from a dict field when present."""
    value = payload.get(key)
    if isinstance(value, dict):
        return _first_non_empty_str(
            value.get("name"),
            value.get("display_name"),
            value.get("company_name"),
        )
    return None


def derive_company_name(
    raw_job: dict[str, Any],
    *,
    configured_company_name: str | None = None,
) -> str:
    """
    Prefer the real employer name from the provider payload.

    Falls back to an explicitly configured company name for known canonical
    ingestion runs, then to ``Unknown`` so provider slugs do not become the
    canonical company by default.
    """
    direct_company = _first_non_empty_str(
        raw_job.get("company"),
        raw_job.get("company_name"),
        raw_job.get("companyName"),
        raw_job.get("organization"),
        raw_job.get("organization_name"),
        raw_job.get("organizationName"),
        raw_job.get("employer"),
        raw_job.get("employer_name"),
        raw_job.get("employerName"),
    )
    if direct_company:
        return direct_company

    for key in ("company", "organization", "employer"):
        nested_company = _company_from_nested_dict(raw_job, key)
        if nested_company:
            return nested_company

    metadata = raw_job.get("metadata")
    if isinstance(metadata, dict):
        metadata_company = _first_non_empty_str(
            metadata.get("company"),
            metadata.get("company_name"),
            metadata.get("companyName"),
            metadata.get("organization_name"),
            metadata.get("organizationName"),
        )
        if metadata_company:
            return metadata_company

    configured = _first_non_empty_str(configured_company_name)
    if configured:
        return configured

    return "Unknown"
