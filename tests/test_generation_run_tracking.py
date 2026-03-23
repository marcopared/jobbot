"""Tests for GenerationRun tracking in generate_grounded_resume_task.

Verifies that both manual and auto-triggered generation runs correctly update
GenerationRun status, artifact_id, finished_at, and auto_generated_at.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from core.db.models import (
    Artifact,
    Company,
    GenerationRun,
    GenerationRunStatus,
    Job,
    JobAnalysis,
    PipelineStatus,
)
from core.db.session import get_sync_session
from core.dedup import compute_dedup_hash_from_raw, normalize_company, normalize_title


def _create_ats_analyzed_job() -> uuid.UUID:
    """Create a job at ATS_ANALYZED with analysis, return job_id."""
    unique = str(uuid.uuid4())[:8]
    company_name = f"GenRunTest_{unique}"
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
            pipeline_status=PipelineStatus.ATS_ANALYZED.value,
            score_total=75.0,
            dedup_hash=dedup_hash,
        )
        session.add(job)
        session.flush()
        analysis = JobAnalysis(
            job_id=job.id,
            total_score=75.0,
            matched_persona="BACKEND",
            persona_confidence=0.9,
            persona_rationale="Test",
            found_keywords=["python", "aws"],
            missing_keywords=["postgresql"],
            ats_compatibility_score=0.85,
        )
        session.add(analysis)
        session.flush()
        return job.id


def _create_generation_run(job_id: uuid.UUID, triggered_by: str) -> uuid.UUID:
    """Create a GenerationRun in queued state, return its id."""
    with get_sync_session() as session:
        run = GenerationRun(
            job_id=job_id,
            status=GenerationRunStatus.QUEUED.value,
            triggered_by=triggered_by,
        )
        session.add(run)
        session.flush()
        return run.id


def _create_artifact(job_id: uuid.UUID) -> uuid.UUID:
    """Create a minimal Artifact row and return its id."""
    with get_sync_session() as session:
        artifact = Artifact(
            job_id=job_id,
            kind="pdf",
            filename="test_resume.pdf",
            path="/tmp/test_resume.pdf",
        )
        session.add(artifact)
        session.flush()
        return artifact.id


@dataclass
class FakeArtifact:
    """Minimal artifact stand-in with a pre-loaded id (avoids detached session errors)."""
    id: uuid.UUID


@dataclass
class FakeResult:
    artifact: FakeArtifact | None
    status: str
    error: str | None = None


def test_manual_run_success_updates_generation_run():
    """Manual generation updates GenerationRun to success with artifact_id and finished_at."""
    job_id = _create_ats_analyzed_job()
    run_id = _create_generation_run(job_id, "manual")
    artifact_id = _create_artifact(job_id)

    with patch(
        "apps.worker.tasks.resume.generate_grounded_resume"
    ) as mock_gen:
        mock_gen.return_value = FakeResult(
            artifact=FakeArtifact(id=artifact_id), status="success"
        )
        from apps.worker.tasks.resume import generate_grounded_resume_task

        result = generate_grounded_resume_task(
            str(job_id),
            generation_run_id=str(run_id),
            triggered_by="manual",
        )

    assert result["status"] == "success"
    assert result["artifact_id"] == str(artifact_id)

    with get_sync_session() as session:
        run = session.get(GenerationRun, run_id)
        assert run.status == GenerationRunStatus.SUCCESS.value
        assert run.artifact_id == artifact_id
        assert run.finished_at is not None

        # Manual runs should NOT set auto_generated_at
        job = session.get(Job, job_id)
        assert job.auto_generated_at is None


def test_auto_run_success_sets_auto_generated_at():
    """Auto generation updates GenerationRun AND sets job.auto_generated_at."""
    job_id = _create_ats_analyzed_job()
    run_id = _create_generation_run(job_id, "auto")
    artifact_id = _create_artifact(job_id)

    with patch(
        "apps.worker.tasks.resume.generate_grounded_resume"
    ) as mock_gen:
        mock_gen.return_value = FakeResult(
            artifact=FakeArtifact(id=artifact_id), status="success"
        )
        from apps.worker.tasks.resume import generate_grounded_resume_task

        result = generate_grounded_resume_task(
            str(job_id),
            generation_run_id=str(run_id),
            triggered_by="auto",
        )

    assert result["status"] == "success"

    with get_sync_session() as session:
        run = session.get(GenerationRun, run_id)
        assert run.status == GenerationRunStatus.SUCCESS.value
        assert run.artifact_id == artifact_id
        assert run.finished_at is not None

        job = session.get(Job, job_id)
        assert job.auto_generated_at is not None


def test_manual_run_failure_updates_generation_run():
    """Failed manual generation updates GenerationRun to failed with failure_reason."""
    job_id = _create_ats_analyzed_job()
    run_id = _create_generation_run(job_id, "manual")

    with patch(
        "apps.worker.tasks.resume.generate_grounded_resume"
    ) as mock_gen:
        mock_gen.return_value = FakeResult(
            artifact=None,
            status="failed",
            error="Experience inventory not found",
        )
        from apps.worker.tasks.resume import generate_grounded_resume_task

        result = generate_grounded_resume_task(
            str(job_id),
            generation_run_id=str(run_id),
            triggered_by="manual",
        )

    assert result["status"] == "failed"
    assert result["error"] == "Experience inventory not found"

    with get_sync_session() as session:
        run = session.get(GenerationRun, run_id)
        assert run.status == GenerationRunStatus.FAILED.value
        assert run.failure_reason == "Experience inventory not found"
        assert run.finished_at is not None
