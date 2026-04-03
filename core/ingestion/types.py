from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class SourceKind(str, Enum):
    CANONICAL_API = "canonical_api"
    PUBLIC_BOARD = "public_board"
    DYNAMIC_BOARD = "dynamic_board"
    BROWSER_AUTH = "browser_auth"


class BackendPreference(str, Enum):
    LEGACY_CONNECTOR = "legacy_connector"
    LEGACY_SCRAPER = "legacy_scraper"
    SCRAPLING = "scrapling"
    BB_BROWSER = "bb_browser"


class FetchMode(str, Enum):
    SIMPLE = "simple"
    DYNAMIC = "dynamic"


class AcquisitionErrorType(str, Enum):
    BLOCKED = "blocked"
    BROWSER_ERROR = "browser_error"
    HTTP_ERROR = "http_error"
    INVALID_REQUEST = "invalid_request"
    MISSING_DEPENDENCY = "missing_dependency"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SourcePolicy:
    source_name: str
    source_kind: SourceKind
    source_role_default: str
    requires_auth: bool
    backend_preference: str
    feature_flag_key: str | None = None


@dataclass(frozen=True)
class AcquisitionProvenance:
    fetch_timestamp: str
    source_url: str
    connector_version: str = "v1"


@dataclass(frozen=True)
class AcquisitionRequest:
    url: str | None = None
    urls: tuple[str, ...] = ()
    method: str = "GET"
    query_params: Mapping[str, Any] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    cookies: Mapping[str, Any] = field(default_factory=dict)
    session_config: Mapping[str, Any] = field(default_factory=dict)
    fetch_mode: FetchMode = FetchMode.SIMPLE
    fallback_fetch_mode: FetchMode | None = None
    wait_for_selector: str | None = None
    wait_selector_state: str | None = None
    timeout_ms: int = 30_000
    wait_after_ms: int | None = None
    extraction_hints: Mapping[str, Any] = field(default_factory=dict)
    body: Any | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_urls: list[str] = []
        if self.url:
            normalized_urls.append(self.url)
        normalized_urls.extend(self.urls)
        normalized_urls = [candidate.strip() for candidate in normalized_urls if candidate and candidate.strip()]
        if not normalized_urls:
            raise ValueError("AcquisitionRequest requires at least one url")

        method = self.method.upper().strip()
        if not method:
            raise ValueError("AcquisitionRequest method cannot be empty")

        if self.timeout_ms <= 0:
            raise ValueError("AcquisitionRequest timeout_ms must be positive")

        fetch_mode = self.fetch_mode
        if isinstance(fetch_mode, str):
            fetch_mode = FetchMode(fetch_mode)

        fallback_fetch_mode = self.fallback_fetch_mode
        if isinstance(fallback_fetch_mode, str):
            fallback_fetch_mode = FetchMode(fallback_fetch_mode)

        object.__setattr__(self, "urls", tuple(normalized_urls))
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "fetch_mode", fetch_mode)
        object.__setattr__(self, "fallback_fetch_mode", fallback_fetch_mode)


@dataclass(frozen=True)
class AcquisitionArtifact:
    content: str | bytes | None
    content_type: str | None = None
    final_url: str | None = None
    status_code: int | None = None
    response_headers: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class AcquisitionError:
    error_type: str
    message: str
    retryable: bool = False
    status_code: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AcquisitionRecord:
    raw_payload: Any
    provenance: AcquisitionProvenance
    capture_metadata: Mapping[str, Any] | None = None
    debug_metadata: Mapping[str, Any] | None = None
    normalized_payload: Any | None = None
    artifact: AcquisitionArtifact | None = None
    error: AcquisitionError | None = None


@dataclass(frozen=True)
class AcquisitionBatch:
    records: list[AcquisitionRecord]
    stats: dict[str, int]
    error: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    error_type: str | None = None
