"""
Lever Postings API connector.

Fetches jobs from https://api.lever.co/v0/postings/{client_name}
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

LEVER_POSTINGS_BASE = "https://api.lever.co/v0/postings"


class LeverConnectorConfig:
    """Configuration for a Lever company board."""

    def __init__(self, client_name: str, company_name: str | None = None):
        self.client_name = client_name.strip().lower()
        self.company_name = (company_name or client_name).strip()


class LeverConnector:
    """
    Connector for the Lever Postings API (v0).

    Fetches jobs from a company's Lever board. Company name defaults to
    client_name (slug) if not provided.
    """

    def __init__(self, config: LeverConnectorConfig):
        self.config = config

    @property
    def source_name(self) -> str:
        return "lever"

    def fetch_raw_jobs(self, **params: object) -> FetchResult:
        """
        Fetch raw job listings from Lever.

        Uses GET /v0/postings/{client_name}?mode=json. Returns full
        job descriptions, categories, and apply URLs.
        """
        url = f"{LEVER_POSTINGS_BASE}/{self.config.client_name}"
        fetch_params = {"mode": "json"}
        fetch_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        provenance = ProvenanceMetadata(
            fetch_timestamp=fetch_timestamp,
            source_url=url,
            connector_version="1.0",
        )

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(url, params=fetch_params)
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

        # Lever returns array directly
        jobs = data if isinstance(data, list) else []
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
        Map a Lever posting dict to the canonical schema.

        Lever fields:
        - id: UUID
        - text: job title
        - categories: { commitment, department, location, team, allLocations }
        - description, descriptionPlain, opening, openingPlain
        - hostedUrl, applyUrl
        - createdAt: microseconds since epoch
        - workplaceType, country
        """
        job_id = raw_job.get("id")
        if job_id is None:
            return None
        external_id = str(job_id)

        title = (raw_job.get("text") or "").strip()
        if not title:
            return None

        company = self.config.company_name
        if not company:
            return None

        # Location from categories.location or allLocations
        location: Optional[str] = None
        cats = raw_job.get("categories") or {}
        if isinstance(cats, dict) and cats.get("location"):
            location = str(cats["location"]).strip()
        if not location and isinstance(cats, dict):
            all_loc = cats.get("allLocations")
            if isinstance(all_loc, (list, tuple)) and all_loc:
                location = str(all_loc[0]).strip()

        # Employment type from categories.commitment
        employment_type: Optional[str] = None
        if isinstance(cats, dict) and cats.get("commitment"):
            employment_type = str(cats["commitment"]).strip()

        source_url = raw_job.get("hostedUrl") or ""
        apply_url = raw_job.get("applyUrl") or source_url

        # Posted date: createdAt is microseconds since epoch
        posted_at: Optional[datetime] = None
        created = raw_job.get("createdAt")
        if created is not None:
            try:
                ts = int(created) / 1000 if int(created) > 1e12 else int(created)
                posted_at = datetime.fromtimestamp(ts, tz=timezone.utc)
            except (ValueError, TypeError):
                pass

        # Description: prefer descriptionPlain, fallback to description/opening
        description = (
            raw_job.get("descriptionPlain")
            or raw_job.get("description")
            or raw_job.get("openingPlain")
            or raw_job.get("opening")
        )
        if description is not None:
            description = str(description).strip() or None

        normalized_title = normalize_title(title)
        normalized_company = normalize_company(company)
        normalized_location = normalize_location(location) if location else None

        return CanonicalJobPayload(
            source_name="lever",
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


def create_lever_connector(
    client_name: str,
    company_name: str | None = None,
) -> LeverConnector:
    """Factory for LeverConnector."""
    return LeverConnector(
        LeverConnectorConfig(client_name=client_name, company_name=company_name)
    )
