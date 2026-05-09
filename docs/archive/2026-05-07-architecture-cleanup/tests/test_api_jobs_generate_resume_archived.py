"""Archived historical tests for POST /api/jobs/{id}/generate-resume.

The custom resume generation endpoint is intentionally not part of the current
local-first MVP. These tests are preserved as historical reference for a future
custom-resume-generation revival, but they should not run in the active suite.
"""

# Original snippets from tests/test_api_jobs.py follow. They are intentionally
# archived outside the active tests/ tree.


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

    detail_resp = await client.get(f"/api/jobs/{job_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["latest_generation_run"]["id"] == data["generation_run_id"]
    assert detail["latest_generation_run"]["status"] == "queued"
    assert detail["latest_generation_run"]["triggered_by"] == "manual"
    assert detail["latest_generation_run"]["artifact_id"] is None




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
