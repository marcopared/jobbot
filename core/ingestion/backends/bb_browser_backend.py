from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import httpx

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.backends.bb_browser_client import (
    BbBrowserClient,
    BbBrowserPageCapture,
)
from core.ingestion.types import (
    AcquisitionArtifact,
    AcquisitionBatch,
    AcquisitionError,
    AcquisitionErrorType,
    AcquisitionProvenance,
    AcquisitionRecord,
    AcquisitionRequest,
)


class BbBrowserSessionBackend(AcquisitionBackend):
    def __init__(self, *, client: BbBrowserClient | None = None) -> None:
        self._client = client or BbBrowserClient()

    @property
    def name(self) -> str:
        return "bb_browser"

    def acquire(self, source_name: str, **kwargs: Any) -> AcquisitionBatch:
        try:
            request = self._coerce_request(**kwargs)
        except Exception as exc:
            error = self._classify_error(exc)
            return AcquisitionBatch(
                records=[],
                stats={"fetched": 0, "errors": 1},
                error=error.message,
                error_type=error.error_type,
                metadata={
                    "source_name": source_name,
                    "failures": [self._serialize_error(error)],
                },
            )

        records: list[AcquisitionRecord] = []
        failures: list[AcquisitionError] = []

        for url in request.urls:
            try:
                capture = self._client.capture_page(
                    source_name=source_name,
                    request=request,
                    url=url,
                )
                capture_error = self._error_from_capture(capture)
                if capture_error is not None:
                    failures.append(capture_error)
                    continue
                records.append(
                    self._build_record(
                        source_name=source_name,
                        request=request,
                        capture=capture,
                    )
                )
            except Exception as exc:
                failures.append(self._classify_error(exc))

        error = failures[0].message if failures and not records else None
        error_type = failures[0].error_type if failures and not records else None
        metadata: dict[str, Any] = {
            "source_name": source_name,
            "requested_urls": list(request.urls),
            "fetch_mode": request.fetch_mode.value,
            "backend": self.name,
        }
        if failures:
            metadata["failures"] = [self._serialize_error(failure) for failure in failures]

        return AcquisitionBatch(
            records=records,
            stats={"fetched": len(records), "errors": len(failures)},
            error=error,
            error_type=error_type,
            metadata=metadata,
        )

    def _coerce_request(self, **kwargs: Any) -> AcquisitionRequest:
        request = kwargs.get("request") or kwargs.get("backend_request")
        if isinstance(request, AcquisitionRequest):
            return request
        if request is not None:
            raise TypeError("request must be an AcquisitionRequest")

        request_keys = {
            "url",
            "urls",
            "method",
            "query_params",
            "headers",
            "cookies",
            "session_config",
            "fetch_mode",
            "fallback_fetch_mode",
            "wait_for_selector",
            "wait_selector_state",
            "timeout_ms",
            "wait_after_ms",
            "extraction_hints",
            "body",
            "metadata",
        }
        payload = {key: value for key, value in kwargs.items() if key in request_keys}
        if not payload:
            raise ValueError("BbBrowserSessionBackend requires an AcquisitionRequest or request fields")
        return AcquisitionRequest(**payload)

    def _build_record(
        self,
        *,
        source_name: str,
        request: AcquisitionRequest,
        capture: BbBrowserPageCapture,
    ) -> AcquisitionRecord:
        content = capture.html or capture.text_snapshot
        capture_metadata: dict[str, Any] = {
            "backend": self.name,
            "fetch_mode": request.fetch_mode.value,
            "acquisition_mode": "browser_session",
            "session_name": capture.session_name,
            "auth_required": bool(request.session_config.get("auth_required", False)),
            "timeout_ms": request.timeout_ms,
            "requested_url": capture.requested_url,
        }
        if request.wait_for_selector:
            capture_metadata["wait_for_selector"] = request.wait_for_selector
        if request.wait_selector_state:
            capture_metadata["wait_selector_state"] = request.wait_selector_state
        if request.wait_after_ms is not None:
            capture_metadata["wait_after_ms"] = request.wait_after_ms
        if capture.network_events:
            capture_metadata["network_events"] = self._summarize_network_events(capture.network_events)
        if capture.metadata:
            capture_metadata["browser_metadata"] = dict(capture.metadata)
        if capture.text_snapshot and not capture.html:
            capture_metadata["content_variant"] = "text_snapshot"
        elif capture.html:
            capture_metadata["content_variant"] = "html"

        return AcquisitionRecord(
            raw_payload=content,
            provenance=AcquisitionProvenance(
                fetch_timestamp=datetime.now(timezone.utc).isoformat(),
                source_url=capture.requested_url,
                connector_version=self.name,
            ),
            capture_metadata=capture_metadata,
            debug_metadata={
                "source_name": source_name,
                "final_url": capture.final_url,
            },
            artifact=AcquisitionArtifact(
                content=content,
                content_type=capture.content_type,
                final_url=capture.final_url,
                status_code=capture.status_code,
                response_headers=capture.response_headers,
            ),
        )

    def _summarize_network_events(
        self,
        events: tuple[Mapping[str, Any], ...],
    ) -> list[dict[str, Any]]:
        summarized: list[dict[str, Any]] = []
        for event in events[:25]:
            summary = {
                "url": self._clean_string(event.get("url")),
                "method": self._clean_string(event.get("method")),
                "status": self._coerce_int(event.get("status")),
                "resource_type": self._clean_string(event.get("resource_type")),
            }
            summarized.append({key: value for key, value in summary.items() if value is not None})
        return summarized

    def _error_from_capture(self, capture: BbBrowserPageCapture) -> AcquisitionError | None:
        status_code = capture.status_code
        if status_code is None or status_code < 400:
            return None

        error_type = (
            AcquisitionErrorType.BLOCKED.value
            if status_code in {401, 403, 429}
            else AcquisitionErrorType.HTTP_ERROR.value
        )
        return AcquisitionError(
            error_type=error_type,
            message=f"bb-browser session capture returned HTTP {status_code} for {capture.requested_url}",
            retryable=status_code in {408, 429, 500, 502, 503, 504},
            status_code=status_code,
            metadata={"backend": self.name},
        )

    def _classify_error(self, exc: Exception) -> AcquisitionError:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        message = str(exc).strip() or exc.__class__.__name__

        if isinstance(exc, ValueError):
            error_type = AcquisitionErrorType.INVALID_REQUEST.value
            retryable = False
        elif isinstance(exc, httpx.TimeoutException) or "timeout" in message.lower():
            error_type = AcquisitionErrorType.TIMEOUT.value
            retryable = True
        elif isinstance(exc, httpx.HTTPStatusError):
            error_type = (
                AcquisitionErrorType.BLOCKED.value
                if status_code in {401, 403, 429}
                else AcquisitionErrorType.HTTP_ERROR.value
            )
            retryable = status_code in {408, 429, 500, 502, 503, 504}
        elif isinstance(exc, (httpx.RequestError, ConnectionError)):
            error_type = AcquisitionErrorType.NETWORK_ERROR.value
            retryable = True
        else:
            error_type = AcquisitionErrorType.BROWSER_ERROR.value
            retryable = True

        return AcquisitionError(
            error_type=error_type,
            message=message,
            retryable=retryable,
            status_code=status_code,
            metadata={"backend": self.name},
        )

    def _coerce_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _clean_string(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _serialize_error(self, error: AcquisitionError) -> dict[str, Any]:
        return {
            "error_type": error.error_type,
            "message": error.message,
            "retryable": error.retryable,
            "status_code": error.status_code,
            "metadata": dict(error.metadata),
        }
