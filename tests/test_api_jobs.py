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


async def test_get_job_debug_disabled_no_internal_data(client):
    """GET /api/jobs/{id}?debug=true omits debug_data when DEBUG_ENDPOINTS_ENABLED is False (default)."""
    list_resp = await client.get("/api/jobs?per_page=1")
    assert list_resp.status_code == 200
    items = list_resp.json().get("items") or []
    if not items:
        pytest.skip("No jobs in DB")
    job_id = items[0]["id"]
    resp = await client.get(f"/api/jobs/{job_id}?debug=true")
    assert resp.status_code == 200
    data = resp.json()
    # debug_data must be None/omitted when debug endpoints are disabled
    assert data.get("debug_data") is None
    assert "dedup_hash" not in (data.get("debug_data") or {})
    assert "source_payload_json" not in (data.get("debug_data") or {})


async def test_get_job_debug_enabled_returns_data(client, monkeypatch):
    """GET /api/jobs/{id}?debug=true includes debug_data when DEBUG_ENDPOINTS_ENABLED is True."""
    from apps.api.routes import jobs as jobs_route

    monkeypatch.setattr(jobs_route.settings, "debug_endpoints_enabled", True)
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
    from core.dedup import (
        compute_dedup_hash_from_raw,
        normalize_company,
        normalize_title,
    )

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
    from core.dedup import (
        compute_dedup_hash_from_raw,
        normalize_company,
        normalize_title,
    )

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
    from core.dedup import (
        compute_dedup_hash_from_raw,
        normalize_company,
        normalize_title,
    )

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
    assert (
        "Resume generation requires" in data["detail"]
        or "classification" in data["detail"]
    )


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


async def test_run_ingestion_greenhouse_success(client):
    """POST /api/jobs/run-ingestion with connector=greenhouse returns run_id and task_id."""
    resp = await client.post(
        "/api/jobs/run-ingestion",
        json={
            "connector": "greenhouse",
            "board_token": "acme",
            "company_name": "Acme Corp",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert "task_id" in data
    assert data.get("status") == "RUNNING"


async def test_run_ingestion_lever_requires_client_name(client):
    """POST /api/jobs/run-ingestion with connector=lever requires client_name."""
    resp = await client.post(
        "/api/jobs/run-ingestion",
        json={"connector": "lever", "company_name": "Acme"},
    )
    assert resp.status_code == 400
    assert "client_name" in resp.json().get("detail", "").lower()


async def test_run_ingestion_ashby_requires_job_board_name(client):
    """POST /api/jobs/run-ingestion with connector=ashby requires job_board_name."""
    resp = await client.post(
        "/api/jobs/run-ingestion",
        json={"connector": "ashby", "company_name": "Acme"},
    )
    assert resp.status_code == 400
    assert "job_board_name" in resp.json().get("detail", "").lower()


async def test_run_ingestion_unsupported_connector(client):
    """POST /api/jobs/run-ingestion with invalid connector returns 422 (Pydantic validation)."""
    resp = await client.post(
        "/api/jobs/run-ingestion",
        json={
            "connector": "unknown",
            "board_token": "x",
            "company_name": "X",
        },
    )
    assert resp.status_code == 422


async def test_ingest_url_unsupported_returns_400(client):
    """POST /api/jobs/ingest-url with unsupported URL returns 400."""
    resp = await client.post(
        "/api/jobs/ingest-url",
        json={"url": "https://example.com/jobs/123"},
    )
    assert resp.status_code == 400
    assert (
        "unsupported" in resp.json().get("detail", "").lower()
        or "supported" in resp.json().get("detail", "").lower()
    )


async def test_ingest_url_supported_accepts(client):
    """POST /api/jobs/ingest-url with supported URL returns run_id and task_id."""
    resp = await client.post(
        "/api/jobs/ingest-url",
        json={"url": "https://boards.greenhouse.io/acme/jobs/127817"},
    )
    # 403 if URL_INGEST_ENABLED=false; 200 otherwise
    assert resp.status_code in (200, 403)
    if resp.status_code == 200:
        data = resp.json()
        assert "run_id" in data
        assert "task_id" in data
        assert data.get("provider") == "greenhouse"


async def test_run_ingestion_greenhouse_requires_board_token(client):
    """POST run-ingestion with greenhouse requires board_token."""
    resp = await client.post(
        "/api/jobs/run-ingestion",
        json={"connector": "greenhouse", "company_name": "Acme"},
    )
    assert resp.status_code == 400
    assert "board_token" in resp.json().get("detail", "")


async def test_health(client):
    """GET /api/health returns ok."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- Ingestion route tests (PR 3: ATS expansion) ---


async def test_run_ingestion_greenhouse_accepts_body(client):
    """POST /api/jobs/run-ingestion with connector=greenhouse enqueues task."""
    resp = await client.post(
        "/api/jobs/run-ingestion",
        json={
            "connector": "greenhouse",
            "board_token": "acme",
            "company_name": "Acme Corp",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert "task_id" in data
    assert data.get("status") == "RUNNING"


async def test_run_ingestion_lever_requires_client_name(client):
    """POST /api/jobs/run-ingestion with connector=lever returns 400 when client_name missing."""
    resp = await client.post(
        "/api/jobs/run-ingestion",
        json={
            "connector": "lever",
            "company_name": "Acme",
        },
    )
    assert resp.status_code == 400
    assert "client_name" in resp.json().get("detail", "").lower()


async def test_run_ingestion_ashby_requires_job_board_name(client):
    """POST /api/jobs/run-ingestion with connector=ashby returns 400 when job_board_name missing."""
    resp = await client.post(
        "/api/jobs/run-ingestion",
        json={
            "connector": "ashby",
            "company_name": "Acme",
        },
    )
    assert resp.status_code == 400
    assert "job_board_name" in resp.json().get("detail", "").lower()


async def test_run_ingestion_unsupported_connector_returns_400(client):
    """POST /api/jobs/run-ingestion with unsupported connector returns 400 or 422."""
    resp = await client.post(
        "/api/jobs/run-ingestion",
        json={
            "connector": "unknown",
            "company_name": "Acme",
        },
    )
    assert resp.status_code in (400, 422)


async def test_ingest_url_unsupported_returns_400(client):
    """POST /api/jobs/ingest-url with unsupported URL returns 400."""
    resp = await client.post(
        "/api/jobs/ingest-url",
        json={"url": "https://example.com/jobs/123"},
    )
    assert resp.status_code == 400
    assert (
        "unsupported" in resp.json().get("detail", "").lower()
        or "supported" in resp.json().get("detail", "").lower()
    )


async def test_ingest_url_supported_returns_200(client):
    """POST /api/jobs/ingest-url with supported Greenhouse URL enqueues task."""
    resp = await client.post(
        "/api/jobs/ingest-url",
        json={"url": "https://boards.greenhouse.io/acme/jobs/127817"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert "task_id" in data
    assert data.get("provider") == "greenhouse"


# --- Discovery route tests (PR 4) ---


async def test_run_discovery_agg1_returns_200_when_enabled(client, monkeypatch):
    """POST /api/jobs/run-discovery with connector=agg1 returns run_id when enabled."""
    from apps.api.routes import jobs as jobs_route

    monkeypatch.setattr(jobs_route.settings, "enable_agg1_discovery", True)
    resp = await client.post(
        "/api/jobs/run-discovery",
        json={"connector": "agg1", "query": "engineer", "location": "San Francisco"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert "task_id" in data
    assert data.get("status") == "RUNNING"
    assert data.get("connector") == "agg1"


async def test_run_discovery_agg1_returns_403_when_disabled(client, monkeypatch):
    """POST /api/jobs/run-discovery with connector=agg1 returns 403 when disabled."""
    from apps.api.routes import jobs as jobs_route

    monkeypatch.setattr(jobs_route.settings, "enable_agg1_discovery", False)
    resp = await client.post(
        "/api/jobs/run-discovery",
        json={"connector": "agg1"},
    )
    assert resp.status_code == 403
    assert (
        "disabled" in resp.json().get("detail", "").lower()
        or "agg1" in resp.json().get("detail", "").lower()
    )


async def test_run_discovery_serp1_returns_403_when_disabled(client, monkeypatch):
    """POST /api/jobs/run-discovery with connector=serp1 returns 403 when disabled."""
    from apps.api.routes import jobs as jobs_route

    monkeypatch.setattr(jobs_route.settings, "enable_serp1_discovery", False)
    resp = await client.post(
        "/api/jobs/run-discovery",
        json={"connector": "serp1"},
    )
    assert resp.status_code == 403
    assert (
        "disabled" in resp.json().get("detail", "").lower()
        or "serp1" in resp.json().get("detail", "").lower()
    )


async def test_run_discovery_serp1_returns_200_when_enabled(client, monkeypatch):
    """POST /api/jobs/run-discovery with connector=serp1 enqueues task when enabled (stub returns empty)."""
    from apps.api.routes import jobs as jobs_route

    monkeypatch.setattr(jobs_route.settings, "enable_serp1_discovery", True)
    resp = await client.post(
        "/api/jobs/run-discovery",
        json={"connector": "serp1", "query": "engineer", "location": "Remote"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert "task_id" in data
    assert data.get("status") == "RUNNING"
    assert data.get("connector") == "serp1"


async def test_run_discovery_unsupported_connector_returns_422(client):
    """POST /api/jobs/run-discovery with invalid connector returns 422."""
    resp = await client.post(
        "/api/jobs/run-discovery",
        json={"connector": "unknown"},
    )
    assert resp.status_code == 422


async def test_list_source_adapter_capabilities_exposes_operator_families(
    client, monkeypatch
):
    """GET /api/jobs/run-source-adapter lists adapter-backed launch metadata."""
    from apps.api.routes import jobs as jobs_route

    monkeypatch.setattr(jobs_route.settings, "startupjobs_nyc_enabled", True)
    monkeypatch.setattr(jobs_route.settings, "technyc_enabled", True)
    monkeypatch.setattr(jobs_route.settings, "linkedin_jobs_enabled", True)
    monkeypatch.setattr(jobs_route.settings, "bb_browser_enabled", True)

    resp = await client.get("/api/jobs/run-source-adapter")
    assert resp.status_code == 200
    items = {item["source_name"]: item for item in resp.json()["items"]}

    assert "startupjobs_nyc" in items
    assert items["startupjobs_nyc"]["source_family"] == "public_board"
    assert items["startupjobs_nyc"]["backend"] == "scrapling"
    assert items["startupjobs_nyc"]["launch_enabled"] is True

    assert "technyc" in items
    assert items["technyc"]["source_family"] == "portfolio_board"
    assert items["technyc"]["family_label"] == "Portfolio boards"
    assert items["technyc"]["backend"] == "scrapling"
    assert items["technyc"]["launch_enabled"] is True

    assert "linkedin_jobs" in items
    assert items["linkedin_jobs"]["source_family"] == "auth_board"
    assert items["linkedin_jobs"]["backend"] == "bb_browser"
    assert items["linkedin_jobs"]["launch_enabled"] is True


async def test_run_source_adapter_portfolio_board_returns_200(client, monkeypatch):
    """POST /api/jobs/run-source-adapter launches a portfolio-board adapter run via the public worker."""
    from apps.api.routes import jobs as jobs_route

    monkeypatch.setattr(jobs_route.settings, "technyc_enabled", True)
    monkeypatch.setattr(
        jobs_route.run_public_board_source,
        "delay",
        lambda **kwargs: type("TaskResult", (), {"id": "portfolio-adapter-task"})(),
    )

    resp = await client.post(
        "/api/jobs/run-source-adapter",
        json={"source_name": "technyc", "max_results": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RUNNING"
    assert data["source_name"] == "technyc"
    assert data["source_family"] == "portfolio_board"
    assert data["backend"] == "scrapling"
    assert data["task_id"] == "portfolio-adapter-task"
    assert data["run_id"]


async def test_run_source_adapter_public_board_returns_200(client, monkeypatch):
    """POST /api/jobs/run-source-adapter launches a public-board adapter run."""
    from apps.api.routes import jobs as jobs_route

    monkeypatch.setattr(jobs_route.settings, "startupjobs_nyc_enabled", True)
    monkeypatch.setattr(
        jobs_route.run_public_board_source,
        "delay",
        lambda **kwargs: type("TaskResult", (), {"id": "public-adapter-task"})(),
    )

    resp = await client.post(
        "/api/jobs/run-source-adapter",
        json={"source_name": "startupjobs_nyc", "max_results": 7},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RUNNING"
    assert data["source_name"] == "startupjobs_nyc"
    assert data["source_family"] == "public_board"
    assert data["backend"] == "scrapling"
    assert data["task_id"] == "public-adapter-task"
    assert data["run_id"]


async def test_run_source_adapter_auth_board_returns_200(client, monkeypatch):
    """POST /api/jobs/run-source-adapter launches an auth-board adapter run."""
    from apps.api.routes import jobs as jobs_route

    monkeypatch.setattr(jobs_route.settings, "linkedin_jobs_enabled", True)
    monkeypatch.setattr(jobs_route.settings, "bb_browser_enabled", True)
    monkeypatch.setattr(
        jobs_route.run_auth_board_source,
        "delay",
        lambda **kwargs: type("TaskResult", (), {"id": "auth-adapter-task"})(),
    )

    resp = await client.post(
        "/api/jobs/run-source-adapter",
        json={"source_name": "linkedin_jobs", "max_results": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RUNNING"
    assert data["source_name"] == "linkedin_jobs"
    assert data["source_family"] == "auth_board"
    assert data["backend"] == "bb_browser"
    assert data["task_id"] == "auth-adapter-task"
    assert data["run_id"]


async def test_run_source_adapter_returns_403_when_backend_disabled(client, monkeypatch):
    """POST /api/jobs/run-source-adapter rejects auth-board launches when bb-browser is off."""
    from apps.api.routes import jobs as jobs_route

    monkeypatch.setattr(jobs_route.settings, "linkedin_jobs_enabled", True)
    monkeypatch.setattr(jobs_route.settings, "bb_browser_enabled", False)

    resp = await client.post(
        "/api/jobs/run-source-adapter",
        json={"source_name": "linkedin_jobs"},
    )
    assert resp.status_code == 403
    assert "BB_BROWSER_ENABLED=false" in resp.json()["detail"]


# --- Manual ingest route tests ---


MANUAL_INGEST_PAYLOAD = {
    "title": "Senior Backend Engineer",
    "company": "Acme Corp",
    "location": "Remote",
    "apply_url": "https://example.com/apply/unique-test-job",
    "description": "Build scalable APIs in Python.",
}


async def test_manual_ingest_missing_required_fields(client):
    """POST /api/jobs/manual-ingest returns 422 when required fields are missing."""
    resp = await client.post("/api/jobs/manual-ingest", json={})
    assert resp.status_code == 422


async def test_manual_ingest_missing_title(client):
    """POST /api/jobs/manual-ingest returns 422 when title is missing."""
    payload = {**MANUAL_INGEST_PAYLOAD}
    del payload["title"]
    resp = await client.post("/api/jobs/manual-ingest", json=payload)
    assert resp.status_code == 422


async def test_manual_ingest_success(client):
    """POST /api/jobs/manual-ingest persists job, returns run_id and job_id."""
    unique = str(uuid.uuid4())[:8]
    payload = {
        **MANUAL_INGEST_PAYLOAD,
        "apply_url": f"https://example.com/apply/{unique}",
        "title": f"Senior Backend Engineer {unique}",
    }
    resp = await client.post("/api/jobs/manual-ingest", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["run_id"]
    assert data["job_id"]
    assert data.get("task_id")

    # Verify job exists and is INGESTED
    job_resp = await client.get(f"/api/jobs/{data['job_id']}")
    assert job_resp.status_code == 200
    job_data = job_resp.json()
    assert job_data["title"].startswith("Senior Backend Engineer")
    assert job_data["company"] == "Acme Corp"
    assert job_data["pipeline_status"] == "INGESTED"
    assert job_data["source"] == "manual_intake"


async def test_manual_ingest_duplicate(client):
    """POST /api/jobs/manual-ingest returns DUPLICATE for identical job."""
    unique = str(uuid.uuid4())[:8]
    payload = {
        **MANUAL_INGEST_PAYLOAD,
        "apply_url": f"https://example.com/apply/dup-{unique}",
        "title": f"Dup Test Engineer {unique}",
    }
    resp1 = await client.post("/api/jobs/manual-ingest", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "SUCCESS"

    resp2 = await client.post("/api/jobs/manual-ingest", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "DUPLICATE"
    assert data2["job_id"] is None
    assert data2["run_id"]


async def test_manual_ingest_with_optional_fields(client):
    """POST /api/jobs/manual-ingest accepts optional fields."""
    unique = str(uuid.uuid4())[:8]
    payload = {
        **MANUAL_INGEST_PAYLOAD,
        "apply_url": f"https://example.com/apply/opt-{unique}",
        "title": f"Full Stack {unique}",
        "source_url": "https://example.com/listing",
        "posted_at": "2026-03-15T10:00:00",
        "salary_min": 120000,
        "salary_max": 180000,
        "workplace_type": "remote",
        "employment_type": "full_time",
    }
    resp = await client.post("/api/jobs/manual-ingest", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["job_id"]

    job_resp = await client.get(f"/api/jobs/{data['job_id']}")
    assert job_resp.status_code == 200
    job_data = job_resp.json()
    assert job_data["salary_min"] == 120000
    assert job_data["salary_max"] == 180000


async def test_manual_ingest_run_visible(client):
    """Manual ingest creates a ScrapeRun that is visible in /api/runs."""
    unique = str(uuid.uuid4())[:8]
    payload = {
        **MANUAL_INGEST_PAYLOAD,
        "apply_url": f"https://example.com/apply/run-{unique}",
        "title": f"Run Vis Test {unique}",
    }
    resp = await client.post("/api/jobs/manual-ingest", json=payload)
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    runs_resp = await client.get("/api/runs")
    assert runs_resp.status_code == 200
    run_ids = [r["id"] for r in runs_resp.json()["items"]]
    assert run_id in run_ids


# --- GenerationRun tracking for manual resume generation ---


async def test_manual_generate_resume_persists_and_returns_generation_run_id(
    client, monkeypatch
):
    """Manual generate persists a GenerationRun, returns its id, and queues the worker with it."""
    from apps.api.routes import jobs as jobs_route
    from core.db.models import GenerationRun
    from core.db.session import get_sync_session

    job_id = _make_job_in_pipeline_state(
        pipeline_status="ATS_ANALYZED",
        has_persona=True,
        has_ats_keywords=True,
    )
    captured: dict[str, str] = {}

    class DummyTask:
        id = "manual-generation-task"

    def _fake_delay(job_id_arg, generation_run_id=None, triggered_by="manual"):
        captured["job_id"] = job_id_arg
        captured["generation_run_id"] = generation_run_id
        captured["triggered_by"] = triggered_by
        return DummyTask()

    monkeypatch.setattr(jobs_route.generate_grounded_resume_task, "delay", _fake_delay)

    resp = await client.post(f"/api/jobs/{job_id}/generate-resume")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["generation_run_id"] is not None
    assert data["job_id"] == str(job_id)
    assert data["task_id"] == "manual-generation-task"

    # Verify GenerationRun was persisted
    run_id = uuid.UUID(data["generation_run_id"])
    with get_sync_session() as session:
        run = session.get(GenerationRun, run_id)
        assert run is not None
        assert run.job_id == job_id
        assert run.status == "queued"
        assert run.triggered_by == "manual"

    assert captured["job_id"] == str(job_id)
    assert captured["generation_run_id"] == data["generation_run_id"]
    assert captured["triggered_by"] == "manual"


async def test_manual_generate_resume_run_id_returned_for_resume_ready(client):
    """POST /api/jobs/{id}/generate-resume on RESUME_READY job also creates a GenerationRun."""
    from core.db.models import GenerationRun
    from core.db.session import get_sync_session

    job_id = _make_job_in_pipeline_state(
        pipeline_status="RESUME_READY",
        has_persona=True,
        has_ats_keywords=True,
    )
    resp = await client.post(f"/api/jobs/{job_id}/generate-resume")
    assert resp.status_code == 200
    data = resp.json()
    assert data["generation_run_id"] is not None

    run_id = uuid.UUID(data["generation_run_id"])
    with get_sync_session() as session:
        run = session.get(GenerationRun, run_id)
        assert run is not None
        assert run.triggered_by == "manual"


async def test_manual_generate_resume_409_no_generation_run(client):
    """POST /api/jobs/{id}/generate-resume with ineligible status does not create a GenerationRun."""
    from core.db.models import GenerationRun
    from core.db.session import get_sync_session
    from sqlalchemy import select

    job_id = _make_job_in_pipeline_state(
        pipeline_status="SCORED",
        has_persona=False,
        has_ats_keywords=False,
    )
    resp = await client.post(f"/api/jobs/{job_id}/generate-resume")
    assert resp.status_code == 409

    # No GenerationRun should exist for this job
    with get_sync_session() as session:
        result = session.execute(
            select(GenerationRun).where(GenerationRun.job_id == job_id)
        )
        runs = result.scalars().all()
        assert len(runs) == 0
