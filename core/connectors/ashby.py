"""
Ashby Job Postings API connector.

Fetches jobs from https://api.ashbyhq.com/posting-api/job-board/{job_board_name}
and normalizes them into the canonical schema.
"""

from datetime import datetime, timezone
from typing import Optional

import httpx

from core.connectors.base import (
    CanonicalJobPayload,
    FetchResult,
    ProvenanceMetadata,
    RawJobWithProvenance,
)
from core.dedup.normalization import (
    normalize_company,
    normalize_location,
    normalize_title,
)

ASHBY_POSTINGS_BASE = "https://api.ashbyhq.com/posting-api/job-board"


class AshbyConnectorConfig:
    """Configuration for an Ashby job board."""

    def __init__(self, job_board_name: str, company_name: str | None = None):
        self.job_board_name = job_board_name.strip()
        self.company_name = (company_name or job_board_name).strip()


class AshbyConnector:
    """
    Connector for the Ashby Public Job Postings API.

    Fetches jobs from a company's Ashby job board. Company name defaults
    to job_board_name if not provided.
    """

    def __init__(self, config: AshbyConnectorConfig):
        self.config = config

    @property
    def source_name(self) -> str:
        return "ashby"

    def fetch_raw_jobs(self, include_compensation: bool = False, **params: object) -> FetchResult:
        """
        Fetch raw job listings from Ashby.

        Uses GET /posting-api/job-board/{job_board_name}.
        Optional includeCompensation=true for salary data.
        """
        url = f"{ASHBY_POSTINGS_BASE}/{self.config.job_board_name}"
        fetch_params: dict = {}
        if include_compensation:
            fetch_params["includeCompensation"] = "true"
        fetch_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        provenance = ProvenanceMetadata(
            fetch_timestamp=fetch_timestamp,
            source_url=url,
            connector_version="1.0",
        )

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(url, params=fetch_params or None)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            return FetchResult(
                raw_jobs=[],
                stats={"fetched": 0, "errors": 1},
                error=str(e),
            )
        except Exception as e:
            return FetchResult(
                raw_jobs=[],
                stats={"fetched": 0, "errors": 1},
                error=str(e),
            )

        jobs = data.get("jobs") or []
        raw_jobs_with_provenance = [
            RawJobWithProvenance(raw_payload=j, provenance=provenance)
            for j in jobs
        ]
        return FetchResult(
            raw_jobs=raw_jobs_with_provenance,
            stats={"fetched": len(jobs), "errors": 0},
            error=None,
        )

    def normalize(self, raw_job: dict, **context: object) -> Optional[CanonicalJobPayload]:
        """
        Map an Ashby job dict to the canonical schema.

        Ashby fields:
        - title, location, department, team
        - isRemote, workplaceType, employmentType
        - descriptionHtml, descriptionPlain
        - publishedAt, jobUrl, applyUrl
        - compensation (if includeCompensation=true)
        """
        # Ashby jobs may not have a stable id; use jobUrl as external_id fallback
        job_url = raw_job.get("jobUrl") or ""
        external_id = job_url.rstrip("/").split("/")[-1] if job_url else ""
        if not external_id:
            external_id = raw_job.get("id") or ""
        if not external_id:
            return None

        title = (raw_job.get("title") or "").strip()
        if not title:
            return None

        company = self.config.company_name
        if not company:
            return None

        location = (raw_job.get("location") or "").strip() or None
        if raw_job.get("isRemote") and not location:
            location = "Remote"

        employment_type: Optional[str] = None
        emp = raw_job.get("employmentType")
        if emp:
            employment_type = str(emp).strip()

        source_url = job_url or None
        apply_url = raw_job.get("applyUrl") or job_url or None

        # Posted date
        posted_at: Optional[datetime] = None
        published = raw_job.get("publishedAt")
        if published:
            try:
                posted_at = datetime.fromisoformat(
                    str(published).replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        # Description: prefer HTML for downstream ATS analysis
        description = (
            raw_job.get("descriptionHtml")
            or raw_job.get("descriptionPlain")
        )
        if description is not None:
            description = str(description).strip() or None

        normalized_title = normalize_title(title)
        normalized_company = normalize_company(company)
        normalized_location = normalize_location(location) if location else None

        return CanonicalJobPayload(
            source_name="ashby",
            external_id=external_id,
            title=title,
            company=company,
            location=location,
            employment_type=employment_type,
            description=description,
            apply_url=apply_url,
            source_url=source_url,
            posted_at=posted_at,
            raw_payload=raw_job,
            normalized_title=normalized_title,
            normalized_company=normalized_company,
            normalized_location=normalized_location,
        )


def create_ashby_connector(
    job_board_name: str,
    company_name: str | None = None,
) -> AshbyConnector:
    """Factory for AshbyConnector."""
    return AshbyConnector(
        AshbyConnectorConfig(job_board_name=job_board_name, company_name=company_name)
    )
