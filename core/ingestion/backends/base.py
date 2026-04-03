from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from core.connectors.base import FetchResult
from core.ingestion.types import (
    AcquisitionArtifact,
    AcquisitionBatch,
    AcquisitionProvenance,
    AcquisitionRecord,
)
from core.scraping.base import NormalizedJob, ScrapeResult


class AcquisitionBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def acquire(self, source_name: str, **kwargs: Any) -> AcquisitionBatch:
        raise NotImplementedError


class LegacyConnectorBackend(AcquisitionBackend):
    @property
    def name(self) -> str:
        return "legacy_connector"

    def acquire(self, source_name: str, **kwargs: Any) -> AcquisitionBatch:
        fetch = kwargs["fetch"]
        params = kwargs.get("params", {})

        result: FetchResult = fetch(**params)
        records = [
            AcquisitionRecord(
                raw_payload=raw_with_prov.raw_payload,
                provenance=AcquisitionProvenance(
                    fetch_timestamp=raw_with_prov.provenance.fetch_timestamp,
                    source_url=raw_with_prov.provenance.source_url,
                    connector_version=raw_with_prov.provenance.connector_version,
                ),
            )
            for raw_with_prov in result.raw_jobs
        ]
        return AcquisitionBatch(
            records=records,
            stats=dict(result.stats),
            error=result.error,
            metadata={"source_name": source_name},
        )


class LegacyScraperBackend(AcquisitionBackend):
    @property
    def name(self) -> str:
        return "legacy_scraper"

    def acquire(self, source_name: str, **kwargs: Any) -> AcquisitionBatch:
        scrape = kwargs["scrape"]
        params = kwargs["params"]

        result: ScrapeResult = scrape(params)
        records = [
            self._job_to_record(source_name=source_name, job=job)
            for job in result.jobs
        ]
        return AcquisitionBatch(
            records=records,
            stats=dict(result.stats),
            error=result.error,
            metadata={"source_name": source_name},
        )

    def _job_to_record(self, *, source_name: str, job: NormalizedJob) -> AcquisitionRecord:
        source_url = job.url or job.apply_url or ""
        return AcquisitionRecord(
            raw_payload=job.raw_payload,
            provenance=AcquisitionProvenance(
                fetch_timestamp=datetime.now(timezone.utc).isoformat(),
                source_url=source_url,
                connector_version="legacy_scraper",
            ),
            debug_metadata={
                "source_name": source_name,
                "normalized_job": asdict(job),
            },
            normalized_payload=job,
            artifact=AcquisitionArtifact(
                content=job.description,
                content_type="text/plain" if job.description else None,
                final_url=source_url or None,
            ),
        )
