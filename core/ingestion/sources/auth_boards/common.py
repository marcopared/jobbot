from __future__ import annotations

from typing import Any, Iterable

from core.ingestion.backends.base import AcquisitionBackend
from core.ingestion.backends.bb_browser_backend import BbBrowserSessionBackend
from core.ingestion.source_policies import get_source_policy
from core.ingestion.sources.public_boards.common import (
    DEFAULT_HEADERS,
    BasePublicBoardSourceAdapter,
)
from core.ingestion.types import AcquisitionRequest, FetchMode, SourcePolicy


class BaseAuthBoardSourceAdapter(BasePublicBoardSourceAdapter):
    default_wait_for_selector = "body"
    default_wait_selector_state = "attached"

    def __init__(
        self,
        *,
        source_name: str,
        policy: SourcePolicy | None = None,
        backend: AcquisitionBackend | None = None,
    ) -> None:
        resolved_policy = policy or get_source_policy(source_name)
        super().__init__(
            source_name=source_name,
            policy=resolved_policy,
            backend=backend or BbBrowserSessionBackend(),
        )

    def build_listing_request(self, **params: Any) -> AcquisitionRequest:
        return self._build_browser_request(
            urls=(self.listing_url,),
            **params,
        )

    def build_detail_request(self, *, detail_urls: Iterable[str], **params: Any) -> AcquisitionRequest:
        return self._build_browser_request(
            urls=tuple(dict.fromkeys(detail_urls)),
            **params,
        )

    def _build_browser_request(
        self,
        *,
        urls: tuple[str, ...],
        **params: Any,
    ) -> AcquisitionRequest:
        session_config = {
            "session_name": str(params.get("session_name") or self.source_name),
            "auth_required": True,
            "sequential_mode": True,
            "source_scope": self.source_name,
        }
        return AcquisitionRequest(
            urls=urls,
            fetch_mode=FetchMode.DYNAMIC,
            headers=DEFAULT_HEADERS,
            session_config=session_config,
            wait_for_selector=str(params.get("wait_for_selector") or self.default_wait_for_selector),
            wait_selector_state=str(
                params.get("wait_selector_state") or self.default_wait_selector_state
            ),
            wait_after_ms=int(params.get("wait_after_ms", 750)),
            timeout_ms=int(params.get("timeout_ms", 45_000)),
            extraction_hints={
                "capture_network": True,
                "capture_html": True,
                "capture_text": True,
                "source_kind": "browser_auth",
            },
            metadata={
                "backend_preference": "bb_browser",
                "source_name": self.source_name,
                "requires_auth": True,
            },
        )
