from __future__ import annotations

import httpx

from core.ingestion.backends.bb_browser_backend import BbBrowserSessionBackend
from core.ingestion.backends.bb_browser_client import BbBrowserPageCapture
from core.ingestion.registry import build_default_backend_registry
from core.ingestion.types import AcquisitionRequest, FetchMode

from tests.bb_browser_test_support import FakeBbBrowserClient


def test_backend_registry_registers_bb_browser_backend():
    backend = build_default_backend_registry().create("bb_browser")
    assert backend.name == "bb_browser"


def test_bb_browser_backend_builds_session_acquisition_record():
    client = FakeBbBrowserClient(
        {
            "https://www.linkedin.com/jobs/search/": BbBrowserPageCapture(
                requested_url="https://www.linkedin.com/jobs/search/",
                final_url="https://www.linkedin.com/jobs/search/?currentJobId=1",
                status_code=200,
                html="<html><body>linkedin</body></html>",
                text_snapshot="linkedin",
                content_type="text/html",
                response_headers={"content-type": "text/html"},
                network_events=(
                    {"url": "https://api.linkedin.com/jobs", "method": "GET", "status": 200},
                ),
                metadata={"bridge": "bb-browser", "dom_snapshot": True},
                session_name="linkedin-session",
            )
        }
    )
    backend = BbBrowserSessionBackend(client=client)

    batch = backend.acquire(
        "linkedin_jobs",
        request=AcquisitionRequest(
            url="https://www.linkedin.com/jobs/search/",
            fetch_mode=FetchMode.DYNAMIC,
            session_config={"auth_required": True, "session_name": "linkedin-session"},
            wait_for_selector=".jobs-search-results",
            wait_selector_state="visible",
            wait_after_ms=700,
            timeout_ms=40_000,
        ),
    )

    assert batch.error is None
    assert batch.stats == {"fetched": 1, "errors": 0}
    assert batch.metadata["backend"] == "bb_browser"

    record = batch.records[0]
    assert record.raw_payload == "<html><body>linkedin</body></html>"
    assert record.provenance.connector_version == "bb_browser"
    assert record.artifact is not None
    assert record.artifact.final_url == "https://www.linkedin.com/jobs/search/?currentJobId=1"
    assert record.capture_metadata == {
        "backend": "bb_browser",
        "fetch_mode": "dynamic",
        "acquisition_mode": "browser_session",
        "session_name": "linkedin-session",
        "auth_required": True,
        "timeout_ms": 40_000,
        "requested_url": "https://www.linkedin.com/jobs/search/",
        "wait_for_selector": ".jobs-search-results",
        "wait_selector_state": "visible",
        "wait_after_ms": 700,
        "network_events": [
            {"url": "https://api.linkedin.com/jobs", "method": "GET", "status": 200}
        ],
        "browser_metadata": {"bridge": "bb-browser", "dom_snapshot": True},
        "content_variant": "html",
    }


def test_bb_browser_backend_returns_network_error_when_client_unavailable():
    request = httpx.Request("POST", "http://127.0.0.1:9223/session/acquire")
    client = FakeBbBrowserClient(
        {
            "https://wellfound.com/jobs": httpx.ConnectError(
                "connection refused",
                request=request,
            )
        }
    )
    backend = BbBrowserSessionBackend(client=client)

    batch = backend.acquire(
        "wellfound",
        request=AcquisitionRequest(
            url="https://wellfound.com/jobs",
            fetch_mode=FetchMode.DYNAMIC,
        ),
    )

    assert batch.records == []
    assert batch.stats == {"fetched": 0, "errors": 1}
    assert batch.error_type == "network_error"
    assert "connection refused" in (batch.error or "")
