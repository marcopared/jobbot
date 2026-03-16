"""Tests for debug endpoints (EPIC 10)."""

import pytest
from httpx import ASGITransport
from dataclasses import asdict

from apps.api.main import app
from core.observability.failures import TaskFailureRecord


@pytest.fixture
async def client():
    """Async client for debug route tests."""
    transport = ASGITransport(app=app)
    async with pytest.importorskip("httpx").AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        yield ac


async def test_debug_failures_404_when_disabled(client):
    """GET /api/debug/failures returns 404 when DEBUG_ENDPOINTS_ENABLED is False (default)."""
    resp = await client.get("/api/debug/failures")
    assert resp.status_code == 404


def test_task_failure_record_no_raw_args_kwargs():
    """TaskFailureRecord stores only safe metadata, not raw args/kwargs (security)."""
    record = TaskFailureRecord(
        task_name="score_jobs",
        error="ConnectionError",
        timestamp="2025-01-01T00:00:00Z",
        retries=2,
        job_id="abc-123",
        run_id=None,
        args_count=1,
        kwargs_count=0,
    )
    d = asdict(record)
    assert "args" not in d
    assert "kwargs" not in d
    assert d["task_name"] == "score_jobs"
    assert d["args_count"] == 1
    assert d["kwargs_count"] == 0
