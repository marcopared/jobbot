"""
Greenhouse Job Board API connector.

Fetches jobs from https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
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
from core.connectors.company_names import derive_company_name
from core.dedup.normalization import (
    normalize_company,
    normalize_location,
    normalize_title,
)

GREENHOUSE_JOBS_BASE = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseConnectorConfig:
    """Configuration for a single Greenhouse board."""

    def __init__(self, board_token: str, company_name: str | None = None):
        self.board_token = board_token.strip()
        self.company_name = (company_name or "").strip()


class GreenhouseConnector:
    """
    Connector for the Greenhouse Job Board API.

    Fetches jobs from a company's Greenhouse board. Company name may be
    supplied for canonical runs, but normalization prefers payload-derived
    employer names when present.
    """

    def __init__(self, config: GreenhouseConnectorConfig):
        self.config = config

    @property
    def source_name(self) -> str:
        return "greenhouse"

    def fetch_raw_jobs(self, include_content: bool = True) -> FetchResult:
        """
        Fetch raw job listings from Greenhouse.

        Uses GET /v1/boards/{board_token}/jobs?content=true to get full
        job descriptions, departments, and offices.
        """
        url = f"{GREENHOUSE_JOBS_BASE}/{self.config.board_token}/jobs"
        params = {"content": "true"} if include_content else {}
        fetch_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        provenance = ProvenanceMetadata(
            fetch_timestamp=fetch_timestamp,
            source_url=url,
            connector_version="1.0",
        )

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(url, params=params)
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
        Map a Greenhouse job dict to the canonical schema.

        Greenhouse job fields (with content=true):
        - id: job post id
        - internal_job_id: job id (null for prospect posts)
        - title: job title
        - updated_at: ISO datetime
        - requisition_id: optional
        - location: { name: str }
        - absolute_url: job page URL (used as source and apply URL)
        - language: e.g. "en"
        - metadata: custom fields or null
        - content: HTML job description
        - departments: list of { id, name, ... }
        - offices: list of { id, name, location, ... }
        """
        job_id = raw_job.get("id")
        if job_id is None:
            return None
        external_id = str(job_id)

        title = (raw_job.get("title") or "").strip()
        if not title:
            return None

        company = derive_company_name(
            raw_job,
            configured_company_name=self.config.company_name,
        )

        # Location from location.name or aggregate from offices
        location = None
        loc_obj = raw_job.get("location")
        if isinstance(loc_obj, dict) and loc_obj.get("name"):
            location = str(loc_obj["name"]).strip()
        elif isinstance(loc_obj, str):
            location = loc_obj.strip()

        if not location and raw_job.get("offices"):
            offices = raw_job.get("offices") or []
            if offices and isinstance(offices[0], dict) and offices[0].get("location"):
                location = str(offices[0]["location"]).strip()

        # Employment type: Greenhouse metadata may contain it; otherwise None
        employment_type: Optional[str] = None
        metadata = raw_job.get("metadata")
        if isinstance(metadata, dict):
            emp = metadata.get("employment_type") or metadata.get("Employment Type")
            if emp:
                employment_type = str(emp).strip()

        source_url = raw_job.get("absolute_url") or ""
        apply_url = source_url  # Greenhouse uses job page as apply entry point

        # Posted/updated date
        posted_at: Optional[datetime] = None
        updated_str = raw_job.get("updated_at")
        if updated_str:
            try:
                posted_at = datetime.fromisoformat(
                    updated_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        # Description
        description = raw_job.get("content")
        if description is not None:
            description = str(description).strip() or None

        # Normalized forms for dedup (shared normalization utilities)
        normalized_title = normalize_title(title)
        normalized_company = normalize_company(company)
        normalized_location = normalize_location(location) or None

        return CanonicalJobPayload(
            source_name="greenhouse",
            external_id=external_id,
            title=title,
            company=company,
            location=location,
            employment_type=employment_type,
            description=description,
            apply_url=apply_url or None,
            source_url=source_url or None,
            posted_at=posted_at,
            raw_payload=raw_job,
            normalized_title=normalized_title,
            normalized_company=normalized_company,
            normalized_location=normalized_location,
        )


def create_greenhouse_connector(
    board_token: str, company_name: str | None = None
) -> GreenhouseConnector:
    """Factory for GreenhouseConnector."""
    return GreenhouseConnector(
        GreenhouseConnectorConfig(board_token=board_token, company_name=company_name)
    )
