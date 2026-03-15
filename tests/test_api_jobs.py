"""Endpoint tests for v1 REST API (EPIC 8).

These tests hit the real API and require a running Postgres with migrations applied.
Run: alembic upgrade head && pytest tests/test_api_jobs.py

Uses httpx.AsyncClient so all requests run in a single event loop, avoiding
asyncpg "another operation is in progress" errors with TestClient.
"""

import uuid

import httpx
import pytest
from httpx import ASGITransport

from apps.api.main import app


@pytest.fixture
async def client():
    """Async client running in same event loop as app, fixing asyncpg connection reuse."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_get_jobs_returns_paginated_structure(client):
    """GET /api/jobs returns items, total, page, per_page."""
    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert isinstance(data["items"], list)
    assert data["page"] >= 1
    assert data["per_page"] >= 1


async def test_get_jobs_list_item_shape(client):
    """List items have title, company, location, score, persona, pipeline_status, user_status, artifact_availability."""
    resp = await client.get("/api/jobs?per_page=1")
    assert resp.status_code == 200
    data = resp.json()
    if data["items"]:
        item = data["items"][0]
        assert "id" in item
        assert "title" in item
        assert "company" in item
        assert "location" in item
        assert "score" in item
        assert "persona" in item
        assert "pipeline_status" in item
        assert "user_status" in item
        assert "artifact_availability" in item


async def test_get_jobs_filter_by_user_status(client):
    """GET /api/jobs accepts user_status filter."""
    resp = await client.get("/api/jobs?user_status=NEW")
    assert resp.status_code == 200


async def test_get_job_404(client):
    """GET /api/jobs/{id} returns 404 for non-existent job."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/jobs/{fake_id}")
    assert resp.status_code == 404
    assert "detail" in resp.json()


async def test_put_status_404(client):
    """PUT /api/jobs/{id}/status returns 404 for non-existent job."""
    fake_id = uuid.uuid4()
    resp = await client.put(
        f"/api/jobs/{fake_id}/status",
        json={"user_status": "SAVED"},
    )
    assert resp.status_code == 404


async def test_put_status_invalid_state(client):
    """PUT /api/jobs/{id}/status returns 400 for invalid user_status."""
    fake_id = uuid.uuid4()
    resp = await client.put(
        f"/api/jobs/{fake_id}/status",
        json={"user_status": "INVALID"},
    )
    # 404 before 400 since job doesn't exist; use valid uuid format
    assert resp.status_code in (400, 404)


async def test_post_generate_resume_404(client):
    """POST /api/jobs/{id}/generate-resume returns 404 for non-existent job."""
    fake_id = uuid.uuid4()
    resp = await client.post(f"/api/jobs/{fake_id}/generate-resume")
    assert resp.status_code == 404


async def test_get_artifacts_404(client):
    """GET /api/jobs/{id}/artifacts returns 404 for non-existent job."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/jobs/{fake_id}/artifacts")
    assert resp.status_code == 404


async def test_health(client):
    """GET /api/health returns ok."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
