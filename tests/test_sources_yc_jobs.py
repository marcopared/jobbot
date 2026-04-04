from __future__ import annotations

from core.ingestion.backends.bb_browser_backend import BbBrowserSessionBackend
from core.ingestion.backends.bb_browser_client import BbBrowserPageCapture
from core.ingestion.sources.auth_boards.yc_jobs import YCJobsSourceAdapter

from tests.bb_browser_test_support import FakeBbBrowserClient, fixture_text


def test_yc_jobs_adapter_fetches_listing_and_detail_from_browser_backend():
    listing_url = "https://www.workatastartup.com/jobs"
    detail_url = "https://www.workatastartup.com/jobs/yc-789-platform-engineer"
    backend = BbBrowserSessionBackend(
        client=FakeBbBrowserClient(
            {
                listing_url: BbBrowserPageCapture(
                    requested_url=listing_url,
                    final_url=listing_url,
                    status_code=200,
                    html=fixture_text("yc_jobs", "listing.html"),
                    content_type="text/html",
                    session_name="yc-session",
                ),
                detail_url: BbBrowserPageCapture(
                    requested_url=detail_url,
                    final_url=detail_url,
                    status_code=200,
                    html=fixture_text("yc_jobs", "detail.html"),
                    content_type="text/html",
                    session_name="yc-session",
                ),
            }
        )
    )
    adapter = YCJobsSourceAdapter(backend=backend)

    batch = adapter.acquire(max_results=1)

    assert batch.error is None
    assert batch.stats == {"fetched": 1, "errors": 0}
    normalized = adapter.normalize(batch.records[0])
    assert normalized is not None
    assert normalized.external_id == "yc-789"
    assert normalized.title == "Platform Engineer"
    assert normalized.company == "Acme AI"
    assert normalized.location == "San Francisco, CA / Remote"
    assert normalized.apply_url == "https://www.workatastartup.com/jobs/yc-789-platform-engineer/apply"
    assert "startup infrastructure" in (normalized.description or "")
