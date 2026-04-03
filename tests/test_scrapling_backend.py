from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend
from core.ingestion.registry import build_default_backend_registry
from core.ingestion.types import AcquisitionRequest, FetchMode


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "scrapling"


def _fixture_text(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


@dataclass
class _FakeResponse:
    text: str | None = None
    body: bytes | str | None = None
    status: int | None = 200
    headers: dict[str, str] | None = None
    url: str | None = None
    meta: dict[str, Any] | None = None
    encoding: str = "utf-8"


class _FakeRequestError(Exception):
    pass


class _FakeSession:
    def __init__(self, module: "_FakeFetchersModule", *, mode: str, kwargs: dict[str, Any]) -> None:
        self._module = module
        self._mode = mode
        self._kwargs = kwargs

    def __enter__(self) -> "_FakeSession":
        self._module.session_kwargs[self._mode].append(self._kwargs)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, url: str, **kwargs: Any) -> Any:
        return self._module.handle(self._mode, "get", url, kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        return self._module.handle(self._mode, "post", url, kwargs)

    def fetch(self, url: str, **kwargs: Any) -> Any:
        return self._module.handle(self._mode, "fetch", url, kwargs)


class _FakeSessionFactory:
    def __init__(self, module: "_FakeFetchersModule", *, mode: str) -> None:
        self._module = module
        self._mode = mode

    def __call__(self, **kwargs: Any) -> _FakeSession:
        return _FakeSession(self._module, mode=self._mode, kwargs=kwargs)


class _FakeFetchersModule:
    def __init__(self) -> None:
        self._plans: dict[tuple[str, str], list[Any]] = {}
        self.calls: list[dict[str, Any]] = []
        self.session_kwargs: dict[str, list[dict[str, Any]]] = {
            "simple": [],
            "dynamic": [],
        }
        self.FetcherSession = _FakeSessionFactory(self, mode="simple")
        self.DynamicSession = _FakeSessionFactory(self, mode="dynamic")

    def enqueue(self, *, mode: str, url: str, result: Any) -> None:
        self._plans.setdefault((mode, url), []).append(result)

    def handle(self, mode: str, method: str, url: str, kwargs: dict[str, Any]) -> Any:
        self.calls.append(
            {
                "mode": mode,
                "method": method,
                "url": url,
                "kwargs": kwargs,
            }
        )
        plan = self._plans.get((mode, url))
        if not plan:
            raise AssertionError(f"No fake response planned for mode={mode} url={url}")
        result = plan.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_backend_registry_registers_scrapling_backend():
    backend = build_default_backend_registry().create("scrapling")
    assert backend.name == "scrapling"


def test_scrapling_backend_fetches_simple_fixture_html():
    fetchers_module = _FakeFetchersModule()
    url = "https://example.com/jobs"
    html = _fixture_text("simple_job_board.html")
    fetchers_module.enqueue(
        mode="simple",
        url=url,
        result=_FakeResponse(
            text=html,
            status=200,
            headers={"content-type": "text/html; charset=utf-8"},
            url="https://example.com/jobs?page=1",
        ),
    )

    backend = ScraplingFetchBackend(fetchers_module=fetchers_module)
    batch = backend.acquire(
        "demo_board",
        request=AcquisitionRequest(
            url=url,
            method="GET",
            query_params={"page": 1},
            headers={"User-Agent": "jobbot-test"},
            cookies={"session": "abc123"},
            session_config={"retries": 2},
            timeout_ms=12_000,
            fetch_mode=FetchMode.SIMPLE,
            extraction_hints={"job_cards": ".job-card"},
        ),
    )

    assert batch.error is None
    assert batch.error_type is None
    assert batch.stats == {"fetched": 1, "errors": 0}
    assert batch.metadata["source_name"] == "demo_board"
    assert batch.metadata["fetch_mode"] == "simple"

    record = batch.records[0]
    assert record.raw_payload == html
    assert record.artifact is not None
    assert record.artifact.content == html
    assert record.artifact.final_url == "https://example.com/jobs?page=1"
    assert record.artifact.status_code == 200
    assert record.artifact.response_headers == {"content-type": "text/html; charset=utf-8"}
    assert record.capture_metadata == {
        "fetch_mode": "simple",
        "attempted_modes": ["simple"],
        "used_fallback": False,
        "timeout_ms": 12_000,
    }
    assert record.provenance.source_url == url
    assert record.provenance.connector_version == "scrapling"

    assert fetchers_module.session_kwargs["simple"] == [
        {
            "retries": 2,
            "cookies": {"session": "abc123"},
            "headers": {"User-Agent": "jobbot-test"},
        }
    ]
    assert fetchers_module.calls == [
        {
            "mode": "simple",
            "method": "get",
            "url": url,
            "kwargs": {
                "timeout": 12_000,
                "params": {"page": 1},
                "headers": {"User-Agent": "jobbot-test"},
            },
        }
    ]


def test_scrapling_backend_escalates_from_simple_to_dynamic():
    fetchers_module = _FakeFetchersModule()
    url = "https://example.com/careers"
    fetchers_module.enqueue(
        mode="simple",
        url=url,
        result=_FakeResponse(
            text="blocked",
            status=403,
            headers={"content-type": "text/html"},
            url=url,
        ),
    )
    dynamic_html = _fixture_text("dynamic_job_board.html")
    fetchers_module.enqueue(
        mode="dynamic",
        url=url,
        result=_FakeResponse(
            text=dynamic_html,
            status=200,
            headers={"content-type": "text/html"},
            url="https://example.com/careers/rendered",
            meta={"rendered": True},
        ),
    )

    backend = ScraplingFetchBackend(fetchers_module=fetchers_module)
    batch = backend.acquire(
        "demo_board",
        request=AcquisitionRequest(
            url=url,
            fetch_mode=FetchMode.SIMPLE,
            fallback_fetch_mode=FetchMode.DYNAMIC,
            wait_for_selector=".results-ready",
            wait_selector_state="visible",
            wait_after_ms=750,
            headers={"X-Test": "dynamic"},
            timeout_ms=18_000,
        ),
    )

    assert batch.error is None
    assert batch.stats == {"fetched": 1, "errors": 0}

    record = batch.records[0]
    assert record.raw_payload == dynamic_html
    assert record.artifact is not None
    assert record.artifact.final_url == "https://example.com/careers/rendered"
    assert record.capture_metadata == {
        "fetch_mode": "dynamic",
        "attempted_modes": ["simple", "dynamic"],
        "used_fallback": True,
        "timeout_ms": 18_000,
        "wait_for_selector": ".results-ready",
        "wait_selector_state": "visible",
        "wait_after_ms": 750,
        "response_meta": {"rendered": True},
    }

    assert fetchers_module.calls == [
        {
            "mode": "simple",
            "method": "get",
            "url": url,
            "kwargs": {
                "timeout": 18_000,
                "headers": {"X-Test": "dynamic"},
            },
        },
        {
            "mode": "dynamic",
            "method": "fetch",
            "url": url,
            "kwargs": {
                "timeout": 18_000,
                "wait_selector": ".results-ready",
                "wait_selector_state": "visible",
                "wait": 750,
                "extra_headers": {"X-Test": "dynamic"},
            },
        },
    ]


def test_scrapling_backend_classifies_timeout_failures():
    fetchers_module = _FakeFetchersModule()
    url = "https://example.com/slow"
    fetchers_module.enqueue(
        mode="dynamic",
        url=url,
        result=TimeoutError("timed out waiting for selector"),
    )

    backend = ScraplingFetchBackend(fetchers_module=fetchers_module)
    batch = backend.acquire(
        "demo_board",
        request=AcquisitionRequest(
            url=url,
            fetch_mode=FetchMode.DYNAMIC,
            wait_for_selector=".job-card",
        ),
    )

    assert batch.records == []
    assert batch.stats == {"fetched": 0, "errors": 1}
    assert batch.error == "timed out waiting for selector"
    assert batch.error_type == "timeout"
    assert batch.metadata["failures"] == [
        {
            "error_type": "timeout",
            "message": "timed out waiting for selector",
            "retryable": True,
            "status_code": None,
            "metadata": {"fetch_mode": "dynamic"},
        }
    ]


def test_scrapling_backend_classifies_network_failures():
    fetchers_module = _FakeFetchersModule()
    url = "https://example.com/down"
    fetchers_module.enqueue(
        mode="simple",
        url=url,
        result=_FakeRequestError("network connection dropped"),
    )

    backend = ScraplingFetchBackend(fetchers_module=fetchers_module)
    batch = backend.acquire(
        "demo_board",
        request=AcquisitionRequest(url=url, fetch_mode=FetchMode.SIMPLE),
    )

    assert batch.records == []
    assert batch.error == "network connection dropped"
    assert batch.error_type == "network_error"


def test_scrapling_backend_rejects_missing_request():
    backend = ScraplingFetchBackend(fetchers_module=_FakeFetchersModule())
    batch = backend.acquire("demo_board")

    assert batch.records == []
    assert batch.stats == {"fetched": 0, "errors": 1}
    assert batch.error == "ScraplingFetchBackend requires an AcquisitionRequest or request fields"
    assert batch.error_type == "invalid_request"
