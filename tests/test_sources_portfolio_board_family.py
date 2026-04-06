from __future__ import annotations

import pytest

from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend
from core.ingestion.sources.portfolio_boards.getro_like import (
    GetroLikePortfolioBoardSourceAdapter,
)
from core.ingestion.sources.portfolio_boards.greycroft import GreycroftSourceAdapter
from core.ingestion.sources.portfolio_boards.primary_vc import PrimaryVCSourceAdapter
from core.ingestion.sources.portfolio_boards.technyc import TechNYCSourceAdapter
from core.ingestion.sources.portfolio_boards.usv import USVSourceAdapter

from tests.public_board_test_support import FakeFetchersModule, FakeResponse, fixture_text


@pytest.mark.parametrize(
    ("adapter_cls", "fixture_dir", "listing_url", "detail_url"),
    [
        (
            TechNYCSourceAdapter,
            "technyc",
            "https://jobs.technyc.org/jobs",
            "https://jobs.technyc.org/companies/cassidy-2-7f40bb2f-9d0a-49e4-ad1e-ca7f8498ccff/jobs/73294014-ai-solutions-consultant",
        ),
        (
            PrimaryVCSourceAdapter,
            "primary_vc",
            "https://jobs.primary.vc/jobs",
            "https://jobs.primary.vc/companies/inspiren-2/jobs/73287563-principal-systems-pm-perception-hardware-platform",
        ),
        (
            GreycroftSourceAdapter,
            "greycroft",
            "https://jobs.greycroft.com/jobs",
            "https://jobs.greycroft.com/companies/narmi-2/jobs/73299386-software-engineer-i-implementations",
        ),
    ],
)
def test_getro_portfolio_boards_share_adapter_family(adapter_cls, fixture_dir, listing_url, detail_url):
    fetchers = FakeFetchersModule()
    fetchers.enqueue(
        mode="simple",
        url=listing_url,
        result=FakeResponse(
            text=fixture_text(fixture_dir, "listing.html"),
            headers={"content-type": "text/html"},
            url=listing_url,
        ),
    )
    fetchers.enqueue(
        mode="simple",
        url=detail_url,
        result=FakeResponse(
            text=fixture_text(fixture_dir, "detail.html"),
            headers={"content-type": "text/html"},
            url=detail_url,
        ),
    )

    adapter = adapter_cls(backend=ScraplingFetchBackend(fetchers_module=fetchers))

    assert isinstance(adapter, GetroLikePortfolioBoardSourceAdapter)
    batch = adapter.acquire(max_results=1)
    assert batch.records[0].raw_payload["detail_url"] == detail_url
    assert batch.records[0].raw_payload["capture_context"]["detail_url"] == detail_url


def test_usv_uses_custom_adapter_outside_getro_family():
    adapter = USVSourceAdapter()

    assert isinstance(adapter, USVSourceAdapter)
    assert not isinstance(adapter, GetroLikePortfolioBoardSourceAdapter)

