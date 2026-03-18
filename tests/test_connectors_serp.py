"""Tests for SERP1 discovery connector DataForSEO implementation."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from core.connectors.serp import create_serp1_connector


@pytest.fixture
def connector():
    return create_serp1_connector(
        login="login",
        password="password",
        base_url="https://api.dataforseo.com",
        location_name="United States",
        language_name="English",
        poll_max_attempts=3,
        poll_interval_seconds=0.1,
        poll_timeout_seconds=5.0,
    )


def _task_post_response(task_id: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "status_code": 20000,
        "tasks": [
            {
                "id": task_id,
                "status_code": 20100,
                "status_message": "Task Created.",
                "result": None,
            }
        ],
    }
    return resp


def _tasks_ready_response(task_id: str, ready: bool) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    results = [{"id": task_id}] if ready else []
    resp.json.return_value = {
        "status_code": 20000,
        "tasks": [
            {
                "status_code": 20000,
                "result": results,
            }
        ],
    }
    return resp


def _advanced_response(task_id: str, items: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "status_code": 20000,
        "tasks": [
            {
                "id": task_id,
                "status_code": 20000,
                "result": [
                    {
                        "check_url": "https://www.google.com/search?q=backend+jobs",
                        "items": items,
                    }
                ],
            }
        ],
    }
    return resp


def test_serp1_source_name(connector):
    assert connector.source_name == "serp1"


def test_fetch_raw_jobs_task_submission_polling_and_advanced_success(connector):
    task_id = "123e4567-e89b-12d3-a456-426614174000"
    item = {
        "job_id": "google-job-1",
        "title": "Senior Backend Engineer",
        "employer_name": "Acme",
        "location": "Remote",
        "source_url": "https://example.com/jobs/1",
        "timestamp": "2025-05-01 10:00:00 +00:00",
    }

    mock_client = MagicMock()
    mock_client.post.return_value = _task_post_response(task_id)
    mock_client.get.side_effect = [
        _tasks_ready_response(task_id, ready=False),
        _tasks_ready_response(task_id, ready=True),
        _advanced_response(task_id, [item]),
    ]

    with patch("core.connectors.serp.httpx.Client") as mock_client_class:
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        with patch("core.connectors.serp.time.sleep") as mock_sleep:
            result = connector.fetch_raw_jobs(query="backend engineer", location="Remote")

    assert result.error is None
    assert result.stats["fetched"] == 1
    assert result.stats["errors"] == 0
    assert len(result.raw_jobs) == 1
    assert result.raw_jobs[0].raw_payload["job_id"] == "google-job-1"
    assert result.raw_jobs[0].raw_payload["_task_id"] == task_id
    assert result.raw_jobs[0].provenance.source_url == "https://www.google.com/search?q=backend+jobs"

    assert mock_client.post.call_count == 1
    assert mock_client.get.call_count == 3
    post_url = mock_client.post.call_args.args[0]
    assert post_url.endswith("/v3/serp/google/jobs/task_post")

    ready_url = mock_client.get.call_args_list[0].args[0]
    assert ready_url.endswith("/v3/serp/google/jobs/tasks_ready")

    advanced_url = mock_client.get.call_args_list[2].args[0]
    assert advanced_url.endswith(f"/v3/serp/google/jobs/task_get/advanced/{task_id}")

    payload = mock_client.post.call_args.kwargs["json"][0]
    assert payload["keyword"] == "backend engineer"
    assert payload["location_name"] == "Remote"
    assert payload["language_name"] == "English"
    assert payload["priority"] == 1
    mock_sleep.assert_called_once()


def test_fetch_raw_jobs_missing_credentials_returns_error():
    connector = create_serp1_connector(
        login="",
        password="",
        location_name="United States",
        language_name="English",
    )
    result = connector.fetch_raw_jobs(query="engineer")
    assert result.error is not None
    assert "DATAFORSEO_LOGIN" in result.error
    assert "DATAFORSEO_PASSWORD" in result.error
    assert result.stats["errors"] == 1
    assert result.raw_jobs == []


def test_fetch_raw_jobs_readiness_timeout_returns_error(connector):
    task_id = "123e4567-e89b-12d3-a456-426614174001"

    mock_client = MagicMock()
    mock_client.post.return_value = _task_post_response(task_id)
    mock_client.get.side_effect = [
        _tasks_ready_response(task_id, ready=False),
        _tasks_ready_response(task_id, ready=False),
        _tasks_ready_response(task_id, ready=False),
    ]

    with patch("core.connectors.serp.httpx.Client") as mock_client_class:
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        with patch("core.connectors.serp.time.sleep"):
            result = connector.fetch_raw_jobs(query="backend engineer")

    assert result.error is not None
    assert "readiness timeout" in result.error.lower()
    assert result.stats["errors"] == 1
    assert result.raw_jobs == []


def test_fetch_raw_jobs_advanced_get_failure_returns_error(connector):
    task_id = "123e4567-e89b-12d3-a456-426614174002"

    mock_client = MagicMock()
    mock_client.post.return_value = _task_post_response(task_id)
    mock_client.get.side_effect = [
        _tasks_ready_response(task_id, ready=True),
        httpx.HTTPStatusError(
            "advanced failed",
            request=MagicMock(),
            response=MagicMock(status_code=500, text="boom"),
        ),
    ]

    with patch("core.connectors.serp.httpx.Client") as mock_client_class:
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        result = connector.fetch_raw_jobs(query="backend engineer")

    assert result.error is not None
    assert "HTTP error" in result.error
    assert result.stats["errors"] == 1
    assert result.raw_jobs == []


def test_fetch_raw_jobs_empty_results(connector):
    task_id = "123e4567-e89b-12d3-a456-426614174003"

    mock_client = MagicMock()
    mock_client.post.return_value = _task_post_response(task_id)
    mock_client.get.side_effect = [
        _tasks_ready_response(task_id, ready=True),
        _advanced_response(task_id, []),
    ]

    with patch("core.connectors.serp.httpx.Client") as mock_client_class:
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
        result = connector.fetch_raw_jobs(query="backend engineer")

    assert result.error is None
    assert result.stats["fetched"] == 0
    assert result.stats["errors"] == 0
    assert result.raw_jobs == []


def test_normalize_maps_fields_and_derived_external_id(connector):
    raw = {
        "title": "Staff Platform Engineer",
        "employer_name": "Example Corp",
        "location": "Austin, TX",
        "source_url": "https://example.com/jobs/staff-platform",
        "snippet": "Build distributed systems and developer platforms.",
        "timestamp": "2025-06-02 09:30:00 +00:00",
        "contract_type": "fulltime",
    }

    canonical = connector.normalize(raw)
    assert canonical is not None
    assert canonical.source_name == "serp1"
    assert canonical.external_id.startswith("serp1-")
    assert canonical.title == "Staff Platform Engineer"
    assert canonical.company == "Example Corp"
    assert canonical.location == "Austin, TX"
    assert canonical.description == "Build distributed systems and developer platforms."
    assert canonical.source_url == "https://example.com/jobs/staff-platform"
    assert canonical.apply_url == "https://example.com/jobs/staff-platform"
    assert canonical.posted_at is not None
    assert canonical.employment_type == "fulltime"
    assert canonical.normalized_title == "staff platform engineer"
    assert canonical.normalized_company == "example corp"
    assert canonical.normalized_location == "austin, tx"


def test_normalize_uses_provider_job_id_when_present(connector):
    raw = {
        "job_id": "google-job-123",
        "title": "Backend Engineer",
        "employer_name": "Acme",
    }

    canonical = connector.normalize(raw)
    assert canonical is not None
    assert canonical.external_id == "google-job-123"


def test_normalize_returns_none_when_title_missing(connector):
    assert connector.normalize({"job_id": "x"}) is None
