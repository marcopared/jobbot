from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from core.connectors.base import CanonicalJobPayload
from core.dedup import normalize_company, normalize_location, normalize_title
from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend
from core.ingestion.source_policies import get_source_policy
from core.ingestion.sources.base import SourceAdapter
from core.ingestion.types import (
    AcquisitionBatch,
    AcquisitionProvenance,
    AcquisitionRecord,
    AcquisitionRequest,
    FetchMode,
    SourcePolicy,
)


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobBot/ingestion-v2)",
}


@dataclass(frozen=True)
class PublicBoardCandidate:
    external_id: str | None
    source_url: str | None
    title: str | None = None
    company: str | None = None
    location: str | None = None
    description: str | None = None
    apply_url: str | None = None
    posted_at: datetime | None = None
    employment_type: str | None = None
    detail_url: str | None = None
    raw_listing: Mapping[str, Any] = field(default_factory=dict)
    raw_detail: Mapping[str, Any] = field(default_factory=dict)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\xa0", " ")
    cleaned = " ".join(text.split()).strip()
    return cleaned or None


_SPACED_LETTERS_RE = re.compile(r"(?<=\b\w) (?=\w\b)")


def collapse_spaced_letters(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    collapsed = text
    while True:
        updated = _SPACED_LETTERS_RE.sub("", collapsed)
        if updated == collapsed:
            break
        collapsed = updated
    return clean_text(collapsed)


def absolutize_url(base_url: str | None, url: str | None) -> str | None:
    candidate = clean_text(url)
    if not candidate:
        return None
    if base_url:
        return clean_text(urljoin(base_url, candidate))
    return candidate


def normalize_public_url(url: str | None) -> str | None:
    return clean_text(url)


def html_to_text(html: str | None) -> str | None:
    value = clean_text(html)
    if not value:
        return None
    return clean_text(BeautifulSoup(value, "html.parser").get_text(" ", strip=True))


def parse_date(value: str | None, *formats: str) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_json_ld(document: BeautifulSoup) -> list[Any]:
    payloads: list[Any] = []
    for script in document.find_all("script", attrs={"type": "application/ld+json"}):
        raw = clean_text(script.string or script.get_text())
        if not raw:
            continue
        try:
            payloads.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return payloads


def parse_job_posting_json_ld(document: BeautifulSoup) -> Mapping[str, Any] | None:
    for payload in parse_json_ld(document):
        if isinstance(payload, Mapping) and payload.get("@type") == "JobPosting":
            return payload
        if isinstance(payload, Mapping):
            graph = payload.get("@graph")
            if isinstance(graph, list):
                for node in graph:
                    if isinstance(node, Mapping) and node.get("@type") == "JobPosting":
                        return node
    return None


def parse_item_list_json_ld(document: BeautifulSoup) -> list[Mapping[str, Any]]:
    for payload in parse_json_ld(document):
        if isinstance(payload, Mapping):
            graph = payload.get("@graph")
            if isinstance(graph, list):
                for node in graph:
                    if isinstance(node, Mapping) and node.get("@type") == "ItemList":
                        elements = node.get("itemListElement")
                        if isinstance(elements, list):
                            return [item for item in elements if isinstance(item, Mapping)]
        if isinstance(payload, Mapping) and payload.get("@type") == "ItemList":
            elements = payload.get("itemListElement")
            if isinstance(elements, list):
                return [item for item in elements if isinstance(item, Mapping)]
    return []


def make_external_id(source_name: str, url: str | None, fallback: str | None = None) -> str | None:
    candidate = clean_text(fallback)
    if candidate:
        return candidate
    normalized_url = normalize_public_url(url)
    if not normalized_url:
        return None
    parsed = urlparse(normalized_url)
    slug = parsed.path.strip("/") or normalized_url
    return f"{source_name}:{slug}"


def hash_external_id(source_name: str, *parts: Any) -> str:
    normalized = "|".join(clean_text(part) or "" for part in parts)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{source_name}:{digest}"


def extract_record_html(record: AcquisitionRecord) -> str | None:
    artifact_content = record.artifact.content if record.artifact else None
    raw_payload = record.raw_payload
    if isinstance(artifact_content, bytes):
        return artifact_content.decode("utf-8", errors="ignore")
    if isinstance(artifact_content, str):
        return artifact_content
    if isinstance(raw_payload, bytes):
        return raw_payload.decode("utf-8", errors="ignore")
    if isinstance(raw_payload, str):
        return raw_payload
    return None


def build_failure_batch(
    *,
    source_name: str,
    error: str,
    error_type: str = "unsupported_source",
    metadata: Mapping[str, Any] | None = None,
) -> AcquisitionBatch:
    merged_metadata = {"source_name": source_name}
    if metadata:
        merged_metadata.update(dict(metadata))
    return AcquisitionBatch(
        records=[],
        stats={"fetched": 0, "errors": 1},
        error=error,
        error_type=error_type,
        metadata=merged_metadata,
    )


class BasePublicBoardSourceAdapter(SourceAdapter):
    listing_url: str
    use_source_url_as_apply_url: bool = True

    def __init__(
        self,
        *,
        source_name: str,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        resolved_policy = policy or get_source_policy(source_name)
        super().__init__(
            source_name=source_name,
            policy=resolved_policy,
            backend=backend or ScraplingFetchBackend(),
        )

    def acquire(self, **params: Any) -> AcquisitionBatch:
        listing_batch = self.backend.acquire(
            self.source_name,
            request=self.build_listing_request(**params),
        )
        if listing_batch.error and not listing_batch.records:
            return listing_batch

        detail_records: list[AcquisitionRecord] = []
        detail_lookup: dict[str, AcquisitionRecord] = {}
        failures = list(self._extract_failures(listing_batch))
        candidates_by_page: list[tuple[AcquisitionRecord, list[PublicBoardCandidate]]] = []

        for page_record in listing_batch.records:
            html = extract_record_html(page_record)
            if not html:
                continue
            page_candidates = list(self.extract_listings(html=html, page_record=page_record, **params))
            candidates_by_page.append((page_record, page_candidates))
            detail_urls = [
                candidate.detail_url
                for candidate in page_candidates
                if candidate.detail_url
            ]
            if not detail_urls:
                continue
            detail_batch = self.backend.acquire(
                self.source_name,
                request=self.build_detail_request(detail_urls=detail_urls, **params),
            )
            detail_records.extend(detail_batch.records)
            failures.extend(self._extract_failures(detail_batch))
            for detail_record in detail_batch.records:
                key = normalize_public_url(detail_record.provenance.source_url)
                if key:
                    detail_lookup[key] = detail_record

        records: list[AcquisitionRecord] = []
        for page_record, candidates in candidates_by_page:
            for candidate in candidates:
                detail_key = normalize_public_url(candidate.detail_url)
                detail_record = detail_lookup.get(detail_key) if detail_key else None
                enriched = self.enrich_candidate(candidate=candidate, detail_record=detail_record)
                records.append(
                    self._candidate_to_record(
                        page_record=page_record,
                        detail_record=detail_record,
                        candidate=enriched,
                    )
                )

        metadata: dict[str, Any] = {
            "source_name": self.source_name,
            "listing_url": self.listing_url,
        }
        if failures:
            metadata["failures"] = failures

        return AcquisitionBatch(
            records=records,
            stats={
                "fetched": len(records),
                "errors": len(failures),
            },
            error=failures[0]["message"] if failures and not records else None,
            error_type=failures[0]["error_type"] if failures and not records else None,
            metadata=metadata,
        )

    def normalize(self, acquired: AcquisitionRecord | Mapping[str, Any], **context: Any) -> CanonicalJobPayload | None:
        raw_payload = acquired.raw_payload if isinstance(acquired, AcquisitionRecord) else acquired
        if not isinstance(raw_payload, Mapping):
            return None

        title = clean_text(raw_payload.get("title"))
        company = clean_text(raw_payload.get("company"))
        source_url = normalize_public_url(raw_payload.get("source_url"))
        apply_url = normalize_public_url(raw_payload.get("apply_url"))
        if not apply_url and self.use_source_url_as_apply_url:
            apply_url = source_url
        if not title or not company or not (source_url or apply_url):
            return None

        location = clean_text(raw_payload.get("location"))
        description = clean_text(raw_payload.get("description"))
        external_id = make_external_id(
            self.source_name,
            source_url or apply_url,
            fallback=clean_text(raw_payload.get("external_id")),
        )
        if not external_id:
            return None

        posted_at = raw_payload.get("posted_at")
        if not isinstance(posted_at, datetime):
            posted_at = parse_date(clean_text(posted_at))

        return CanonicalJobPayload(
            source_name=self.source_name,
            external_id=external_id,
            title=title,
            company=company,
            location=location,
            employment_type=clean_text(raw_payload.get("employment_type")),
            description=description,
            apply_url=apply_url,
            source_url=source_url or apply_url,
            posted_at=posted_at,
            raw_payload=dict(raw_payload),
            normalized_title=normalize_title(title),
            normalized_company=normalize_company(company),
            normalized_location=normalize_location(location) or None,
        )

    def build_listing_request(self, **params: Any) -> AcquisitionRequest:
        return AcquisitionRequest(
            url=self.listing_url,
            fetch_mode=FetchMode.SIMPLE,
            headers=DEFAULT_HEADERS,
            timeout_ms=int(params.get("timeout_ms", 30_000)),
        )

    def build_detail_request(self, *, detail_urls: Iterable[str], **params: Any) -> AcquisitionRequest:
        return AcquisitionRequest(
            urls=tuple(dict.fromkeys(detail_urls)),
            fetch_mode=FetchMode.SIMPLE,
            headers=DEFAULT_HEADERS,
            timeout_ms=int(params.get("timeout_ms", 30_000)),
        )

    @abstractmethod
    def extract_listings(self, *, html: str, page_record: AcquisitionRecord, **params: Any) -> Iterable[PublicBoardCandidate]:
        raise NotImplementedError

    def enrich_candidate(
        self,
        *,
        candidate: PublicBoardCandidate,
        detail_record: AcquisitionRecord | None,
    ) -> PublicBoardCandidate:
        return candidate

    def _candidate_to_record(
        self,
        *,
        page_record: AcquisitionRecord,
        detail_record: AcquisitionRecord | None,
        candidate: PublicBoardCandidate,
    ) -> AcquisitionRecord:
        provenance_source = candidate.detail_url or candidate.source_url or page_record.provenance.source_url
        provenance_record = detail_record or page_record
        payload = {
            "external_id": candidate.external_id,
            "title": candidate.title,
            "company": candidate.company,
            "location": candidate.location,
            "description": candidate.description,
            "source_url": candidate.source_url,
            "apply_url": candidate.apply_url,
            "employment_type": candidate.employment_type,
            "posted_at": candidate.posted_at.isoformat() if candidate.posted_at else None,
            "detail_url": candidate.detail_url,
            "raw_listing": dict(candidate.raw_listing),
            "raw_detail": dict(candidate.raw_detail),
            "capture_context": {
                "listing_url": page_record.provenance.source_url,
                "detail_url": detail_record.provenance.source_url if detail_record else None,
                "listing_capture": dict(page_record.capture_metadata or {}),
                "detail_capture": dict(detail_record.capture_metadata or {}) if detail_record else None,
            },
        }
        return AcquisitionRecord(
            raw_payload=payload,
            provenance=AcquisitionProvenance(
                fetch_timestamp=provenance_record.provenance.fetch_timestamp,
                source_url=provenance_source or page_record.provenance.source_url,
                connector_version=provenance_record.provenance.connector_version,
            ),
            capture_metadata=dict(provenance_record.capture_metadata or {}),
            debug_metadata={
                "source_name": self.source_name,
                "listing_source_url": page_record.provenance.source_url,
                "detail_source_url": detail_record.provenance.source_url if detail_record else None,
            },
            artifact=detail_record.artifact if detail_record else page_record.artifact,
        )

    def _extract_failures(self, batch: AcquisitionBatch) -> list[dict[str, Any]]:
        failures = batch.metadata.get("failures", [])
        if isinstance(failures, list):
            return [failure for failure in failures if isinstance(failure, dict)]
        return []


class UnsupportedPublicBoardSourceAdapter(SourceAdapter):
    def __init__(
        self,
        *,
        source_name: str,
        reason: str,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        resolved_policy = policy or get_source_policy(source_name)
        super().__init__(
            source_name=source_name,
            policy=resolved_policy,
            backend=backend or ScraplingFetchBackend(),
        )
        self._reason = reason

    def acquire(self, **params: Any) -> AcquisitionBatch:
        return build_failure_batch(
            source_name=self.source_name,
            error=self._reason,
            metadata={"reason": self._reason},
        )

    def normalize(self, acquired: AcquisitionRecord | Any, **context: Any) -> Any | None:
        return None
