from __future__ import annotations

from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend
from core.ingestion.sources.public_boards.startupjobs_nyc import StartupJobsNYCSourceAdapter

from tests.public_board_test_support import FakeFetchersModule, FakeResponse, fixture_text


def test_startupjobs_nyc_adapter_fetches_listing_and_detail():
    fetchers = FakeFetchersModule()
    listing_url = "https://startupjobs.nyc/"
    detail_url = "https://startupjobs.nyc/jobs/openai-manager-solutions-engineering"
    fetchers.enqueue(
        mode="simple",
        url=listing_url,
        result=FakeResponse(
            text=fixture_text("startupjobs_nyc", "listing.html"),
            headers={"content-type": "text/html"},
            url=listing_url,
        ),
    )
    fetchers.enqueue(
        mode="simple",
        url=detail_url,
        result=FakeResponse(
            text=fixture_text("startupjobs_nyc", "detail.html"),
            headers={"content-type": "text/html"},
            url=detail_url,
        ),
    )

    adapter = StartupJobsNYCSourceAdapter(
        backend=ScraplingFetchBackend(fetchers_module=fetchers),
    )

    batch = adapter.acquire(max_results=1)

    assert batch.error is None
    assert batch.stats == {"fetched": 1, "errors": 0}
    normalized = adapter.normalize(batch.records[0])
    assert normalized is not None
    assert normalized.external_id == "openai-manager-solutions-engineering"
    assert normalized.company == "OpenAI"
    assert normalized.title == "Manager, Solutions Engineering"
    assert normalized.location == "San Francisco, California, United States"
    assert normalized.apply_url == "https://jobs.ashbyhq.com/openai/ab463045-cd9b-4100-a037-f1135ace1464?utm_source=jobs.a16z.com"
    assert normalized.description is not None
