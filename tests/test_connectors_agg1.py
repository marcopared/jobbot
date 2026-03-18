"""Tests for AGG-1 (Adzuna) discovery connector hardening."""

from unittest.mock import MagicMock, patch

import pytest

from core.connectors.agg1 import create_agg1_connector


@pytest.fixture
def connector():
    return create_agg1_connector(
        app_id="test_app_id",
        app_key="test_app_key",
        country="us",
    )


def test_normalize_full_job(connector):
    """Normalize Adzuna job fields using frozen alpha mapping."""
    raw = {
        "id": "abc123",
        "title": "Senior Backend Engineer",
        "company": {"display_name": "Acme Corp"},
        "location": {"display_name": "New York, NY"},
        "description": "We are looking for a senior backend engineer with Python and AWS experience.",
        "redirect_url": "https://www.adzuna.com/jobs/abc123",
        "created": "2024-01-15T12:00:00Z",
        "contract_type": "permanent",
        "contract_time": "full_time",
        "salary_min": 140000,
        "salary_max": 190000,
    }
    canonical = connector.normalize(raw)
    assert canonical is not None
    assert canonical.source_name == "agg1"
    assert canonical.external_id == "abc123"
    assert canonical.title == "Senior Backend Engineer"
    assert canonical.company == "Acme Corp"
    assert canonical.location == "New York, NY"
    assert canonical.description is not None
    assert "Python" in canonical.description
    assert canonical.apply_url == "https://www.adzuna.com/jobs/abc123"
    assert canonical.source_url == "https://www.adzuna.com/jobs/abc123"
    assert canonical.posted_at is not None
    assert canonical.employment_type == "full_time / permanent"
    assert canonical.normalized_title == "senior backend engineer"
    assert canonical.normalized_company == "acme corp"
    assert canonical.normalized_location == "new york, ny"
    assert canonical.raw_payload["contract_time"] == "full_time"
    assert canonical.raw_payload["contract_type"] == "permanent"
    assert canonical.raw_payload["salary_min"] == 140000
    assert canonical.raw_payload["salary_max"] == 190000


def test_normalize_company_fallback_when_missing(connector):
    """When company.display_name missing, use Unknown."""
    raw = {
        "id": "x1",
        "title": "Engineer",
        "redirect_url": "https://example.com/job/x1",
    }
    canonical = connector.normalize(raw)
    assert canonical is not None
    assert canonical.company == "Unknown"
    assert canonical.normalized_company == "unknown"


def test_normalize_location_from_area(connector):
    """When location.display_name missing, use area[0]."""
    raw = {
        "id": "x2",
        "title": "DevOps",
        "company": {"display_name": "Tech Co"},
        "location": {"area": ["Remote", "Austin"]},
        "redirect_url": "https://example.com/job/x2",
    }
    canonical = connector.normalize(raw)
    assert canonical is not None
    assert canonical.location == "Remote"


def test_normalize_missing_id_returns_none(connector):
    """Job without id cannot be normalized."""
    raw = {"title": "Test", "redirect_url": "https://example.com/job/1"}
    assert connector.normalize(raw) is None


def test_normalize_missing_title_returns_none(connector):
    """Job without title cannot be normalized."""
    raw = {"id": "x3", "redirect_url": "https://example.com/job/x3"}
    assert connector.normalize(raw) is None


def test_fetch_raw_jobs_no_credentials_returns_error(connector):
    """Fetch without credentials returns error."""
    empty_connector = create_agg1_connector(app_id="", app_key="", country="us")
    result = empty_connector.fetch_raw_jobs(query="engineer")
    assert result.error is not None
    assert "ADZUNA" in result.error or "credentials" in result.error.lower()
    assert result.stats.get("errors", 0) == 1
    assert len(result.raw_jobs) == 0


def test_fetch_raw_jobs_multi_page(connector):
    """Fetches sequential pages until an empty page is returned."""
    page1 = MagicMock()
    page1.raise_for_status = MagicMock()
    page1.json.return_value = {
        "results": [
            {"id": "p1j1", "title": "Job 1"},
            {"id": "p1j2", "title": "Job 2"},
        ]
    }
    page2 = MagicMock()
    page2.raise_for_status = MagicMock()
    page2.json.return_value = {"results": [{"id": "p2j1", "title": "Job 3"}]}
    mock_client = MagicMock()
    mock_client.get.side_effect = [page1, page2]

    with patch("core.connectors.agg1.httpx.Client") as mock_client_class:
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        result = connector.fetch_raw_jobs(
            query="engineer",
            location="Austin",
            results_per_page=2,
            max_pages=5,
        )

    assert result.error is None
    assert result.stats["fetched"] == 3
    assert len(result.raw_jobs) == 3
    assert mock_client.get.call_count == 2
    called_urls = [c.args[0] for c in mock_client.get.call_args_list]
    assert called_urls[0].endswith("/search/1")
    assert called_urls[1].endswith("/search/2")


def test_fetch_raw_jobs_bounded_by_max_results(connector):
    """Per-run cap truncates fetched jobs even when more pages are available."""
    page1 = MagicMock()
    page1.raise_for_status = MagicMock()
    page1.json.return_value = {"results": [{"id": "1"}, {"id": "2"}]}
    page2 = MagicMock()
    page2.raise_for_status = MagicMock()
    page2.json.return_value = {"results": [{"id": "3"}, {"id": "4"}]}

    mock_client = MagicMock()
    mock_client.get.side_effect = [page1, page2]

    with patch("core.connectors.agg1.httpx.Client") as mock_client_class:
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        result = connector.fetch_raw_jobs(
            query="engineer",
            results_per_page=2,
            max_pages=10,
            max_results=3,
        )

    assert result.error is None
    assert result.stats["fetched"] == 3
    assert [j.raw_payload["id"] for j in result.raw_jobs] == ["1", "2", "3"]
    assert mock_client.get.call_count == 2


def test_fetch_raw_jobs_http_failure_returns_error(connector):
    """HTTP failures are returned as provider errors."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 410
    mock_response.text = '{"exception":"AuthorisationFailed"}'

    import httpx

    http_error = httpx.HTTPStatusError(
        message="boom",
        request=MagicMock(),
        response=mock_response,
    )
    mock_client.get.side_effect = http_error

    with patch("core.connectors.agg1.httpx.Client") as mock_client_class:
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        result = connector.fetch_raw_jobs(query="engineer")

    assert result.error is not None
    assert "HTTP error" in result.error
    assert result.stats.get("errors") == 1
    assert result.raw_jobs == []


def test_fetch_raw_jobs_provider_error_payload_returns_error(connector):
    """Provider-level exception payload is handled cleanly."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "exception": "AuthorisationFailed",
        "display": "Authorisation failed",
    }
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp

    with patch("core.connectors.agg1.httpx.Client") as mock_client_class:
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        result = connector.fetch_raw_jobs(query="engineer")

    assert result.error is not None
    assert "provider error" in result.error.lower()
    assert result.stats.get("errors") == 1
    assert result.raw_jobs == []


def test_fetch_raw_jobs_filter_param_wiring(connector):
    """Alpha Adzuna filter set is wired into query params."""
    page = MagicMock()
    page.raise_for_status = MagicMock()
    page.json.return_value = {"results": []}
    mock_client = MagicMock()
    mock_client.get.return_value = page

    with patch("core.connectors.agg1.httpx.Client") as mock_client_class:
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        connector.fetch_raw_jobs(
            query="backend engineer",
            location="Remote",
            distance=25,
            results_per_page=30,
            max_days_old=7,
            salary_min=120000,
            salary_max=200000,
            full_time=True,
            part_time=False,
            contract=1,
            permanent="true",
            category="it-jobs",
        )

    assert mock_client.get.call_count == 1
    _, kwargs = mock_client.get.call_args
    params = kwargs["params"]
    assert params["what"] == "backend engineer"
    assert params["where"] == "Remote"
    assert params["distance"] == 25
    assert params["results_per_page"] == 30
    assert params["max_days_old"] == 7
    assert params["sort_by"] == "date"
    assert params["salary_min"] == 120000
    assert params["salary_max"] == 200000
    assert params["full_time"] == "1"
    assert "part_time" not in params
    assert params["contract"] == "1"
    assert params["permanent"] == "1"
    assert params["category"] == "it-jobs"
