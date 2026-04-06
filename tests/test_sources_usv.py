from __future__ import annotations

from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend
from core.ingestion.sources.portfolio_boards.usv import USVSourceAdapter

from tests.public_board_test_support import FakeFetchersModule, FakeResponse, fixture_text


def test_usv_adapter_fetches_consider_api_results():
    fetchers = FakeFetchersModule()
    search_url = "https://jobs.usv.com/api-boards/search-jobs"
    fetchers.enqueue(
        mode="simple",
        url=search_url,
        result=FakeResponse(
            text=fixture_text("usv", "search_jobs.json"),
            headers={"content-type": "application/json"},
            url=search_url,
        ),
    )

    adapter = USVSourceAdapter(
        backend=ScraplingFetchBackend(fetchers_module=fetchers),
    )

    batch = adapter.acquire(max_results=1)

    assert batch.error is None
    assert batch.stats == {"fetched": 1, "errors": 0}
    normalized = adapter.normalize(batch.records[0])
    assert normalized is not None
    assert normalized.external_id == "e23d43f4-8239-4a1a-925a-d68031eff30b"
    assert normalized.company == "Radiant"
    assert normalized.title == "Electrical Engineer, PCB Design"
    assert normalized.location == "El Segundo, California, United States"
    assert normalized.apply_url == (
        "https://jobs.ashbyhq.com/radiant-industries/"
        "e23d43f4-8239-4a1a-925a-d68031eff30b?utm_source=jobs.usv.com"
    )
    assert batch.records[0].raw_payload["capture_context"]["search_api_url"] == search_url

