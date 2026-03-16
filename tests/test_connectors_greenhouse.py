"""Tests for Greenhouse connector normalization."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.connectors.greenhouse import (
    GreenhouseConnector,
    GreenhouseConnectorConfig,
    create_greenhouse_connector,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "greenhouse"


@pytest.fixture
def sample_response():
    with open(FIXTURES_DIR / "sample_jobs_response.json") as f:
        return json.load(f)


@pytest.fixture
def connector():
    return create_greenhouse_connector(
        board_token="acme",
        company_name="Acme Corp",
    )


def test_normalize_full_job(connector, sample_response):
    """Normalize a job with all fields present."""
    raw = sample_response["jobs"][0]
    canonical = connector.normalize(raw)
    assert canonical is not None
    assert canonical.source_name == "greenhouse"
    assert canonical.external_id == "127817"
    assert canonical.title == "Senior Software Engineer"
    assert canonical.company == "Acme Corp"
    assert canonical.location == "San Francisco, CA"
    assert canonical.employment_type == "Full-time"
    assert canonical.description == "<p>We are looking for a Senior Software Engineer to build scalable systems.</p>"
    assert canonical.apply_url == "https://boards.greenhouse.io/acme/jobs/127817"
    assert canonical.source_url == "https://boards.greenhouse.io/acme/jobs/127817"
    assert canonical.posted_at is not None
    assert canonical.raw_payload == raw
    assert canonical.normalized_title == "senior software engineer"
    assert canonical.normalized_company == "acme corp"
    assert canonical.normalized_location == "san francisco, ca"


def test_normalize_remote_job(connector, sample_response):
    """Normalize a job with minimal metadata (metadata null)."""
    raw = sample_response["jobs"][1]
    canonical = connector.normalize(raw)
    assert canonical is not None
    assert canonical.external_id == "127818"
    assert canonical.title == "Platform Engineer"
    assert canonical.company == "Acme Corp"
    assert canonical.location == "Remote"
    assert canonical.employment_type is None
    assert canonical.description == "<p>Remote-first platform role.</p>"


def test_normalize_location_from_offices(connector, sample_response):
    """When location.name is empty, use first office location."""
    raw = sample_response["jobs"][2]
    canonical = connector.normalize(raw)
    assert canonical is not None
    assert canonical.location == "New York, NY, United States"
    assert canonical.employment_type == "Part-time"


def test_normalize_missing_id_returns_none(connector):
    """Job without id cannot be normalized."""
    raw = {"title": "Test", "absolute_url": "https://example.com/jobs/1"}
    assert connector.normalize(raw) is None


def test_normalize_missing_title_returns_none(connector):
    """Job without title cannot be normalized."""
    raw = {"id": 123, "absolute_url": "https://example.com/jobs/123"}
    assert connector.normalize(raw) is None


def test_normalize_empty_company_returns_none():
    """Job with empty company_name in config cannot be normalized."""
    conn = create_greenhouse_connector(board_token="x", company_name="")
    raw = {"id": 1, "title": "Test", "absolute_url": "https://x.com/job/1"}
    assert conn.normalize(raw) is None


def test_fetch_raw_jobs_mocked(connector):
    """Fetch returns FetchResult with raw_jobs wrapped in provenance."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"jobs": [{"id": 1, "title": "Test"}], "meta": {"total": 1}}
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("core.connectors.greenhouse.httpx.Client") as mock_client_class:
        mock_client_class.return_value = mock_client
        result = connector.fetch_raw_jobs(include_content=True)
    assert result.error is None
    assert result.stats["fetched"] == 1
    assert len(result.raw_jobs) == 1
    assert result.raw_jobs[0].raw_payload == {"id": 1, "title": "Test"}
    assert result.raw_jobs[0].provenance.source_url == "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    assert result.raw_jobs[0].provenance.fetch_timestamp


def test_fetch_http_error_returns_error(connector):
    """Fetch returns error on HTTP failure."""
    import httpx as httpx_mod

    mock_client = MagicMock()
    mock_client.get.side_effect = httpx_mod.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("core.connectors.greenhouse.httpx.Client") as mock_client_class:
        mock_client_class.return_value = mock_client
        result = connector.fetch_raw_jobs()
    assert result.error is not None
    assert result.raw_jobs == []
    assert result.stats.get("fetched", 0) == 0
