from __future__ import annotations

import pytest

from core.ingestion.backends.bb_browser_client import (
    BbBrowserClient,
    BbBrowserClientConfig,
)
from core.ingestion.types import AcquisitionRequest, FetchMode

from tests.bb_browser_test_support import FakeBbBrowserTransport


def test_bb_browser_client_builds_capture_payload_and_normalizes_response():
    transport = FakeBbBrowserTransport(
        responses={
            "https://www.linkedin.com/jobs/search/": {
                "capture": {
                    "final_url": "https://www.linkedin.com/jobs/search/?currentJobId=1",
                    "status_code": 200,
                    "html": "<html><body>ok</body></html>",
                    "text": "ok",
                    "content_type": "text/html",
                    "response_headers": {"content-type": "text/html"},
                    "network": [{"url": "https://api.linkedin.com/jobs", "method": "GET", "status": 200}],
                    "metadata": {"bridge": "bb-browser"},
                    "session_name": "linkedin-session",
                }
            }
        }
    )
    client = BbBrowserClient(
        config=BbBrowserClientConfig(
            base_url="http://127.0.0.1:9223",
            default_session_name="default-session",
        ),
        transport=transport,
    )

    capture = client.capture_page(
        source_name="linkedin_jobs",
        request=AcquisitionRequest(
            url="https://www.linkedin.com/jobs/search/",
            fetch_mode=FetchMode.DYNAMIC,
            headers={"User-Agent": "jobbot-test"},
            session_config={"auth_required": True},
            wait_for_selector=".jobs-search-results",
            wait_selector_state="visible",
            wait_after_ms=800,
            timeout_ms=25_000,
        ),
        url="https://www.linkedin.com/jobs/search/",
    )

    assert capture.final_url == "https://www.linkedin.com/jobs/search/?currentJobId=1"
    assert capture.html == "<html><body>ok</body></html>"
    assert capture.text_snapshot == "ok"
    assert capture.status_code == 200
    assert capture.session_name == "linkedin-session"
    assert capture.metadata == {"bridge": "bb-browser"}
    assert capture.network_events == (
        {"url": "https://api.linkedin.com/jobs", "method": "GET", "status": 200},
    )

    payload = transport.calls[0]
    assert payload["source_name"] == "linkedin_jobs"
    assert payload["url"] == "https://www.linkedin.com/jobs/search/"
    assert payload["fetch_mode"] == "dynamic"
    assert payload["headers"] == {"User-Agent": "jobbot-test"}
    assert payload["session_config"]["auth_required"] is True
    assert payload["session_config"]["session_name"] == "default-session"
    assert payload["session_config"]["sequential_mode"] is True
    assert payload["wait_for_selector"] == ".jobs-search-results"
    assert payload["wait_selector_state"] == "visible"
    assert payload["wait_after_ms"] == 800


def test_bb_browser_client_uses_top_level_response_shape_and_request_session_name():
    transport = FakeBbBrowserTransport(
        responses={
            "https://wellfound.com/jobs": {
                "final_url": "https://wellfound.com/jobs",
                "status_code": 200,
                "text": "fallback text",
            }
        }
    )
    client = BbBrowserClient(
        config=BbBrowserClientConfig(base_url="http://127.0.0.1:9223"),
        transport=transport,
    )

    capture = client.capture_page(
        source_name="wellfound",
        request=AcquisitionRequest(
            url="https://wellfound.com/jobs",
            fetch_mode=FetchMode.DYNAMIC,
            session_config={"session_name": "wellfound-session"},
        ),
        url="https://wellfound.com/jobs",
    )

    assert capture.html is None
    assert capture.text_snapshot == "fallback text"
    assert capture.session_name == "wellfound-session"


def test_bb_browser_client_config_from_env_uses_same_runtime_defaults_and_names(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BB_BROWSER_BASE_URL", "https://bb-browser.internal")
    monkeypatch.setenv("BB_BROWSER_CAPTURE_PATH", "/bridge/capture")
    monkeypatch.setenv("BB_BROWSER_API_KEY", "secret-token")
    monkeypatch.setenv("BB_BROWSER_TIMEOUT_MS", "12345")
    monkeypatch.setenv("BB_BROWSER_CONNECT_TIMEOUT_MS", "2345")
    monkeypatch.setenv("BB_BROWSER_SESSION_NAME", "operator-session")
    monkeypatch.setenv("BB_BROWSER_VERIFY_SSL", "false")

    config = BbBrowserClientConfig.from_env()

    assert config.base_url == "https://bb-browser.internal"
    assert config.capture_path == "/bridge/capture"
    assert config.api_key == "secret-token"
    assert config.request_timeout_ms == 12345
    assert config.connect_timeout_ms == 2345
    assert config.default_session_name == "operator-session"
    assert config.verify_ssl is False


def test_bb_browser_client_config_from_env_falls_back_to_prompt5_defaults(monkeypatch: pytest.MonkeyPatch):
    for key in [
        "BB_BROWSER_BASE_URL",
        "BB_BROWSER_CAPTURE_PATH",
        "BB_BROWSER_API_KEY",
        "BB_BROWSER_TIMEOUT_MS",
        "BB_BROWSER_CONNECT_TIMEOUT_MS",
        "BB_BROWSER_SESSION_NAME",
        "BB_BROWSER_VERIFY_SSL",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = BbBrowserClientConfig.from_env()

    assert config.base_url == "http://127.0.0.1:9223"
    assert config.capture_path == "/session/acquire"
    assert config.api_key is None
    assert config.request_timeout_ms == 45_000
    assert config.connect_timeout_ms == 5_000
    assert config.default_session_name == "jobbot-ingestion"
    assert config.verify_ssl is True
