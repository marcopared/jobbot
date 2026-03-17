"""Tests for AGG-1 (Adzuna) discovery connector normalization."""

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
    """Normalize an Adzuna job with all fields."""
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
    assert canonical.normalized_title == "senior backend engineer"
    assert canonical.normalized_company == "acme corp"
    assert canonical.normalized_location == "new york, ny"


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


def test_fetch_raw_jobs_mocked(connector):
    """Fetch returns FetchResult with raw_jobs wrapped in provenance."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {
                "id": "mock1",
                "title": "Test Job",
                "company": {"display_name": "Mock Co"},
                "redirect_url": "https://adzuna.com/job/mock1",
            },
        ],
    }
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp

    with patch("core.connectors.agg1.httpx.Client") as mock_client_class:
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        result = connector.fetch_raw_jobs(query="engineer", location="NYC")
    assert result.error is None
    assert result.stats["fetched"] == 1
    assert len(result.raw_jobs) == 1
    assert result.raw_jobs[0].raw_payload["title"] == "Test Job"
    assert "adzuna.com" in result.raw_jobs[0].provenance.source_url
