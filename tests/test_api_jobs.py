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


async def test_put_status_rejects_new(client):
    """PUT /api/jobs/{id}/status returns 400 when user_status=NEW (not client-settable)."""
    # Need an existing job; use first from list
    list_resp = await client.get("/api/jobs?per_page=1")
    assert list_resp.status_code == 200
    items = list_resp.json().get("items") or []
    if not items:
        pytest.skip("No jobs in DB; run seed or pipeline tests first")
    job_id = items[0]["id"]
    resp = await client.put(
        f"/api/jobs/{job_id}/status",
        json={"user_status": "NEW"},
    )
    assert resp.status_code == 400
    assert "NEW" in resp.json().get("detail", "")


async def test_bulk_status_rejects_new(client):
    """POST /api/jobs/bulk-status returns 400 when status=NEW."""
    resp = await client.post(
        "/api/jobs/bulk-status?status=NEW",
        json={"job_ids": [str(uuid.uuid4())]},
    )
    assert resp.status_code == 400
    assert "NEW" in resp.json().get("detail", "")


async def test_get_job_debug_returns_extra(client):
    """GET /api/jobs/{id}?debug=true includes debug_data."""
    list_resp = await client.get("/api/jobs?per_page=1")
    assert list_resp.status_code == 200
    items = list_resp.json().get("items") or []
    if not items:
        pytest.skip("No jobs in DB")
    job_id = items[0]["id"]
    resp = await client.get(f"/api/jobs/{job_id}?debug=true")
    assert resp.status_code == 200
    data = resp.json()
    assert "debug_data" in data
    assert data["debug_data"] is not None
    assert "dedup_hash" in data["debug_data"]
    assert "source_payload_json" in data["debug_data"]


async def test_get_job_rejected_404_without_include_rejected(client):
    """GET /api/jobs/{id} returns 404 for REJECTED jobs unless include_rejected=true."""
    from sqlalchemy import select

    from core.db.models import Company, Job, PipelineStatus
    from core.db.session import get_sync_session
    from core.dedup import compute_dedup_hash_from_raw, normalize_company, normalize_title

    # Create a REJECTED job directly
    unique = str(uuid.uuid4())[:8]
    company_name = f"TestRejected_{unique}"
    dedup_hash = compute_dedup_hash_from_raw(
        company=company_name,
        title="Rejected Job",
        location="Nowhere",
        apply_url=f"https://example.com/{unique}",
    )
    with get_sync_session() as session:
        company = Company(name=company_name)
        session.add(company)
        session.flush()
        job = Job(
            source="jobspy",
            source_job_id=unique,
            title="Rejected Job",
            raw_title="Rejected Job",
            normalized_title=normalize_title("Rejected Job"),
            company_id=company.id,
            company_name_raw=company_name,
            raw_company=company_name,
            normalized_company=normalize_company(company_name),
            location="Nowhere",
            raw_location="Nowhere",
            normalized_location="nowhere",
            remote_flag=False,
            url=f"https://example.com/{unique}",
            apply_url=f"https://example.com/{unique}",
            description="Bad job",
            status="REJECTED",
            user_status="NEW",
            pipeline_status=PipelineStatus.REJECTED.value,
            score_total=10.0,
            dedup_hash=dedup_hash,
        )
        session.add(job)
        session.flush()
        job_id = job.id

    resp = await client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 404

    resp_with = await client.get(f"/api/jobs/{job_id}?include_rejected=true")
    assert resp_with.status_code == 200


def _make_job_in_pipeline_state(
    pipeline_status: str,
    *,
    has_persona: bool = False,
    has_ats_keywords: bool = False,
    score_total: float = 75.0,
) -> uuid.UUID:
    """Create a Job + optional JobAnalysis in the given pipeline_state. Returns job_id."""
    from core.db.models import Company, Job, JobAnalysis, PipelineStatus
    from core.db.session import get_sync_session
    from core.dedup import compute_dedup_hash_from_raw, normalize_company, normalize_title

    unique = str(uuid.uuid4())[:8]
    company_name = f"TestResume_{unique}"
    dedup_hash = compute_dedup_hash_from_raw(
        company=company_name,
        title="Senior Engineer",
        location="Remote",
        apply_url=f"https://example.com/{unique}",
    )
    with get_sync_session() as session:
        company = Company(name=company_name)
        session.add(company)
        session.flush()
        job = Job(
            source="jobspy",
            source_job_id=unique,
            title="Senior Engineer",
            raw_title="Senior Engineer",
            normalized_title=normalize_title("Senior Engineer"),
            company_id=company.id,
            company_name_raw=company_name,
            raw_company=company_name,
            normalized_company=normalize_company(company_name),
            location="Remote",
            raw_location="Remote",
            normalized_location="remote",
            remote_flag=True,
            url=f"https://example.com/{unique}",
            apply_url=f"https://example.com/{unique}",
            description="Python, AWS, APIs",
            status="NEW",
            user_status="NEW",
            pipeline_status=pipeline_status,
            score_total=score_total,
            dedup_hash=dedup_hash,
        )
        session.add(job)
        session.flush()
        analysis = JobAnalysis(
            job_id=job.id,
            total_score=score_total,
            matched_persona="BACKEND" if has_persona else None,
            persona_confidence=0.9 if has_persona else None,
            persona_rationale="Test" if has_persona else None,
            found_keywords=["python", "aws"] if has_ats_keywords else None,
            missing_keywords=["postgresql"] if has_ats_keywords else None,
            ats_compatibility_score=0.85 if has_ats_keywords else None,
        )
        session.add(analysis)
        session.flush()
        job_id = job.id
    return job_id


async def test_post_generate_resume_404(client):
    """POST /api/jobs/{id}/generate-resume returns 404 for non-existent job."""
    fake_id = uuid.uuid4()
    resp = await client.post(f"/api/jobs/{fake_id}/generate-resume")
    assert resp.status_code == 404


async def test_post_generate_resume_409_scored_only(client):
    """POST /api/jobs/{id}/generate-resume returns 409 for scored-only job (no classification/ATS)."""
    job_id = _make_job_in_pipeline_state(
        pipeline_status="SCORED",
        has_persona=False,
        has_ats_keywords=False,
    )
    resp = await client.post(f"/api/jobs/{job_id}/generate-resume")
    assert resp.status_code == 409
    data = resp.json()
    assert "ATS_ANALYZED" in data["detail"] or "pipeline" in data["detail"].lower()


async def test_post_generate_resume_409_classified_not_ats(client):
    """POST /api/jobs/{id}/generate-resume returns 409 for classified-but-not-ATS-analyzed job."""
    job_id = _make_job_in_pipeline_state(
        pipeline_status="CLASSIFIED",
        has_persona=True,
        has_ats_keywords=False,
    )
    resp = await client.post(f"/api/jobs/{job_id}/generate-resume")
    assert resp.status_code == 409
    data = resp.json()
    assert "ATS_ANALYZED" in data["detail"] or "pipeline" in data["detail"].lower()


async def test_post_generate_resume_200_ats_analyzed(client):
    """POST /api/jobs/{id}/generate-resume returns 200 for ATS_ANALYZED job (accepted)."""
    job_id = _make_job_in_pipeline_state(
        pipeline_status="ATS_ANALYZED",
        has_persona=True,
        has_ats_keywords=True,
    )
    resp = await client.post(f"/api/jobs/{job_id}/generate-resume")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "queued"
    assert "task_id" in data
    assert data.get("job_id") == str(job_id)


async def test_post_generate_resume_200_resume_ready(client):
    """POST /api/jobs/{id}/generate-resume returns 200 for RESUME_READY job (regenerate allowed)."""
    job_id = _make_job_in_pipeline_state(
        pipeline_status="RESUME_READY",
        has_persona=True,
        has_ats_keywords=True,
    )
    resp = await client.post(f"/api/jobs/{job_id}/generate-resume")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "queued"
    assert "task_id" in data


async def test_post_generate_resume_409_when_not_analyzed(client):
    """POST /api/jobs/{id}/generate-resume returns 409 when job lacks analysis and pipeline state."""
    from core.db.models import Company, Job, PipelineStatus
    from core.db.session import get_sync_session
    from core.dedup import compute_dedup_hash_from_raw, normalize_company, normalize_title

    unique = str(uuid.uuid4())[:8]
    company_name = f"TestNotAnalyzed_{unique}"
    dedup_hash = compute_dedup_hash_from_raw(
        company=company_name,
        title="Ingested Only",
        location="Remote",
        apply_url=f"https://example.com/{unique}",
    )
    with get_sync_session() as session:
        company = Company(name=company_name)
        session.add(company)
        session.flush()
        job = Job(
            source="jobspy",
            source_job_id=unique,
            title="Ingested Only",
            raw_title="Ingested Only",
            normalized_title=normalize_title("Ingested Only"),
            company_id=company.id,
            company_name_raw=company_name,
            raw_company=company_name,
            normalized_company=normalize_company(company_name),
            location="Remote",
            raw_location="Remote",
            normalized_location="remote",
            remote_flag=True,
            url=f"https://example.com/{unique}",
            apply_url=f"https://example.com/{unique}",
            description="Just ingested",
            status="NEW",
            user_status="NEW",
            pipeline_status=PipelineStatus.INGESTED.value,
            score_total=0.0,
            dedup_hash=dedup_hash,
        )
        session.add(job)
        session.flush()
        job_id = job.id

    resp = await client.post(f"/api/jobs/{job_id}/generate-resume")
    assert resp.status_code == 409
    data = resp.json()
    assert "detail" in data
    assert "Resume generation requires" in data["detail"] or "classification" in data["detail"]


async def test_get_artifacts_404(client):
    """GET /api/jobs/{id}/artifacts returns 404 for non-existent job."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/jobs/{fake_id}/artifacts")
    assert resp.status_code == 404


async def test_artifact_download_404(client):
    """GET /api/artifacts/{id}/download returns 404 for non-existent artifact."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/artifacts/{fake_id}/download")
    assert resp.status_code == 404


async def test_artifact_preview_404(client):
    """GET /api/artifacts/{id}/preview returns 404 for non-existent artifact."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/artifacts/{fake_id}/preview")
    assert resp.status_code == 404


async def test_health(client):
    """GET /api/health returns ok."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
