from __future__ import annotations

from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend
from core.ingestion.sources.public_boards.welcome_to_the_jungle import (
    WelcomeToTheJungleSourceAdapter,
)

from tests.public_board_test_support import FakeFetchersModule, FakeResponse, fixture_text


def test_wttj_adapter_fetches_listing_and_detail():
    fetchers = FakeFetchersModule()
    listing_url = "https://www.welcometothejungle.com/en/jobs"
    detail_url = "https://www.welcometothejungle.com/en/companies/maki/jobs/digital-marketing-manager_new-york"
    fetchers.enqueue(
        mode="simple",
        url=listing_url,
        result=FakeResponse(
            text=fixture_text("wttj", "listing.html"),
            headers={"content-type": "text/html"},
            url=listing_url,
        ),
    )
    fetchers.enqueue(
        mode="simple",
        url=detail_url,
        result=FakeResponse(
            text=fixture_text("wttj", "detail.html"),
            headers={"content-type": "text/html"},
            url=detail_url,
        ),
    )

    adapter = WelcomeToTheJungleSourceAdapter(
        backend=ScraplingFetchBackend(fetchers_module=fetchers),
    )

    batch = adapter.acquire(max_results=1)

    assert batch.error is None
    assert batch.stats == {"fetched": 1, "errors": 0}
    normalized = adapter.normalize(batch.records[0])
    assert normalized is not None
    assert normalized.external_id == "en/companies/maki/jobs/digital-marketing-manager_new-york"
    assert normalized.company == "MakiPeople"
    assert normalized.title == "Growth Marketing Manager"
    assert normalized.location == "New York, New York, US"
    assert normalized.apply_url == detail_url
    assert "demand generation engine" in (normalized.description or "").lower()
