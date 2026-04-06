from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Mapping, Protocol
from urllib.parse import urljoin

import httpx

from core.ingestion.types import AcquisitionRequest


@dataclass(frozen=True)
class BbBrowserClientConfig:
    base_url: str
    capture_path: str = "/session/acquire"
    api_key: str | None = None
    request_timeout_ms: int = 45_000
    connect_timeout_ms: int = 5_000
    default_session_name: str = "jobbot-ingestion"
    verify_ssl: bool = True

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "BbBrowserClientConfig":
        resolved = environ or os.environ
        return cls(
            base_url=resolved.get("BB_BROWSER_BASE_URL", "http://127.0.0.1:9223"),
            capture_path=resolved.get("BB_BROWSER_CAPTURE_PATH", "/session/acquire"),
            api_key=cls._clean_optional_string(resolved.get("BB_BROWSER_API_KEY")),
            request_timeout_ms=cls._coerce_int(
                resolved.get("BB_BROWSER_TIMEOUT_MS"),
                default=45_000,
            ),
            connect_timeout_ms=cls._coerce_int(
                resolved.get("BB_BROWSER_CONNECT_TIMEOUT_MS"),
                default=5_000,
            ),
            default_session_name=resolved.get("BB_BROWSER_SESSION_NAME", "jobbot-ingestion"),
            verify_ssl=cls._coerce_bool(
                resolved.get("BB_BROWSER_VERIFY_SSL"),
                default=True,
            ),
        )

    @staticmethod
    def _coerce_int(value: str | None, *, default: int) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_bool(value: str | None, *, default: bool) -> bool:
        if value is None:
            return default
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default

    @staticmethod
    def _clean_optional_string(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


@dataclass(frozen=True)
class BbBrowserPageCapture:
    requested_url: str
    final_url: str | None = None
    status_code: int | None = None
    html: str | None = None
    text_snapshot: str | None = None
    content_type: str | None = None
    response_headers: Mapping[str, Any] | None = None
    network_events: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    session_name: str | None = None


class BbBrowserTransport(Protocol):
    def capture(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        raise NotImplementedError


class HttpxBbBrowserTransport:
    def __init__(
        self,
        *,
        config: BbBrowserClientConfig,
        client_factory: Any = httpx.Client,
    ) -> None:
        self._config = config
        self._client_factory = client_factory

    def capture(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        timeout = httpx.Timeout(
            timeout=self._config.request_timeout_ms / 1000.0,
            connect=self._config.connect_timeout_ms / 1000.0,
        )
        endpoint = urljoin(self._config.base_url.rstrip("/") + "/", self._config.capture_path.lstrip("/"))

        with self._client_factory(timeout=timeout, verify=self._config.verify_ssl, headers=headers) as client:
            response = client.post(endpoint, json=dict(payload))
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, Mapping):
            raise ValueError("bb-browser transport returned a non-object response")
        return dict(data)


class BbBrowserClient:
    def __init__(
        self,
        *,
        config: BbBrowserClientConfig | None = None,
        transport: BbBrowserTransport | None = None,
    ) -> None:
        resolved_config = config or BbBrowserClientConfig.from_env()
        self._config = resolved_config
        self._transport = transport or HttpxBbBrowserTransport(config=resolved_config)

    @property
    def config(self) -> BbBrowserClientConfig:
        return self._config

    def capture_page(
        self,
        *,
        source_name: str,
        request: AcquisitionRequest,
        url: str,
    ) -> BbBrowserPageCapture:
        payload = self._build_capture_payload(
            source_name=source_name,
            request=request,
            url=url,
        )
        response = self._transport.capture(payload)
        return self._coerce_capture(
            requested_url=url,
            response=response,
            request=request,
        )

    def _build_capture_payload(
        self,
        *,
        source_name: str,
        request: AcquisitionRequest,
        url: str,
    ) -> dict[str, Any]:
        session_config = dict(request.session_config)
        session_config.setdefault("session_name", self._config.default_session_name)
        session_config.setdefault("sequential_mode", True)

        payload: dict[str, Any] = {
            "source_name": source_name,
            "url": url,
            "method": request.method,
            "headers": dict(request.headers),
            "cookies": dict(request.cookies),
            "query_params": dict(request.query_params),
            "session_config": session_config,
            "timeout_ms": request.timeout_ms,
            "wait_for_selector": request.wait_for_selector,
            "wait_selector_state": request.wait_selector_state,
            "wait_after_ms": request.wait_after_ms,
            "fetch_mode": request.fetch_mode.value,
            "metadata": dict(request.metadata),
            "extraction_hints": dict(request.extraction_hints),
        }
        if request.fallback_fetch_mode is not None:
            payload["fallback_fetch_mode"] = request.fallback_fetch_mode.value
        if request.body is not None:
            payload["body"] = request.body
        return payload

    def _coerce_capture(
        self,
        *,
        requested_url: str,
        response: Mapping[str, Any],
        request: AcquisitionRequest,
    ) -> BbBrowserPageCapture:
        payload = response.get("capture")
        if isinstance(payload, Mapping):
            data = payload
        else:
            data = response

        network_events = data.get("network") or data.get("network_events") or []
        if not isinstance(network_events, list):
            network_events = []

        response_headers = data.get("response_headers") or data.get("headers")
        if not isinstance(response_headers, Mapping):
            response_headers = None

        metadata = data.get("metadata")
        if not isinstance(metadata, Mapping):
            metadata = {}

        session_name = data.get("session_name")
        if not session_name:
            session_name = request.session_config.get("session_name") or self._config.default_session_name

        return BbBrowserPageCapture(
            requested_url=requested_url,
            final_url=self._clean_string(data.get("final_url") or data.get("url")) or requested_url,
            status_code=self._coerce_int(data.get("status_code")),
            html=self._clean_string(data.get("html")),
            text_snapshot=self._clean_string(
                data.get("text")
                or data.get("dom_text")
                or data.get("snapshot_text")
            ),
            content_type=self._clean_string(data.get("content_type")),
            response_headers=dict(response_headers) if response_headers is not None else None,
            network_events=tuple(
                dict(event)
                for event in network_events
                if isinstance(event, Mapping)
            ),
            metadata=dict(metadata),
            session_name=self._clean_string(session_name),
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
