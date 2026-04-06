from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from core.ingestion.backends.bb_browser_client import BbBrowserPageCapture


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "auth_boards"


def fixture_text(*parts: str) -> str:
    return FIXTURES_DIR.joinpath(*parts).read_text(encoding="utf-8")


@dataclass
class FakeBbBrowserTransport:
    responses: dict[str, Mapping[str, Any]]

    def __post_init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def capture(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        url = str(payload.get("url") or "")
        self.calls.append(dict(payload))
        try:
            response = self.responses[url]
        except KeyError as exc:
            raise AssertionError(f"No fake bb-browser response planned for {url}") from exc
        if isinstance(response, Exception):
            raise response
        return dict(response)


class FakeBbBrowserClient:
    def __init__(self, captures: Mapping[str, BbBrowserPageCapture | Exception]) -> None:
        self._captures = dict(captures)
        self.calls: list[dict[str, Any]] = []

    def capture_page(self, *, source_name: str, request, url: str) -> BbBrowserPageCapture:
        self.calls.append(
            {
                "source_name": source_name,
                "url": url,
                "request": request,
            }
        )
        planned = self._captures[url]
        if isinstance(planned, Exception):
            raise planned
        return planned
