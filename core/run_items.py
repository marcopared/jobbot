"""Canonical ScrapeRun.items_json helpers shared by writers and readers."""

from __future__ import annotations

from typing import Any, Mapping

from core.scraping.base import detect_ats_type


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value.strip()
            continue
        return value
    return None


def _string_or_empty(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_outcome(value: Any) -> str:
    outcome = _string_or_empty(value) or "skipped"
    if outcome == "not_found":
        return "skipped"
    return outcome


def _infer_ats_type(source: str, url: str, apply_url: str | None, item: Mapping[str, Any]) -> str:
    explicit = _string_or_empty(item.get("ats_type"))
    if explicit:
        return explicit
    detected = detect_ats_type(apply_url or url).value
    if detected != "unknown":
        return detected
    return source or "unknown"


def normalize_run_item(
    item: Mapping[str, Any] | None,
    *,
    run_source: str | None = None,
    default_index: int = 0,
) -> dict[str, Any]:
    """Return the canonical ScrapeRun item shape for any legacy or partial row."""
    raw = item if isinstance(item, Mapping) else {}

    source = _string_or_empty(_first_value(raw.get("source"), run_source))
    url = _string_or_empty(
        _first_value(
            raw.get("url"),
            raw.get("source_url"),
            raw.get("listing_url"),
            raw.get("apply_url"),
        )
    )
    apply_url = _string_or_none(_first_value(raw.get("apply_url"), raw.get("url")))
    raw_payload = _first_value(
        raw.get("raw_payload_json"),
        raw.get("raw_payload"),
        raw.get("source_payload_json"),
    )

    normalized = {
        "index": _int_or_default(raw.get("index"), default_index),
        "outcome": _normalize_outcome(raw.get("outcome")),
        "job_id": _string_or_none(raw.get("job_id")),
        "dedup_hash": _string_or_empty(raw.get("dedup_hash")),
        "source": source,
        "source_job_id": _string_or_none(_first_value(raw.get("source_job_id"), raw.get("external_id"))),
        "title": _string_or_empty(raw.get("title")),
        "company_name": _string_or_empty(_first_value(raw.get("company_name"), raw.get("company"))),
        "location": _string_or_none(raw.get("location")),
        "url": url,
        "apply_url": apply_url,
        "ats_type": _infer_ats_type(source, url, apply_url, raw),
        "raw_payload_json": raw_payload if isinstance(raw_payload, (dict, list)) else raw_payload,
    }

    for key in (
        "dedup_reason",
        "reason",
        "backfilled_payload",
        "backfilled_apply_url",
        "source_confidence",
    ):
        if key in raw:
            normalized[key] = raw.get(key)

    return normalized


def normalize_run_items(items: Any, *, run_source: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [
        normalize_run_item(item, run_source=run_source, default_index=index)
        for index, item in enumerate(items, start=1)
        if isinstance(item, Mapping)
    ]


def make_run_item(
    *,
    index: int,
    outcome: str,
    job_id: str | None,
    dedup_hash: str | None,
    source: str,
    source_job_id: str | None,
    title: str | None,
    company_name: str | None,
    location: str | None,
    url: str | None,
    apply_url: str | None,
    ats_type: str | None,
    raw_payload_json: Any,
    **extra: Any,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "index": index,
        "outcome": outcome,
        "job_id": job_id,
        "dedup_hash": dedup_hash,
        "source": source,
        "source_job_id": source_job_id,
        "title": title,
        "company_name": company_name,
        "location": location,
        "url": url,
        "apply_url": apply_url,
        "ats_type": ats_type,
        "raw_payload_json": raw_payload_json,
    }
    item.update(extra)
    return normalize_run_item(item, run_source=source, default_index=index)
