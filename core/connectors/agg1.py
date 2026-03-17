"""
AGG-1 discovery connector (Adzuna API reference implementation).

Fetches jobs from https://api.adzuna.com/v1/api/jobs (query-driven, multi-company).
Discovery sources are not canonical truth; records are marked with source_role=discovery.
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

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs"


class Agg1ConnectorConfig:
    """Configuration for AGG-1 (Adzuna) discovery."""

    def __init__(
        self,
        app_id: str,
        app_key: str,
        country: str = "us",
    ):
        self.app_id = app_id.strip()
        self.app_key = app_key.strip()
        self.country = (country or "us").strip().lower()


class Agg1Connector:
    """
    Discovery connector using Adzuna Jobs API.

    Query-driven retrieval across many companies. Lower confidence than
    canonical ATS sources. Per ARCH §13.4: discovery, not canonical truth.
    """

    def __init__(self, config: Agg1ConnectorConfig):
        self.config = config

    @property
    def source_name(self) -> str:
        return "agg1"

    def fetch_raw_jobs(
        self,
        query: str | None = None,
        location: str | None = None,
        results_per_page: int = 20,
        **params: object,
    ) -> FetchResult:
        """
        Fetch raw job listings from Adzuna.

        Uses GET /v1/api/jobs/{country}/search/1 with what= and where= params.
        """
        if not self.config.app_id or not self.config.app_key:
            return FetchResult(
                raw_jobs=[],
                stats={"fetched": 0, "errors": 1},
                error="AGG-1 requires ADZUNA_APP_ID and ADZUNA_APP_KEY",
            )
        url = f"{ADZUNA_BASE}/{self.config.country}/search/1"
        fetch_params = {
            "app_id": self.config.app_id,
            "app_key": self.config.app_key,
            "results_per_page": min(max(results_per_page, 1), 50),
        }
        if query:
            fetch_params["what"] = query.strip()
        if location:
            fetch_params["where"] = location.strip()

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

        results = data.get("results") or []
        raw_jobs_with_provenance = [
            RawJobWithProvenance(raw_payload=j, provenance=provenance)
            for j in results
        ]
        return FetchResult(
            raw_jobs=raw_jobs_with_provenance,
            stats={"fetched": len(results), "errors": 0},
            error=None,
        )

    def normalize(self, raw_job: dict, **context: object) -> Optional[CanonicalJobPayload]:
        """
        Map Adzuna job dict to canonical schema.

        Adzuna fields: id, title, description, created, redirect_url,
        company.display_name, location.display_name, contract_type, contract_time,
        salary_min, salary_max.
        """
        job_id = raw_job.get("id")
        if job_id is None:
            return None
        external_id = str(job_id)

        title = (raw_job.get("title") or "").strip()
        if not title:
            return None

        company_obj = raw_job.get("company") or {}
        company = (
            company_obj.get("display_name") if isinstance(company_obj, dict) else None
        ) or ""
        company = str(company).strip() or "Unknown"
        loc_obj = raw_job.get("location") or {}
        location: Optional[str] = None
        if isinstance(loc_obj, dict) and loc_obj.get("display_name"):
            location = str(loc_obj["display_name"]).strip()
        else:
            area_list = loc_obj.get("area") if isinstance(loc_obj, dict) else None
            if isinstance(area_list, (list, tuple)) and area_list:
                location = str(area_list[0]).strip() if area_list else None

        source_url = raw_job.get("redirect_url") or ""
        apply_url = source_url

        posted_at: Optional[datetime] = None
        created = raw_job.get("created")
        if created:
            try:
                s = str(created).replace("Z", "+00:00")
                posted_at = datetime.fromisoformat(s)
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass

        description = (raw_job.get("description") or "").strip() or None
        employment_type = (raw_job.get("contract_type") or raw_job.get("contract_time") or "").strip() or None

        normalized_title = normalize_title(title)
        normalized_company = normalize_company(company)
        normalized_location = normalize_location(location) if location else None

        return CanonicalJobPayload(
            source_name="agg1",
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


def create_agg1_connector(
    app_id: str,
    app_key: str,
    country: str = "us",
) -> Agg1Connector:
    """Factory for Agg1Connector."""
    return Agg1Connector(
        Agg1ConnectorConfig(app_id=app_id, app_key=app_key, country=country)
    )
