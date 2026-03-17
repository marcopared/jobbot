"""Tests for Lever connector normalization."""

from unittest.mock import MagicMock, patch

import pytest

from core.connectors.lever import create_lever_connector


@pytest.fixture
def connector():
    return create_lever_connector(
        client_name="leverdemo",
        company_name="Lever Demo",
    )


def test_normalize_full_job(connector):
    """Normalize a Lever posting with all fields."""
    raw = {
        "id": "33538a2f-d27d-4a96-8f05-fa4b0e4d940e",
        "text": "AbelsonTaylor Writer",
        "categories": {
            "commitment": "Regular Full Time (Salary)",
            "department": "Customer Success",
            "location": "Arlington, TX",
            "team": "Professional Services",
        },
        "hostedUrl": "https://jobs.lever.co/leverdemo/33538a2f-d27d-4a96-8f05-fa4b0e4d940e",
        "applyUrl": "https://jobs.lever.co/leverdemo/33538a2f-d27d-4a96-8f05-fa4b0e4d940e/apply",
        "createdAt": 1553186035299,
        "descriptionPlain": "Welcome to the Demo Job Listing.",
    }
    canonical = connector.normalize(raw)
    assert canonical is not None
    assert canonical.source_name == "lever"
    assert canonical.external_id == "33538a2f-d27d-4a96-8f05-fa4b0e4d940e"
    assert canonical.title == "AbelsonTaylor Writer"
    assert canonical.company == "Lever Demo"
    assert canonical.location == "Arlington, TX"
    assert canonical.employment_type == "Regular Full Time (Salary)"
    assert canonical.description == "Welcome to the Demo Job Listing."
    assert canonical.apply_url == "https://jobs.lever.co/leverdemo/33538a2f-d27d-4a96-8f05-fa4b0e4d940e/apply"
    assert canonical.source_url == "https://jobs.lever.co/leverdemo/33538a2f-d27d-4a96-8f05-fa4b0e4d940e"
    assert canonical.posted_at is not None
    assert canonical.normalized_title == "abelsontaylor writer"
    assert canonical.normalized_company == "lever demo"
    assert canonical.normalized_location == "arlington, tx"


def test_normalize_location_from_all_locations(connector):
    """When categories.location missing, use allLocations[0]."""
    raw = {
        "id": "abc-123",
        "text": "Engineer",
        "categories": {"allLocations": ["Remote", "New York"]},
        "hostedUrl": "https://jobs.lever.co/x/abc-123",
        "applyUrl": "https://jobs.lever.co/x/abc-123/apply",
    }
    canonical = connector.normalize(raw)
    assert canonical is not None
    assert canonical.location == "Remote"


def test_normalize_missing_id_returns_none(connector):
    """Job without id cannot be normalized."""
    raw = {"text": "Test", "hostedUrl": "https://jobs.lever.co/x/1"}
    assert connector.normalize(raw) is None


def test_normalize_missing_title_returns_none(connector):
    """Job without text (title) cannot be normalized."""
    raw = {"id": "abc", "hostedUrl": "https://jobs.lever.co/x/abc"}
    assert connector.normalize(raw) is None


def test_fetch_raw_jobs_mocked(connector):
    """Fetch returns FetchResult with raw_jobs wrapped in provenance."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {"id": "abc", "text": "Test Job", "hostedUrl": "https://jobs.lever.co/x/abc"},
    ]
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp

    with patch("core.connectors.lever.httpx.Client") as mock_client_class:
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        result = connector.fetch_raw_jobs()
    assert result.error is None
    assert result.stats["fetched"] == 1
    assert len(result.raw_jobs) == 1
    assert result.raw_jobs[0].raw_payload["text"] == "Test Job"
    assert "api.lever.co" in result.raw_jobs[0].provenance.source_url
