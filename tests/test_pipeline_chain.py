"""Pipeline chain tests: score -> classify -> ATS -> generation_gate for all ingestion paths.

JobSpy scrape, Greenhouse/canonical ingest, and discovery use the same post-ingestion chain.
These tests verify:
- INGESTED jobs reach CLASSIFIED and ATS_ANALYZED
- Score-threshold rejection is preserved (REJECTED jobs skip classification/ATS)
- Persona data exists for eligible jobs from both paths
- ats_match chains to evaluate_generation_gate; gate runs for all paths
- Full Celery chain (score->classify->ats->gate) executes end-to-end

Requires: Postgres with migrations applied (alembic upgrade head).
Run: pytest tests/test_pipeline_chain.py
"""

import uuid

import pytest

from core.dedup import compute_dedup_hash_from_raw, normalize_company, normalize_title
from core.db.models import Company, Job, JobAnalysis, PipelineStatus, ResolutionStatus, SourceRole
from core.db.session import get_sync_session

from apps.worker.tasks.ats_match import ats_match_resume
from apps.worker.tasks.classify import classify_jobs
from apps.worker.tasks.generation import evaluate_generation_gate
from apps.worker.tasks.score import score_jobs


def _make_ingested_job(
    source: str,
    title: str = "Senior Software Engineer",
    description: str = "Build APIs. Python, FastAPI, AWS, PostgreSQL. Fintech.",
    location: str = "Remote",
    remote_flag: bool = True,
    source_role: str | None = None,
    source_confidence: float | None = None,
    resolution_status: str | None = None,
) -> uuid.UUID:
    """Insert a Job with pipeline_status=INGESTED. Returns job_id."""
    unique = str(uuid.uuid4())[:8]
    company_name = f"TestCorp_{unique}"
    apply_url = f"https://example.com/jobs/{unique}"

    dedup_hash = compute_dedup_hash_from_raw(
        company=company_name,
        title=title,
        location=location,
        apply_url=apply_url,
    )

    with get_sync_session() as session:
        company = Company(name=company_name)
        session.add(company)
        session.flush()

        job_kw: dict = {
            "source": source,
            "source_job_id": unique,
            "title": title,
            "raw_title": title,
            "normalized_title": normalize_title(title),
            "company_id": company.id,
            "company_name_raw": company_name,
            "raw_company": company_name,
            "normalized_company": normalize_company(company_name),
            "location": location,
            "raw_location": location,
            "normalized_location": location.lower() if location else None,
            "remote_flag": remote_flag,
            "url": apply_url,
            "apply_url": apply_url,
            "description": description,
            "status": "NEW",
            "user_status": "NEW",
            "pipeline_status": PipelineStatus.INGESTED.value,
            "score_total": 0.0,
            "dedup_hash": dedup_hash,
        }
        if source_role is not None:
            job_kw["source_role"] = source_role
        if source_confidence is not None:
            job_kw["source_confidence"] = source_confidence
        if resolution_status is not None:
            job_kw["resolution_status"] = resolution_status
        job = Job(**job_kw)
        session.add(job)
        session.flush()
        job_id = job.id
    return job_id


def _get_job_state(job_id: uuid.UUID) -> dict | None:
    """Fetch job pipeline_status and score. Returns dict to avoid detached instance."""
    from sqlalchemy import select

    with get_sync_session() as session:
        row = session.execute(
            select(
                Job.pipeline_status,
                Job.score_total,
                Job.ats_match_score,
            ).where(Job.id == job_id)
        ).first()
        if not row:
            return None
        return {
            "pipeline_status": row.pipeline_status,
            "score_total": row.score_total,
            "ats_match_score": row.ats_match_score,
        }


def _get_analysis(job_id: uuid.UUID) -> dict | None:
    """Fetch job_analyses row for job."""
    from sqlalchemy import select

    with get_sync_session() as session:
        row = session.execute(
            select(JobAnalysis).where(JobAnalysis.job_id == job_id)
        ).scalar_one_or_none()
        return {
            "matched_persona": row.matched_persona,
            "ats_compatibility_score": row.ats_compatibility_score,
        } if row else None


def test_jobspy_ingested_job_reaches_classified_and_ats_analyzed():
    """JobSpy-created job (source=jobspy, source_role=discovery) flows through full chain to ATS_ANALYZED."""
    job_id = _make_ingested_job(
        source="jobspy",
        source_role=SourceRole.DISCOVERY.value,
        source_confidence=0.8,
        resolution_status=ResolutionStatus.PENDING.value,
    )
    job_ids = [str(job_id)]

    score_jobs.apply(kwargs={"job_ids": job_ids})
    state = _get_job_state(job_id)
    assert state is not None
    assert state["pipeline_status"] == PipelineStatus.SCORED.value, (
        f"Expected SCORED after score_jobs, got {state['pipeline_status']} (score={state['score_total']})"
    )

    classify_jobs.apply(kwargs={"job_ids": job_ids})
    state = _get_job_state(job_id)
    assert state is not None
    assert state["pipeline_status"] == PipelineStatus.CLASSIFIED.value

    analysis = _get_analysis(job_id)
    assert analysis is not None
    assert analysis["matched_persona"] in ("BACKEND", "PLATFORM_INFRA", "HYBRID")

    ats_match_resume.apply(kwargs={"job_ids": job_ids})
    state = _get_job_state(job_id)
    assert state is not None
    assert state["pipeline_status"] == PipelineStatus.ATS_ANALYZED.value

    analysis = _get_analysis(job_id)
    assert analysis is not None
    assert analysis.get("ats_compatibility_score") is not None


def test_greenhouse_ingested_job_reaches_classified_and_ats_analyzed():
    """Greenhouse-created job (source=greenhouse, INGESTED) flows through full chain to CLASSIFIED and ATS_ANALYZED."""
    job_id = _make_ingested_job(source="greenhouse")
    job_ids = [str(job_id)]

    score_jobs.apply(kwargs={"job_ids": job_ids})
    state = _get_job_state(job_id)
    assert state is not None
    assert state["pipeline_status"] == PipelineStatus.SCORED.value

    classify_jobs.apply(kwargs={"job_ids": job_ids})
    state = _get_job_state(job_id)
    assert state is not None
    assert state["pipeline_status"] == PipelineStatus.CLASSIFIED.value

    ats_match_resume.apply(kwargs={"job_ids": job_ids})
    state = _get_job_state(job_id)
    assert state is not None
    assert state["pipeline_status"] == PipelineStatus.ATS_ANALYZED.value


def test_score_threshold_rejection_preserved():
    """Low-scoring job stays REJECTED and never reaches classification or ATS."""
    job_id = _make_ingested_job(
        source="jobspy",
        title="Intern Software Engineer",
        description="Coffee fetching, data entry.",
        location="Unknown City",
        remote_flag=False,  # No remote -> location_score 40, total stays below 60
    )
    job_ids = [str(job_id)]

    score_jobs.apply(kwargs={"job_ids": job_ids})
    state = _get_job_state(job_id)
    assert state is not None
    assert state["pipeline_status"] == PipelineStatus.REJECTED.value

    # classify_jobs only processes SCORED; our job is REJECTED so it won't be touched
    classify_jobs.apply()
    state = _get_job_state(job_id)
    assert state["pipeline_status"] == PipelineStatus.REJECTED.value

    # ats_match_resume only processes CLASSIFIED when no job_ids; our job stays REJECTED
    ats_match_resume.apply()
    state = _get_job_state(job_id)
    assert state["pipeline_status"] == PipelineStatus.REJECTED.value


def test_ats_match_chains_to_evaluate_generation_gate():
    """ats_match returns job_ids; evaluate_generation_gate runs and respects gate (queued=0 when disabled)."""
    job_id = _make_ingested_job(source="greenhouse")
    job_ids = [str(job_id)]

    score_jobs.apply(kwargs={"job_ids": job_ids})
    classify_jobs.apply(kwargs={"job_ids": job_ids})
    out = ats_match_resume.apply(kwargs={"job_ids": job_ids}).get()
    assert "job_ids" in out
    assert str(job_id) in out["job_ids"]

    gate_out = evaluate_generation_gate.apply(kwargs={"chain_output": out}).get()
    assert "evaluated" in gate_out
    assert "queued" in gate_out
    assert gate_out["evaluated"] >= 1
    # With ENABLE_AUTO_RESUME_GENERATION=false (default), no jobs queued
    assert gate_out["queued"] == 0


def test_full_chain_as_scrape_runs_end_to_end():
    """Full Celery chain score->classify->ats->gate runs when invoked like scrape (no job_ids to score)."""
    job_id = _make_ingested_job(
        source="jobspy",
        source_role=SourceRole.DISCOVERY.value,
        source_confidence=0.8,
        resolution_status=ResolutionStatus.PENDING.value,
    )
    chain = (
        score_jobs.s()
        | classify_jobs.s()
        | ats_match_resume.s()
        | evaluate_generation_gate.s()
    )
    result = chain.apply().get()
    assert "evaluated" in result
    assert "queued" in result
    assert result["evaluated"] >= 1, "Gate should receive at least our job from chain"
    state = _get_job_state(job_id)
    assert state is not None
    assert state["pipeline_status"] == PipelineStatus.ATS_ANALYZED.value
