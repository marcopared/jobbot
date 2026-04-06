from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "public_boards"


def fixture_text(*parts: str) -> str:
    return (FIXTURES_DIR.joinpath(*parts)).read_text(encoding="utf-8")


@dataclass
class FakeResponse:
    text: str | None = None
    body: bytes | str | None = None
    status: int | None = 200
    headers: dict[str, str] | None = None
    url: str | None = None
    meta: dict[str, Any] | None = None
    encoding: str = "utf-8"


class FakeSession:
    def __init__(self, module: "FakeFetchersModule", *, mode: str, kwargs: dict[str, Any]) -> None:
        self._module = module
        self._mode = mode
        self._kwargs = kwargs

    def __enter__(self) -> "FakeSession":
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


class FakeSessionFactory:
    def __init__(self, module: "FakeFetchersModule", *, mode: str) -> None:
        self._module = module
        self._mode = mode

    def __call__(self, **kwargs: Any) -> FakeSession:
        return FakeSession(self._module, mode=self._mode, kwargs=kwargs)


class FakeFetchersModule:
    def __init__(self) -> None:
        self._plans: dict[tuple[str, str], list[Any]] = {}
        self.calls: list[dict[str, Any]] = []
        self.session_kwargs: dict[str, list[dict[str, Any]]] = {
            "simple": [],
            "dynamic": [],
        }
        self.FetcherSession = FakeSessionFactory(self, mode="simple")
        self.DynamicSession = FakeSessionFactory(self, mode="dynamic")

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
