from __future__ import annotations

from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend
from core.ingestion.sources.portfolio_boards.greycroft import GreycroftSourceAdapter

from tests.public_board_test_support import FakeFetchersModule, FakeResponse, fixture_text


def test_greycroft_adapter_fetches_listing_and_detail():
    fetchers = FakeFetchersModule()
    listing_url = "https://jobs.greycroft.com/jobs"
    detail_url = (
        "https://jobs.greycroft.com/companies/narmi-2/"
        "jobs/73299386-software-engineer-i-implementations"
    )
    fetchers.enqueue(
        mode="simple",
        url=listing_url,
        result=FakeResponse(
            text=fixture_text("greycroft", "listing.html"),
            headers={"content-type": "text/html"},
            url=listing_url,
        ),
    )
    fetchers.enqueue(
        mode="simple",
        url=detail_url,
        result=FakeResponse(
            text=fixture_text("greycroft", "detail.html"),
            headers={"content-type": "text/html"},
            url=detail_url,
        ),
    )

    adapter = GreycroftSourceAdapter(
        backend=ScraplingFetchBackend(fetchers_module=fetchers),
    )

    batch = adapter.acquire(max_results=1)

    assert batch.error is None
    assert batch.stats == {"fetched": 1, "errors": 0}
    normalized = adapter.normalize(batch.records[0])
    assert normalized is not None
    assert normalized.external_id == "73299386"
    assert normalized.company == "Narmi"
    assert normalized.title == "Software Engineer I - Implementations"
    assert normalized.location == "New York, NY, USA"
    assert normalized.apply_url == "https://www.builtinnyc.com/job/software-engineer-i-implementations/8945978"
    assert "digital banking" in (normalized.description or "").lower()

