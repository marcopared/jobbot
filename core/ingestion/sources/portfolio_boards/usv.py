from __future__ import annotations

from typing import Any, Mapping

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.sources.portfolio_boards.common import load_json_object
from core.ingestion.sources.public_boards.common import (
    BasePublicBoardSourceAdapter,
    DEFAULT_HEADERS,
    clean_text,
    extract_record_html,
)
from core.ingestion.types import (
    AcquisitionBatch,
    AcquisitionProvenance,
    AcquisitionRecord,
    AcquisitionRequest,
    FetchMode,
    SourcePolicy,
)


class USVSourceAdapter(BasePublicBoardSourceAdapter):
    listing_url = "https://jobs.usv.com/jobs"
    search_api_url = "https://jobs.usv.com/api-boards/search-jobs"
    board_id = "union-square-ventures"

    def __init__(
        self,
        *,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        super().__init__(
            source_name="usv",
            policy=policy,
            backend=backend,
        )

    def acquire(self, **params: Any) -> AcquisitionBatch:
        max_results = max(1, int(params.get("max_results", 25)))
        listing_batch = self.backend.acquire(
            self.source_name,
            request=self.build_listing_request(max_results=max_results),
        )
        if listing_batch.error and not listing_batch.records:
            return listing_batch

        failures = self._extract_failures(listing_batch)
        records: list[AcquisitionRecord] = []
        total = 0
        search_meta: Mapping[str, Any] = {}

        for listing_record in listing_batch.records:
            payload = load_json_object(extract_record_html(listing_record))
            jobs = payload.get("jobs")
            if isinstance(payload.get("meta"), Mapping):
                search_meta = dict(payload["meta"])
            try:
                total = int(payload.get("total", total))
            except (TypeError, ValueError):
                total = total

            if not isinstance(jobs, list):
                continue

            for job in jobs[:max_results]:
                if not isinstance(job, Mapping):
                    continue

                source_url = clean_text(job.get("url")) or clean_text(job.get("applyUrl"))
                apply_url = clean_text(job.get("applyUrl")) or source_url
                location = None
                raw_locations = job.get("locations")
                if isinstance(raw_locations, list):
                    for entry in raw_locations:
                        location = clean_text(entry)
                        if location:
                            break

                posted_at = clean_text(job.get("timeStamp"))
                raw_payload = {
                    "external_id": clean_text(job.get("jobId")),
                    "title": clean_text(job.get("title")),
                    "company": clean_text(job.get("companyName")),
                    "location": location,
                    "description": None,
                    "source_url": source_url,
                    "apply_url": apply_url,
                    "employment_type": None,
                    "posted_at": posted_at,
                    "raw_listing": dict(job),
                    "raw_detail": {
                        "search_meta": dict(search_meta),
                    },
                    "capture_context": {
                        "listing_url": self.listing_url,
                        "detail_url": None,
                        "listing_capture": dict(listing_record.capture_metadata or {}),
                        "detail_capture": None,
                        "search_api_url": self.search_api_url,
                    },
                }
                records.append(
                    AcquisitionRecord(
                        raw_payload=raw_payload,
                        provenance=AcquisitionProvenance(
                            fetch_timestamp=listing_record.provenance.fetch_timestamp,
                            source_url=source_url or listing_record.provenance.source_url,
                            connector_version=listing_record.provenance.connector_version,
                        ),
                        capture_metadata=dict(listing_record.capture_metadata or {}),
                        debug_metadata={
                            "source_name": self.source_name,
                            "listing_source_url": listing_record.provenance.source_url,
                            "detail_source_url": None,
                        },
                        artifact=listing_record.artifact,
                    )
                )

        metadata: dict[str, Any] = {
            "source_name": self.source_name,
            "listing_url": self.listing_url,
            "search_api_url": self.search_api_url,
            "total": total,
        }
        if search_meta:
            metadata["search_meta"] = dict(search_meta)
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

    def build_listing_request(self, **params: Any) -> AcquisitionRequest:
        max_results = max(1, int(params.get("max_results", 25)))
        return AcquisitionRequest(
            url=self.search_api_url,
            method="POST",
            fetch_mode=FetchMode.SIMPLE,
            headers={
                **DEFAULT_HEADERS,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            body={
                "meta": {"size": max_results},
                "board": {"id": self.board_id, "isParent": True},
                "query": {},
                "grouped": False,
            },
            timeout_ms=int(params.get("timeout_ms", 30_000)),
        )

    def extract_listings(
        self,
        *,
        html: str,
        page_record: AcquisitionRecord,
        **params: Any,
    ):
        return []

    def enrich_candidate(self, *, candidate, detail_record):
        return candidate


def build_usv_adapter(
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> USVSourceAdapter:
    return USVSourceAdapter(policy=policy, backend=backend)
