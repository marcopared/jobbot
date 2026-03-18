"""SERP1 discovery connector (DataForSEO Google Jobs, feature-flagged)."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from apps.api.settings import Settings
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

DEFAULT_BASE_URL = "https://api.dataforseo.com"
DEFAULT_PRIORITY = 1
DEFAULT_DEPTH = 10
DEFAULT_POLL_MAX_ATTEMPTS = 8
DEFAULT_POLL_INTERVAL_SECONDS = 1.5
DEFAULT_POLL_TIMEOUT_SECONDS = 20.0


class Serp1ConnectorConfig:
    """Configuration for SERP1 (DataForSEO Google Jobs)."""

    def __init__(
        self,
        login: str,
        password: str,
        base_url: str = DEFAULT_BASE_URL,
        location_name: str = "",
        language_name: str = "",
        poll_max_attempts: int = DEFAULT_POLL_MAX_ATTEMPTS,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        poll_timeout_seconds: float = DEFAULT_POLL_TIMEOUT_SECONDS,
    ):
        self.login = (login or "").strip()
        self.password = (password or "").strip()
        self.base_url = (base_url or DEFAULT_BASE_URL).strip().rstrip("/")
        self.location_name = (location_name or "").strip()
        self.language_name = (language_name or "").strip()
        self.poll_max_attempts = max(1, int(poll_max_attempts))
        self.poll_interval_seconds = max(0.1, float(poll_interval_seconds))
        self.poll_timeout_seconds = max(1.0, float(poll_timeout_seconds))


class Serp1Connector:
    """Bounded synchronous wrapper over DataForSEO Google Jobs task APIs."""

    def __init__(self, config: Serp1ConnectorConfig):
        self.config = config

    @property
    def source_name(self) -> str:
        return "serp1"

    def fetch_raw_jobs(
        self,
        query: str | None = None,
        location: str | None = None,
        **params: object,
    ) -> FetchResult:
        """
        Fetch jobs using DataForSEO Google Jobs task flow:
        1) task_post
        2) bounded polling via tasks_ready
        3) task_get/advanced
        """
        missing = []
        if not self.config.login:
            missing.append("DATAFORSEO_LOGIN")
        if not self.config.password:
            missing.append("DATAFORSEO_PASSWORD")
        if missing:
            return FetchResult(
                raw_jobs=[],
                stats={"fetched": 0, "errors": 1},
                error=f"SERP1 requires {', '.join(missing)}",
            )

        keyword = (query or "").strip()
        if not keyword:
            return FetchResult(
                raw_jobs=[],
                stats={"fetched": 0, "errors": 1},
                error="SERP1 requires a non-empty query",
            )

        location_name = self._coerce_str(
            params.get("location_name") or location or self.config.location_name
        )
        location_code = self._coerce_optional_int(params.get("location_code"))
        language_name = self._coerce_str(
            params.get("language_name") or self.config.language_name
        )
        language_code = self._coerce_str(params.get("language_code"))

        if not location_name and location_code is None:
            return FetchResult(
                raw_jobs=[],
                stats={"fetched": 0, "errors": 1},
                error="SERP1 requires location_name or location_code",
            )
        if not language_name and not language_code:
            return FetchResult(
                raw_jobs=[],
                stats={"fetched": 0, "errors": 1},
                error="SERP1 requires language_name or language_code",
            )

        depth = self._coerce_int(params.get("depth"), default=DEFAULT_DEPTH)
        depth = max(1, min(depth, 200))
        priority = self._coerce_int(params.get("priority"), default=DEFAULT_PRIORITY)
        if priority not in (1, 2):
            priority = DEFAULT_PRIORITY

        task_payload: dict[str, Any] = {
            "keyword": keyword,
            "depth": depth,
            "priority": priority,
        }
        if location_code is not None:
            task_payload["location_code"] = location_code
        else:
            task_payload["location_name"] = location_name

        if language_code:
            task_payload["language_code"] = language_code
        else:
            task_payload["language_name"] = language_name

        location_radius = self._coerce_str(params.get("location_radius"))
        if location_radius:
            task_payload["location_radius"] = location_radius

        employment_type = self._coerce_employment_type(params.get("employment_type"))
        if employment_type:
            task_payload["employment_type"] = employment_type

        poll_max_attempts = self._coerce_int(
            params.get("poll_max_attempts"), default=self.config.poll_max_attempts
        )
        poll_max_attempts = max(1, poll_max_attempts)
        poll_interval_seconds = self._coerce_float(
            params.get("poll_interval_seconds"),
            default=self.config.poll_interval_seconds,
        )
        poll_interval_seconds = max(0.1, poll_interval_seconds)
        poll_timeout_seconds = self._coerce_float(
            params.get("poll_timeout_seconds"), default=self.config.poll_timeout_seconds
        )
        poll_timeout_seconds = max(1.0, poll_timeout_seconds)

        task_post_url = f"{self.config.base_url}/v3/serp/google/jobs/task_post"
        tasks_ready_url = f"{self.config.base_url}/v3/serp/google/jobs/tasks_ready"

        try:
            with httpx.Client(
                auth=(self.config.login, self.config.password), timeout=30.0
            ) as client:
                task_id = self._submit_task(client, task_post_url, task_payload)
                if not task_id:
                    return FetchResult(
                        raw_jobs=[],
                        stats={"fetched": 0, "errors": 1},
                        error="DataForSEO task_post failed: missing task id",
                    )

                ready = self._poll_until_ready(
                    client=client,
                    tasks_ready_url=tasks_ready_url,
                    task_id=task_id,
                    max_attempts=poll_max_attempts,
                    poll_interval_seconds=poll_interval_seconds,
                    timeout_seconds=poll_timeout_seconds,
                )
                if not ready:
                    return FetchResult(
                        raw_jobs=[],
                        stats={"fetched": 0, "errors": 1},
                        error=(
                            "DataForSEO readiness timeout "
                            f"(task_id={task_id}, attempts={poll_max_attempts}, timeout_seconds={poll_timeout_seconds})"
                        ),
                    )

                advanced_url = f"{self.config.base_url}/v3/serp/google/jobs/task_get/advanced/{task_id}"
                advanced_result = self._get_advanced_result(client, advanced_url)
                if advanced_result is None:
                    return FetchResult(
                        raw_jobs=[],
                        stats={"fetched": 0, "errors": 1},
                        error=f"DataForSEO advanced-get failed (task_id={task_id})",
                    )

                result_check_url = self._coerce_str(advanced_result.get("check_url"))
                items = advanced_result.get("items")
                if not isinstance(items, list):
                    return FetchResult(
                        raw_jobs=[],
                        stats={"fetched": 0, "errors": 1},
                        error="DataForSEO response error: expected 'items' list",
                    )

                fetch_timestamp = (
                    datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                )
                provenance_source_url = result_check_url or advanced_url
                provenance = ProvenanceMetadata(
                    fetch_timestamp=fetch_timestamp,
                    source_url=provenance_source_url,
                    connector_version="1.0",
                )

                raw_jobs_with_provenance: list[RawJobWithProvenance] = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    enriched_item = dict(item)
                    enriched_item["_task_id"] = task_id
                    if result_check_url:
                        enriched_item["_check_url"] = result_check_url
                    raw_jobs_with_provenance.append(
                        RawJobWithProvenance(
                            raw_payload=enriched_item,
                            provenance=provenance,
                        )
                    )

                return FetchResult(
                    raw_jobs=raw_jobs_with_provenance,
                    stats={"fetched": len(raw_jobs_with_provenance), "errors": 0},
                    error=None,
                )
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
                error=f"DataForSEO request failed: {e}",
            )
        except Exception as e:
            return FetchResult(
                raw_jobs=[],
                stats={"fetched": 0, "errors": 1},
                error=f"DataForSEO unexpected error: {e}",
            )

    def normalize(
        self, raw_job: dict[str, Any], **context: object
    ) -> CanonicalJobPayload | None:
        """Normalize DataForSEO Google Jobs item to canonical discovery payload."""
        title = self._coerce_str(raw_job.get("title"))
        if not title:
            return None

        company = self._coerce_str(raw_job.get("employer_name"))
        if not company:
            company = self._coerce_str(raw_job.get("company"))
        if not company:
            company = "Unknown"

        location = self._coerce_str(raw_job.get("location")) or None
        description = self._coerce_str(raw_job.get("snippet"))
        if not description:
            description = self._coerce_str(raw_job.get("description"))
        if not description:
            description = None

        source_url = self._coerce_str(raw_job.get("source_url")) or None
        apply_url = self._coerce_str(raw_job.get("apply_url")) or source_url

        posted_at = self._parse_datetime(raw_job.get("timestamp"))
        if posted_at is None:
            posted_at = self._parse_datetime(raw_job.get("posted_at"))

        job_id = self._coerce_str(raw_job.get("job_id"))
        external_id = job_id or self._derive_external_id(
            title=title,
            company=company,
            location=location,
            source_url=source_url,
            timestamp=self._coerce_str(raw_job.get("timestamp")),
        )

        employment_type = self._coerce_str(raw_job.get("contract_type")) or None

        normalized_title = normalize_title(title)
        normalized_company = normalize_company(company)
        normalized_location = normalize_location(location) if location else None

        return CanonicalJobPayload(
            source_name="serp1",
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

    @staticmethod
    def _coerce_str(value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _coerce_int(value: object, default: int | None = None) -> int:
        try:
            if value is None:
                if default is None:
                    raise ValueError("no default")
                return default
            return int(value)
        except (TypeError, ValueError):
            if default is None:
                raise
            return default

    @staticmethod
    def _coerce_optional_int(value: object) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_float(value: object, default: float) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _coerce_employment_type(cls, value: object) -> list[str] | None:
        if value is None:
            return None
        allowed = {"fulltime", "partime", "contractor", "intern"}
        if isinstance(value, str):
            parts = [p.strip().lower() for p in value.split(",") if p.strip()]
        elif isinstance(value, (list, tuple, set)):
            parts = [cls._coerce_str(v).lower() for v in value if cls._coerce_str(v)]
        else:
            return None

        cleaned = [p for p in parts if p in allowed]
        return cleaned or None

    @staticmethod
    def _response_tasks(payload: object) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        tasks = payload.get("tasks")
        if not isinstance(tasks, list):
            return []
        return [task for task in tasks if isinstance(task, dict)]

    @staticmethod
    def _is_success_status(value: object) -> bool:
        try:
            code = int(value)
        except (TypeError, ValueError):
            return False
        return 20000 <= code < 30000

    def _submit_task(
        self,
        client: httpx.Client,
        task_post_url: str,
        task_payload: dict[str, Any],
    ) -> str | None:
        response = client.post(task_post_url, json=[task_payload])
        response.raise_for_status()
        payload = response.json()

        if not self._is_success_status((payload or {}).get("status_code")):
            return None

        for task in self._response_tasks(payload):
            if not self._is_success_status(task.get("status_code")):
                continue
            task_id = self._coerce_str(task.get("id"))
            if task_id:
                return task_id
        return None

    def _poll_until_ready(
        self,
        client: httpx.Client,
        tasks_ready_url: str,
        task_id: str,
        max_attempts: int,
        poll_interval_seconds: float,
        timeout_seconds: float,
    ) -> bool:
        start = time.monotonic()
        for attempt in range(1, max_attempts + 1):
            if time.monotonic() - start > timeout_seconds:
                return False

            response = client.get(tasks_ready_url)
            response.raise_for_status()
            payload = response.json()
            if not self._is_success_status((payload or {}).get("status_code")):
                return False

            ready_ids = self._extract_ready_task_ids(payload)
            if task_id in ready_ids:
                return True

            if attempt < max_attempts:
                time.sleep(poll_interval_seconds)

        return False

    def _get_advanced_result(
        self,
        client: httpx.Client,
        advanced_url: str,
    ) -> dict[str, Any] | None:
        response = client.get(advanced_url)
        response.raise_for_status()
        payload = response.json()

        if not self._is_success_status((payload or {}).get("status_code")):
            return None

        for task in self._response_tasks(payload):
            if not self._is_success_status(task.get("status_code")):
                continue
            result = task.get("result")
            if isinstance(result, list) and result:
                first = result[0]
                if isinstance(first, dict):
                    return first
        return {"items": []}

    @staticmethod
    def _extract_ready_task_ids(payload: object) -> set[str]:
        ready_ids: set[str] = set()
        if not isinstance(payload, dict):
            return ready_ids

        tasks = payload.get("tasks")
        if not isinstance(tasks, list):
            return ready_ids

        for task in tasks:
            if not isinstance(task, dict):
                continue
            if not Serp1Connector._is_success_status(task.get("status_code")):
                continue
            result = task.get("result")
            if not isinstance(result, list):
                continue
            for item in result:
                if not isinstance(item, dict):
                    continue
                task_id = item.get("id")
                if task_id:
                    ready_ids.add(str(task_id))
        return ready_ids

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None

        normalized = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

        formats = [
            "%Y-%m-%d %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _derive_external_id(
        title: str,
        company: str,
        location: str | None,
        source_url: str | None,
        timestamp: str,
    ) -> str:
        stable_input = "|".join(
            [
                title.strip().lower(),
                company.strip().lower(),
                (location or "").strip().lower(),
                (source_url or "").strip().lower(),
                timestamp.strip().lower(),
            ]
        )
        digest = hashlib.sha256(stable_input.encode("utf-8")).hexdigest()[:24]
        return f"serp1-{digest}"

    @staticmethod
    def _format_http_status_error(err: httpx.HTTPStatusError) -> str:
        response = err.response
        detail = response.text.strip() if response is not None else ""
        if response is not None and detail:
            return f"DataForSEO HTTP error {response.status_code}: {detail}"
        if response is not None:
            return f"DataForSEO HTTP error {response.status_code}"
        return str(err)


def create_serp1_connector(
    login: str | None = None,
    password: str | None = None,
    base_url: str | None = None,
    location_name: str | None = None,
    language_name: str | None = None,
    poll_max_attempts: int | None = None,
    poll_interval_seconds: float | None = None,
    poll_timeout_seconds: float | None = None,
) -> Serp1Connector:
    """Factory for DataForSEO-backed SERP1 connector."""
    settings = Settings()
    config = Serp1ConnectorConfig(
        login=login if login is not None else settings.dataforseo_login,
        password=password if password is not None else settings.dataforseo_password,
        base_url=base_url if base_url is not None else settings.dataforseo_base_url,
        location_name=(
            location_name
            if location_name is not None
            else settings.dataforseo_location_name
        ),
        language_name=(
            language_name
            if language_name is not None
            else settings.dataforseo_language_name
        ),
        poll_max_attempts=(
            poll_max_attempts
            if poll_max_attempts is not None
            else settings.dataforseo_poll_max_attempts
        ),
        poll_interval_seconds=(
            poll_interval_seconds
            if poll_interval_seconds is not None
            else settings.dataforseo_poll_interval_seconds
        ),
        poll_timeout_seconds=(
            poll_timeout_seconds
            if poll_timeout_seconds is not None
            else settings.dataforseo_poll_timeout_seconds
        ),
    )
    return Serp1Connector(config)
