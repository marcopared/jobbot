from __future__ import annotations

from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend
from core.ingestion.sources.portfolio_boards.primary_vc import PrimaryVCSourceAdapter

from tests.public_board_test_support import FakeFetchersModule, FakeResponse, fixture_text


def test_primary_vc_adapter_fetches_listing_and_detail():
    fetchers = FakeFetchersModule()
    listing_url = "https://jobs.primary.vc/jobs"
    detail_url = (
        "https://jobs.primary.vc/companies/inspiren-2/"
        "jobs/73287563-principal-systems-pm-perception-hardware-platform"
    )
    fetchers.enqueue(
        mode="simple",
        url=listing_url,
        result=FakeResponse(
            text=fixture_text("primary_vc", "listing.html"),
            headers={"content-type": "text/html"},
            url=listing_url,
        ),
    )
    fetchers.enqueue(
        mode="simple",
        url=detail_url,
        result=FakeResponse(
            text=fixture_text("primary_vc", "detail.html"),
            headers={"content-type": "text/html"},
            url=detail_url,
        ),
    )

    adapter = PrimaryVCSourceAdapter(
        backend=ScraplingFetchBackend(fetchers_module=fetchers),
    )

    batch = adapter.acquire(max_results=1)

    assert batch.error is None
    assert batch.stats == {"fetched": 1, "errors": 0}
    normalized = adapter.normalize(batch.records[0])
    assert normalized is not None
    assert normalized.external_id == "73287563"
    assert normalized.company == "Inspiren"
    assert normalized.title == "Principal Systems PM, Perception Hardware & Platform"
    assert normalized.location == "New York, NY, USA"
    assert normalized.apply_url == "https://boards.greenhouse.io/inspiren/jobs/5097877007"
    assert "connected ecosystem in senior living" in (normalized.description or "").lower()

