from __future__ import annotations

from typing import Any

from core.db.models import JobSource
from core.ingestion.backends.base import AcquisitionBackend, LegacyScraperBackend
from core.ingestion.source_policies import get_source_policy
from core.ingestion.sources.base import SourceAdapter
from core.ingestion.types import AcquisitionBatch, AcquisitionRecord, SourcePolicy
from core.scraping.base import NormalizedJob, ScrapeParams, ScrapeResult


class JobSpyScraperSourceAdapter(SourceAdapter):
    def __init__(
        self,
        scraper: Any,
        *,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        resolved_policy = policy or get_source_policy("jobspy")
        super().__init__(
            source_name="jobspy",
            policy=resolved_policy,
            backend=backend or LegacyScraperBackend(),
        )
        self._scraper = scraper

    @property
    def scraper(self) -> Any:
        return self._scraper

    def acquire(self, **params: Any) -> AcquisitionBatch:
        scrape_params = params.get("params")
        if scrape_params is None:
            scrape_params = ScrapeParams(**params)
        return self.backend.acquire(
            self.source_name,
            scrape=self._scraper.scrape,
            params=scrape_params,
        )

    def normalize(self, acquired: AcquisitionRecord | dict[str, Any], **context: Any) -> NormalizedJob | None:
        if isinstance(acquired, AcquisitionRecord) and isinstance(acquired.normalized_payload, NormalizedJob):
            return acquired.normalized_payload

        raw_payload = acquired.raw_payload if isinstance(acquired, AcquisitionRecord) else acquired
        if not isinstance(raw_payload, dict):
            return None

        title = str(raw_payload.get("title") or "").strip()
        url = str(raw_payload.get("job_url") or raw_payload.get("url") or "").strip()
        if not title or not url:
            return None

        company_name = str(raw_payload.get("company") or raw_payload.get("company_name") or "").strip()
        location = raw_payload.get("location")
        apply_url = raw_payload.get("job_url_direct") or raw_payload.get("apply_url")
        description = raw_payload.get("description")
        source_job_id = raw_payload.get("id") or raw_payload.get("source_job_id")

        return NormalizedJob(
            title=title,
            company_name=company_name,
            location=str(location).strip() if location else None,
            url=url,
            apply_url=str(apply_url).strip() if apply_url else None,
            description=str(description).strip() if description else None,
            salary_min=None,
            salary_max=None,
            posted_at=None,
            remote_flag=bool(raw_payload.get("is_remote", False)),
            source=JobSource.JOBSPY,
            source_job_id=str(source_job_id).strip() if source_job_id else None,
            raw_payload=raw_payload,
        )

    def scrape(self, params: ScrapeParams) -> ScrapeResult:
        batch = self.acquire(params=params)
        jobs = [
            normalized
            for record in batch.records
            if (normalized := self.normalize(record)) is not None
        ]
        return ScrapeResult(
            jobs=jobs,
            stats=dict(batch.stats),
            error=batch.error,
        )


def build_jobspy_scraper_adapter(
    scraper: Any,
    *,
    policy: SourcePolicy | None = None,
    backend: AcquisitionBackend | None = None,
) -> JobSpyScraperSourceAdapter:
    return JobSpyScraperSourceAdapter(scraper=scraper, policy=policy, backend=backend)
