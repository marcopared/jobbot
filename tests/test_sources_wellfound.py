from __future__ import annotations

from core.ingestion.backends.bb_browser_backend import BbBrowserSessionBackend
from core.ingestion.backends.bb_browser_client import BbBrowserPageCapture
from core.ingestion.sources.auth_boards.wellfound import WellfoundSourceAdapter

from tests.bb_browser_test_support import FakeBbBrowserClient, fixture_text


def test_wellfound_adapter_fetches_listing_and_detail_from_browser_backend():
    listing_url = "https://wellfound.com/jobs"
    detail_url = "https://wellfound.com/company/acme-ai/jobs/wf-456-senior-platform-engineer"
    backend = BbBrowserSessionBackend(
        client=FakeBbBrowserClient(
            {
                listing_url: BbBrowserPageCapture(
                    requested_url=listing_url,
                    final_url=listing_url,
                    status_code=200,
                    html=fixture_text("wellfound", "listing.html"),
                    content_type="text/html",
                    session_name="wellfound-session",
                ),
                detail_url: BbBrowserPageCapture(
                    requested_url=detail_url,
                    final_url=detail_url,
                    status_code=200,
                    html=fixture_text("wellfound", "detail.html"),
                    content_type="text/html",
                    session_name="wellfound-session",
                ),
            }
        )
    )
    adapter = WellfoundSourceAdapter(backend=backend)

    batch = adapter.acquire(max_results=1)

    assert batch.error is None
    assert batch.stats == {"fetched": 1, "errors": 0}
    normalized = adapter.normalize(batch.records[0])
    assert normalized is not None
    assert normalized.external_id == "wf-456"
    assert normalized.title == "Senior Platform Engineer"
    assert normalized.company == "Acme AI"
    assert normalized.location == "Remote, US"
    assert normalized.apply_url == "https://jobs.acme.ai/apply/wf-456"
    assert "platform reliability" in (normalized.description or "")
