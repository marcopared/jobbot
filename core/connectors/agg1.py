"""
AGG-1 discovery connector (Adzuna API implementation).

Fetches jobs from https://api.adzuna.com/v1/api/jobs (query-driven, multi-company).
Discovery sources are not canonical truth; records are marked with source_role=discovery.
"""

from datetime import datetime, timezone
from typing import Any, Optional

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
ADZUNA_MIN_RESULTS_PER_PAGE = 1
ADZUNA_MAX_RESULTS_PER_PAGE = 50
ADZUNA_DEFAULT_RESULTS_PER_PAGE = 20
ADZUNA_DEFAULT_MAX_PAGES = 3
ADZUNA_DEFAULT_MAX_RESULTS_PER_RUN = 100
ADZUNA_ALLOWED_SORTS = {"default", "hybrid", "date", "salary", "relevance"}


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
        results_per_page: int = ADZUNA_DEFAULT_RESULTS_PER_PAGE,
        **params: object,
    ) -> FetchResult:
        """
        Fetch raw job listings from Adzuna.

        Uses GET /v1/api/jobs/{country}/search/{page} with bounded multi-page fetch.
        """
        if not self.config.app_id or not self.config.app_key:
            return FetchResult(
                raw_jobs=[],
                stats={"fetched": 0, "errors": 1},
                error="AGG-1 requires ADZUNA_APP_ID and ADZUNA_APP_KEY",
            )

        per_page = self._coerce_int(
            results_per_page, default=ADZUNA_DEFAULT_RESULTS_PER_PAGE
        )
        per_page = max(
            ADZUNA_MIN_RESULTS_PER_PAGE, min(per_page, ADZUNA_MAX_RESULTS_PER_PAGE)
        )

        max_pages = self._coerce_int(
            params.get("max_pages"), default=ADZUNA_DEFAULT_MAX_PAGES
        )
        max_pages = max(1, max_pages)

        max_results = self._coerce_int(
            params.get("max_results"), default=ADZUNA_DEFAULT_MAX_RESULTS_PER_RUN
        )
        max_results = max(1, max_results)

        fetch_params: dict[str, Any] = {
            "app_id": self.config.app_id,
            "app_key": self.config.app_key,
            "results_per_page": per_page,
            "sort_by": self._coerce_sort(params.get("sort_by")),
        }
        if query:
            fetch_params["what"] = query.strip()
        if location:
            fetch_params["where"] = location.strip()
        self._add_int_filter(
            fetch_params, "distance", params.get("distance"), minimum=0
        )
        self._add_int_filter(
            fetch_params, "max_days_old", params.get("max_days_old"), minimum=0
        )
        self._add_int_filter(fetch_params, "salary_min", params.get("salary_min"))
        self._add_int_filter(fetch_params, "salary_max", params.get("salary_max"))
        self._add_boolean_filter(fetch_params, "full_time", params.get("full_time"))
        self._add_boolean_filter(fetch_params, "part_time", params.get("part_time"))
        self._add_boolean_filter(fetch_params, "contract", params.get("contract"))
        self._add_boolean_filter(fetch_params, "permanent", params.get("permanent"))
        self._add_string_filter(fetch_params, "category", params.get("category"))

        raw_jobs_with_provenance: list[RawJobWithProvenance] = []
        fetched = 0

        try:
            with httpx.Client(timeout=30.0) as client:
                for page in range(1, max_pages + 1):
                    url = f"{ADZUNA_BASE}/{self.config.country}/search/{page}"
                    fetch_timestamp = (
                        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    )
                    provenance = ProvenanceMetadata(
                        fetch_timestamp=fetch_timestamp,
                        source_url=url,
                        connector_version="1.1",
                    )
                    resp = client.get(url, params=fetch_params)
                    resp.raise_for_status()
                    data = resp.json()
                    provider_error = self._provider_error_from_payload(data)
                    if provider_error:
                        return FetchResult(
                            raw_jobs=[],
                            stats={"fetched": 0, "errors": 1},
                            error=provider_error,
                        )

                    results = data.get("results") or []
                    if not isinstance(results, list):
                        return FetchResult(
                            raw_jobs=[],
                            stats={"fetched": 0, "errors": 1},
                            error="Adzuna response error: expected 'results' list",
                        )
                    if not results:
                        break

                    for job in results:
                        raw_jobs_with_provenance.append(
                            RawJobWithProvenance(raw_payload=job, provenance=provenance)
                        )
                    fetched = len(raw_jobs_with_provenance)
                    if fetched >= max_results:
                        raw_jobs_with_provenance = raw_jobs_with_provenance[
                            :max_results
                        ]
                        fetched = len(raw_jobs_with_provenance)
                        break

                    if len(results) < per_page:
                        break
        except httpx.HTTPStatusError as e:
            return FetchResult(
                raw_jobs=[],
                stats={"fetched": 0, "errors": 1},
                error=self._format_http_status_error(e),
            )
        except httpx.RequestError as e:
            return FetchResult(
                raw_jobs=[],
                stats={"fetched": 0, "errors": 1},
                error=f"Adzuna request failed: {e}",
            )
        except Exception as e:
            return FetchResult(
                raw_jobs=[],
                stats={"fetched": 0, "errors": 1},
                error=str(e),
            )

        return FetchResult(
            raw_jobs=raw_jobs_with_provenance,
            stats={"fetched": fetched, "errors": 0},
            error=None,
        )

    def normalize(
        self, raw_job: dict, **context: object
    ) -> Optional[CanonicalJobPayload]:
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
        contract_time = str(raw_job.get("contract_time") or "").strip()
        contract_type = str(raw_job.get("contract_type") or "").strip()
        employment_type_parts = [
            part for part in (contract_time, contract_type) if part
        ]
        employment_type = (
            " / ".join(employment_type_parts) if employment_type_parts else None
        )

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

    @staticmethod
    def _coerce_int(value: object, default: int) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_sort(value: object) -> str:
        if not isinstance(value, str):
            return "date"
        normalized = value.strip().lower()
        if normalized in ADZUNA_ALLOWED_SORTS:
            return normalized
        return "date"

    @staticmethod
    def _add_int_filter(
        target: dict[str, Any],
        key: str,
        value: object,
        minimum: int | None = None,
    ) -> None:
        if value is None:
            return
        try:
            num = int(value)
        except (TypeError, ValueError):
            return
        if minimum is not None and num < minimum:
            return
        target[key] = num

    @staticmethod
    def _is_truthy(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return False

    @classmethod
    def _add_boolean_filter(
        cls, target: dict[str, Any], key: str, value: object
    ) -> None:
        if cls._is_truthy(value):
            target[key] = "1"

    @staticmethod
    def _add_string_filter(target: dict[str, Any], key: str, value: object) -> None:
        if not isinstance(value, str):
            return
        cleaned = value.strip()
        if cleaned:
            target[key] = cleaned

    @staticmethod
    def _provider_error_from_payload(payload: object) -> str | None:
        if not isinstance(payload, dict):
            return None
        exc = payload.get("exception")
        if not exc:
            return None
        display = payload.get("display")
        if isinstance(display, str) and display.strip():
            return f"Adzuna provider error: {display.strip()}"
        return f"Adzuna provider error: {exc}"

    @staticmethod
    def _format_http_status_error(err: httpx.HTTPStatusError) -> str:
        response = err.response
        detail = response.text.strip() if response is not None else ""
        if detail:
            return f"Adzuna HTTP error {response.status_code}: {detail}"
        return str(err)


def create_agg1_connector(
    app_id: str,
    app_key: str,
    country: str = "us",
) -> Agg1Connector:
    """Factory for Agg1Connector."""
    return Agg1Connector(
        Agg1ConnectorConfig(app_id=app_id, app_key=app_key, country=country)
    )
