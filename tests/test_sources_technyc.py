from __future__ import annotations

from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend
from core.ingestion.sources.portfolio_boards.technyc import TechNYCSourceAdapter

from tests.public_board_test_support import FakeFetchersModule, FakeResponse, fixture_text


def test_technyc_adapter_fetches_listing_and_detail():
    fetchers = FakeFetchersModule()
    listing_url = "https://jobs.technyc.org/jobs"
    detail_url = (
        "https://jobs.technyc.org/companies/cassidy-2-7f40bb2f-9d0a-49e4-ad1e-ca7f8498ccff/"
        "jobs/73294014-ai-solutions-consultant"
    )
    fetchers.enqueue(
        mode="simple",
        url=listing_url,
        result=FakeResponse(
            text=fixture_text("technyc", "listing.html"),
            headers={"content-type": "text/html"},
            url=listing_url,
        ),
    )
    fetchers.enqueue(
        mode="simple",
        url=detail_url,
        result=FakeResponse(
            text=fixture_text("technyc", "detail.html"),
            headers={"content-type": "text/html"},
            url=detail_url,
        ),
    )

    adapter = TechNYCSourceAdapter(
        backend=ScraplingFetchBackend(fetchers_module=fetchers),
    )

    batch = adapter.acquire(max_results=1)

    assert batch.error is None
    assert batch.stats == {"fetched": 1, "errors": 0}
    normalized = adapter.normalize(batch.records[0])
    assert normalized is not None
    assert normalized.external_id == "73294014"
    assert normalized.company == "Cassidy"
    assert normalized.title == "AI Solutions Consultant"
    assert normalized.location == "New York, NY, USA"
    assert normalized.apply_url == "https://www.linkedin.com/jobs/view/ai-solutions-consultant-at-cassidy-4395702255"
    assert "innovative no-code platform" in (normalized.description or "").lower()

