from __future__ import annotations

from core.ingestion.backends.bb_browser_backend import BbBrowserSessionBackend
from core.ingestion.backends.bb_browser_client import BbBrowserPageCapture
from core.ingestion.sources.auth_boards.linkedin_jobs import LinkedInJobsSourceAdapter

from tests.bb_browser_test_support import FakeBbBrowserClient, fixture_text


def test_linkedin_jobs_adapter_fetches_listing_and_detail_from_browser_backend():
    listing_url = "https://www.linkedin.com/jobs/search/"
    detail_url = "https://www.linkedin.com/jobs/view/li-123/"
    backend = BbBrowserSessionBackend(
        client=FakeBbBrowserClient(
            {
                listing_url: BbBrowserPageCapture(
                    requested_url=listing_url,
                    final_url=listing_url,
                    status_code=200,
                    html=fixture_text("linkedin_jobs", "listing.html"),
                    content_type="text/html",
                    session_name="linkedin-session",
                ),
                detail_url: BbBrowserPageCapture(
                    requested_url=detail_url,
                    final_url=detail_url,
                    status_code=200,
                    html=fixture_text("linkedin_jobs", "detail.html"),
                    content_type="text/html",
                    session_name="linkedin-session",
                ),
            }
        )
    )
    adapter = LinkedInJobsSourceAdapter(backend=backend)

    batch = adapter.acquire(max_results=1)

    assert batch.error is None
    assert batch.stats == {"fetched": 1, "errors": 0}
    record = batch.records[0]
    payload = record.raw_payload
    assert payload["capture_context"]["listing_capture"]["acquisition_mode"] == "browser_session"
    assert payload["capture_context"]["detail_capture"]["backend"] == "bb_browser"

    normalized = adapter.normalize(record)
    assert normalized is not None
    assert normalized.external_id == "li-123"
    assert normalized.title == "Senior Platform Engineer"
    assert normalized.company == "Acme AI"
    assert normalized.location == "New York, NY"
    assert normalized.apply_url == "https://jobs.acme.ai/apply/li-123"
    assert "enterprise AI workloads" in (normalized.description or "")
    assert adapter.policy.requires_auth is True
    assert adapter.policy.backend_preference == "bb_browser"
