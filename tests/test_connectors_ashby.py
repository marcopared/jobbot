"""Tests for Ashby connector normalization."""

from unittest.mock import MagicMock, patch

import pytest

from core.connectors.ashby import create_ashby_connector


@pytest.fixture
def connector():
    return create_ashby_connector(
        job_board_name="Ashby",
        company_name="Ashby Inc",
    )


def test_normalize_full_job(connector):
    """Normalize an Ashby job with all fields."""
    raw = {
        "title": "Product Manager",
        "location": "Houston, TX",
        "department": "Product",
        "team": "Growth",
        "isRemote": True,
        "workplaceType": "Remote",
        "employmentType": "FullTime",
        "descriptionHtml": "<p>Join our team</p>",
        "descriptionPlain": "Join our team",
        "publishedAt": "2021-04-30T16:21:55.393+00:00",
        "jobUrl": "https://jobs.ashbyhq.com/ashby/product-manager",
        "applyUrl": "https://jobs.ashbyhq.com/ashby/apply",
    }
    canonical = connector.normalize(raw)
    assert canonical is not None
    assert canonical.source_name == "ashby"
    assert canonical.external_id == "product-manager"
    assert canonical.title == "Product Manager"
    assert canonical.company == "Ashby Inc"
    assert canonical.location == "Houston, TX"
    assert canonical.employment_type == "FullTime"
    assert canonical.description is not None
    assert "Join our team" in (canonical.description or "")
    assert canonical.apply_url == "https://jobs.ashbyhq.com/ashby/apply"
    assert canonical.source_url == "https://jobs.ashbyhq.com/ashby/product-manager"
    assert canonical.posted_at is not None


def test_normalize_remote_without_location(connector):
    """When isRemote and no location, use Remote."""
    raw = {
        "title": "Engineer",
        "jobUrl": "https://jobs.ashbyhq.com/acme/engineer",
        "applyUrl": "https://jobs.ashbyhq.com/acme/apply",
        "isRemote": True,
    }
    canonical = connector.normalize(raw)
    assert canonical is not None
    assert canonical.location == "Remote"


def test_normalize_missing_job_url_returns_none(connector):
    """Job without jobUrl cannot be normalized (no external_id)."""
    raw = {"title": "Test", "applyUrl": "https://apply.com"}
    assert connector.normalize(raw) is None


def test_normalize_missing_title_returns_none(connector):
    """Job without title cannot be normalized."""
    raw = {"jobUrl": "https://jobs.ashbyhq.com/x/y"}
    assert connector.normalize(raw) is None


def test_fetch_raw_jobs_mocked(connector):
    """Fetch returns FetchResult with raw_jobs wrapped in provenance."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "jobs": [
            {
                "title": "Engineer",
                "jobUrl": "https://jobs.ashbyhq.com/ashby/engineer",
                "applyUrl": "https://jobs.ashbyhq.com/ashby/apply",
            },
        ],
    }
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp

    with patch("core.connectors.ashby.httpx.Client") as mock_client_class:
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        result = connector.fetch_raw_jobs()
    assert result.error is None
    assert result.stats["fetched"] == 1
    assert len(result.raw_jobs) == 1
    assert result.raw_jobs[0].raw_payload["title"] == "Engineer"
    assert "api.ashbyhq.com" in result.raw_jobs[0].provenance.source_url
