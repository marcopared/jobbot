from __future__ import annotations

from typing import Any, Iterable, Mapping

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.sources.portfolio_boards.common import (
    extract_initial_state,
    getro_employment_type,
    getro_primary_location,
)
from core.ingestion.sources.public_boards.common import (
    BasePublicBoardSourceAdapter,
    PublicBoardCandidate,
    absolutize_url,
    clean_text,
    html_to_text,
    parse_date,
)
from core.ingestion.types import AcquisitionRecord, SourcePolicy


class GetroLikePortfolioBoardSourceAdapter(BasePublicBoardSourceAdapter):
    def __init__(
        self,
        *,
        source_name: str,
        listing_url: str,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        self.listing_url = listing_url
        super().__init__(
            source_name=source_name,
            policy=policy,
            backend=backend,
        )

    def extract_listings(
        self,
        *,
        html: str,
        page_record: AcquisitionRecord,
        **params: Any,
    ) -> Iterable[PublicBoardCandidate]:
        initial_state = extract_initial_state(html)
        jobs_state = initial_state.get("jobs")
        if not isinstance(jobs_state, Mapping):
            return

        jobs = jobs_state.get("found")
        if not isinstance(jobs, list):
            return

        max_results = int(params.get("max_results", 25))
        for job in jobs[:max_results]:
            if not isinstance(job, Mapping):
                continue
            organization = job.get("organization")
            if not isinstance(organization, Mapping):
                continue

            org_slug = clean_text(organization.get("slug"))
            job_slug = clean_text(job.get("slug"))
            if not org_slug or not job_slug:
                continue

            detail_url = absolutize_url(
                page_record.provenance.source_url,
                f"/companies/{org_slug}/jobs/{job_slug}",
            )
            if not detail_url:
                continue

            yield PublicBoardCandidate(
                external_id=str(job.get("id")) if job.get("id") is not None else job_slug,
                source_url=detail_url,
                title=clean_text(job.get("title")),
                company=clean_text(organization.get("name")),
                location=getro_primary_location(job.get("locations")),
                apply_url=clean_text(job.get("url")),
                detail_url=detail_url,
                raw_listing=dict(job),
            )

    def enrich_candidate(
        self,
        *,
        candidate: PublicBoardCandidate,
        detail_record: AcquisitionRecord | None,
    ) -> PublicBoardCandidate:
        if detail_record is None:
            return candidate

        initial_state = extract_initial_state(detail_record.artifact.content if detail_record.artifact else None)
        jobs_state = initial_state.get("jobs")
        if not isinstance(jobs_state, Mapping):
            return candidate

        current_job = jobs_state.get("currentJob")
        if not isinstance(current_job, Mapping):
            return candidate

        organization = current_job.get("organization")
        org_name = None
        if isinstance(organization, Mapping):
            org_name = clean_text(organization.get("name"))

        return PublicBoardCandidate(
            external_id=candidate.external_id,
            source_url=candidate.source_url,
            title=clean_text(current_job.get("title")) or candidate.title,
            company=org_name or candidate.company,
            location=getro_primary_location(current_job.get("locations")) or candidate.location,
            description=html_to_text(clean_text(current_job.get("description"))) or candidate.description,
            apply_url=clean_text(current_job.get("url")) or candidate.apply_url,
            posted_at=parse_date(clean_text(current_job.get("postedAt"))) or candidate.posted_at,
            employment_type=getro_employment_type(current_job.get("employmentTypes")) or candidate.employment_type,
            detail_url=candidate.detail_url,
            raw_listing=dict(candidate.raw_listing),
            raw_detail={"current_job": dict(current_job)},
        )
