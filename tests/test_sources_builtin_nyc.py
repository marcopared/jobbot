from __future__ import annotations

from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend
from core.ingestion.sources.public_boards.builtin_nyc import BuiltInNYCSourceAdapter

from tests.public_board_test_support import FakeFetchersModule, FakeResponse, fixture_text


def test_builtin_nyc_adapter_fetches_listing_and_detail():
    fetchers = FakeFetchersModule()
    listing_url = "https://www.builtinnyc.com/jobs"
    detail_url = "https://www.builtinnyc.com/job/vp-customer-success/8956308"
    fetchers.enqueue(
        mode="simple",
        url=listing_url,
        result=FakeResponse(
            text=fixture_text("builtin_nyc", "listing.html"),
            headers={"content-type": "text/html"},
            url=listing_url,
        ),
    )
    fetchers.enqueue(
        mode="simple",
        url=detail_url,
        result=FakeResponse(
            text=fixture_text("builtin_nyc", "detail.html"),
            headers={"content-type": "text/html"},
            url=detail_url,
        ),
    )

    adapter = BuiltInNYCSourceAdapter(
        backend=ScraplingFetchBackend(fetchers_module=fetchers),
    )

    batch = adapter.acquire(max_results=1)

    assert batch.error is None
    assert batch.stats == {"fetched": 1, "errors": 0}
    normalized = adapter.normalize(batch.records[0])
    assert normalized is not None
    assert normalized.external_id == "8956308"
    assert normalized.company == "Runwise"
    assert normalized.title == "VP, Customer Success"
    assert normalized.location == "New York, NY, US"
    assert normalized.apply_url == "https://job-boards.greenhouse.io/runwise/jobs/4670112006?gh_src=h0gktq2v6us"
    assert "customer success organization" in (normalized.description or "").lower()
