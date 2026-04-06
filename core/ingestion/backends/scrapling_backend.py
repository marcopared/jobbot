from __future__ import annotations

import importlib
from datetime import datetime, timezone
from typing import Any, Mapping

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.types import (
    AcquisitionArtifact,
    AcquisitionBatch,
    AcquisitionError,
    AcquisitionErrorType,
    AcquisitionProvenance,
    AcquisitionRecord,
    AcquisitionRequest,
    FetchMode,
)


class ScraplingFetchBackend(AcquisitionBackend):
    def __init__(self, *, fetchers_module: Any | None = None) -> None:
        self._fetchers_module = fetchers_module

    @property
    def name(self) -> str:
        return "scrapling"

    def acquire(self, source_name: str, **kwargs: Any) -> AcquisitionBatch:
        try:
            request = self._coerce_request(**kwargs)
        except Exception as exc:
            error = self._classify_error(exc, mode=None)
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
            record, failure = self._acquire_url(
                source_name=source_name,
                request=request,
                url=url,
            )
            if record is not None:
                records.append(record)
                continue
            if failure is not None:
                failures.append(failure)

        error = None
        error_type = None
        if failures and not records:
            error = failures[0].message
            error_type = failures[0].error_type

        metadata: dict[str, Any] = {
            "source_name": source_name,
            "requested_urls": list(request.urls),
            "fetch_mode": request.fetch_mode.value,
        }
        if request.fallback_fetch_mode is not None:
            metadata["fallback_fetch_mode"] = request.fallback_fetch_mode.value
        if request.extraction_hints:
            metadata["extraction_hints"] = dict(request.extraction_hints)
        if failures:
            metadata["failures"] = [self._serialize_error(failure) for failure in failures]

        return AcquisitionBatch(
            records=records,
            stats={
                "fetched": len(records),
                "errors": len(failures),
            },
            error=error,
            error_type=error_type,
            metadata=metadata,
        )

    def _acquire_url(
        self,
        *,
        source_name: str,
        request: AcquisitionRequest,
        url: str,
    ) -> tuple[AcquisitionRecord | None, AcquisitionError | None]:
        attempted_modes = [request.fetch_mode]
        if request.fallback_fetch_mode and request.fallback_fetch_mode not in attempted_modes:
            attempted_modes.append(request.fallback_fetch_mode)

        last_error: AcquisitionError | None = None
        for attempt_index, mode in enumerate(attempted_modes):
            try:
                response = self._fetch(url=url, request=request, mode=mode)
                http_error = self._error_from_status(response=response, mode=mode, url=url)
                if http_error is not None:
                    last_error = http_error
                    continue
                return (
                    self._build_record(
                        source_name=source_name,
                        request=request,
                        requested_url=url,
                        response=response,
                        mode=mode,
                        attempted_modes=[candidate.value for candidate in attempted_modes[: attempt_index + 1]],
                    ),
                    None,
                )
            except Exception as exc:
                last_error = self._classify_error(exc, mode=mode)
                continue

        return None, last_error

    def _fetch(self, *, url: str, request: AcquisitionRequest, mode: FetchMode) -> Any:
        if mode == FetchMode.SIMPLE:
            return self._fetch_simple(url=url, request=request)
        if mode == FetchMode.DYNAMIC:
            return self._fetch_dynamic(url=url, request=request)
        raise ValueError(f"Unsupported fetch mode: {mode}")

    def _fetch_simple(self, *, url: str, request: AcquisitionRequest) -> Any:
        fetchers = self._load_fetchers_module()
        session_cls = getattr(fetchers, "FetcherSession", None)
        request_kwargs = self._build_request_kwargs(request=request, mode=FetchMode.SIMPLE)
        session_kwargs = self._build_session_kwargs(request=request, mode=FetchMode.SIMPLE)

        if session_cls is not None:
            with session_cls(**session_kwargs) as session:
                method = getattr(session, request.method.lower(), None)
                if method is None:
                    raise ValueError(f"Unsupported HTTP method for Scrapling simple mode: {request.method}")
                return method(url, **request_kwargs)

        fetcher = getattr(fetchers, "Fetcher", None)
        if fetcher is None:
            raise ModuleNotFoundError("scrapling.fetchers.Fetcher is unavailable")

        method = getattr(fetcher, request.method.lower(), None)
        if method is None:
            raise ValueError(f"Unsupported HTTP method for Scrapling simple mode: {request.method}")
        return method(url, **{**session_kwargs, **request_kwargs})

    def _fetch_dynamic(self, *, url: str, request: AcquisitionRequest) -> Any:
        fetchers = self._load_fetchers_module()
        session_cls = getattr(fetchers, "DynamicSession", None)
        request_kwargs = self._build_request_kwargs(request=request, mode=FetchMode.DYNAMIC)
        session_kwargs = self._build_session_kwargs(request=request, mode=FetchMode.DYNAMIC)

        if session_cls is not None:
            with session_cls(**session_kwargs) as session:
                return session.fetch(url, **request_kwargs)

        fetcher = getattr(fetchers, "DynamicFetcher", None)
        if fetcher is None:
            raise ModuleNotFoundError("scrapling.fetchers.DynamicFetcher is unavailable")
        return fetcher.fetch(url, **{**session_kwargs, **request_kwargs})

    def _build_record(
        self,
        *,
        source_name: str,
        request: AcquisitionRequest,
        requested_url: str,
        response: Any,
        mode: FetchMode,
        attempted_modes: list[str],
    ) -> AcquisitionRecord:
        response_headers = self._mapping_or_none(getattr(response, "headers", None))
        content_type = None
        if response_headers is not None:
            content_type = str(response_headers.get("content-type") or "").strip() or None

        content = self._extract_content(response)
        final_url = self._coerce_final_url(response=response, requested_url=requested_url)
        status_code = self._coerce_status_code(response)
        response_meta = self._mapping_or_none(getattr(response, "meta", None))

        capture_metadata: dict[str, Any] = {
            "fetch_mode": mode.value,
            "attempted_modes": attempted_modes,
            "used_fallback": attempted_modes[-1] != request.fetch_mode.value,
            "timeout_ms": request.timeout_ms,
        }
        if request.wait_for_selector:
            capture_metadata["wait_for_selector"] = request.wait_for_selector
        if request.wait_selector_state:
            capture_metadata["wait_selector_state"] = request.wait_selector_state
        if request.wait_after_ms is not None:
            capture_metadata["wait_after_ms"] = request.wait_after_ms
        if response_meta:
            capture_metadata["response_meta"] = response_meta

        return AcquisitionRecord(
            raw_payload=content,
            provenance=AcquisitionProvenance(
                fetch_timestamp=datetime.now(timezone.utc).isoformat(),
                source_url=requested_url,
                connector_version="scrapling",
            ),
            capture_metadata=capture_metadata,
            debug_metadata={
                "source_name": source_name,
                "requested_url": requested_url,
            },
            artifact=AcquisitionArtifact(
                content=content,
                content_type=content_type,
                final_url=final_url,
                status_code=status_code,
                response_headers=response_headers,
            ),
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
            raise ValueError("ScraplingFetchBackend requires an AcquisitionRequest or request fields")

        return AcquisitionRequest(**payload)

    def _build_request_kwargs(self, *, request: AcquisitionRequest, mode: FetchMode) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "timeout": request.timeout_ms,
        }
        if request.query_params:
            kwargs["params"] = dict(request.query_params)
        if request.body is not None:
            if isinstance(request.body, (dict, list)):
                kwargs["json"] = request.body
            else:
                kwargs["data"] = request.body

        if mode == FetchMode.DYNAMIC:
            if request.wait_for_selector:
                kwargs["wait_selector"] = request.wait_for_selector
            if request.wait_selector_state:
                kwargs["wait_selector_state"] = request.wait_selector_state
            if request.wait_after_ms is not None:
                kwargs["wait"] = request.wait_after_ms
            if request.headers:
                kwargs["extra_headers"] = dict(request.headers)
        elif request.headers:
            kwargs["headers"] = dict(request.headers)

        return kwargs

    def _build_session_kwargs(self, *, request: AcquisitionRequest, mode: FetchMode) -> dict[str, Any]:
        session_kwargs = dict(request.session_config)
        if request.cookies:
            session_kwargs.setdefault("cookies", dict(request.cookies))

        if mode == FetchMode.DYNAMIC:
            if request.headers:
                session_kwargs.setdefault("extra_headers", dict(request.headers))
        elif request.headers:
            session_kwargs.setdefault("headers", dict(request.headers))

        return session_kwargs

    def _load_fetchers_module(self) -> Any:
        if self._fetchers_module is None:
            self._fetchers_module = importlib.import_module("scrapling.fetchers")
        return self._fetchers_module

    def _error_from_status(self, *, response: Any, mode: FetchMode, url: str) -> AcquisitionError | None:
        status_code = self._coerce_status_code(response)
        if status_code is None or status_code < 400:
            return None

        error_type = (
            AcquisitionErrorType.BLOCKED.value
            if status_code in {401, 403, 429}
            else AcquisitionErrorType.HTTP_ERROR.value
        )
        return AcquisitionError(
            error_type=error_type,
            message=f"{mode.value} fetch returned HTTP {status_code} for {url}",
            retryable=status_code in {408, 429, 500, 502, 503, 504},
            status_code=status_code,
            metadata={"fetch_mode": mode.value},
        )

    def _classify_error(self, exc: Exception, *, mode: FetchMode | None) -> AcquisitionError:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        message = str(exc).strip() or exc.__class__.__name__
        exc_name = exc.__class__.__name__.lower()
        lower_message = message.lower()

        if isinstance(exc, ModuleNotFoundError):
            error_type = AcquisitionErrorType.MISSING_DEPENDENCY.value
            retryable = False
        elif isinstance(exc, ValueError):
            error_type = AcquisitionErrorType.INVALID_REQUEST.value
            retryable = False
        elif "timeout" in exc_name or "timeout" in lower_message:
            error_type = AcquisitionErrorType.TIMEOUT.value
            retryable = True
        elif status_code in {401, 403, 429}:
            error_type = AcquisitionErrorType.BLOCKED.value
            retryable = status_code in {429}
        elif "httpstatuserror" in exc_name:
            error_type = AcquisitionErrorType.HTTP_ERROR.value
            retryable = status_code in {408, 429, 500, 502, 503, 504}
        elif "requesterror" in exc_name or "connection" in lower_message or "network" in lower_message:
            error_type = AcquisitionErrorType.NETWORK_ERROR.value
            retryable = True
        elif mode == FetchMode.DYNAMIC:
            error_type = AcquisitionErrorType.BROWSER_ERROR.value
            retryable = True
        else:
            error_type = AcquisitionErrorType.UNKNOWN.value
            retryable = False

        metadata: dict[str, Any] = {}
        if mode is not None:
            metadata["fetch_mode"] = mode.value
        if status_code is not None:
            metadata["status_code"] = status_code

        return AcquisitionError(
            error_type=error_type,
            message=message,
            retryable=retryable,
            status_code=status_code,
            metadata=metadata,
        )

    def _coerce_status_code(self, response: Any) -> int | None:
        value = getattr(response, "status", None)
        if value is None:
            value = getattr(response, "status_code", None)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _coerce_final_url(self, *, response: Any, requested_url: str) -> str:
        final_url = getattr(response, "url", None)
        if final_url is None:
            return requested_url
        return str(final_url)

    def _extract_content(self, response: Any) -> str | bytes | None:
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text

        body = getattr(response, "body", None)
        if isinstance(body, str):
            return body
        if isinstance(body, bytes):
            encoding = getattr(response, "encoding", None) or "utf-8"
            try:
                return body.decode(encoding, errors="replace")
            except LookupError:
                return body.decode("utf-8", errors="replace")
        return None

    def _mapping_or_none(self, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, Mapping):
            return {str(key): value[key] for key in value}
        items = getattr(value, "items", None)
        if callable(items):
            return {str(key): item for key, item in items()}
        return None

    def _serialize_error(self, error: AcquisitionError) -> dict[str, Any]:
        return {
            "error_type": error.error_type,
            "message": error.message,
            "retryable": error.retryable,
            "status_code": error.status_code,
            "metadata": dict(error.metadata),
        }
