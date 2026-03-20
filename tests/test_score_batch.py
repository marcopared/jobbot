"""Regression test: score_jobs must upsert a JobAnalysis row for every job in the batch.

Prior bug: session.execute(stmt_ja) was outside the loop, so only the last job
received a job_analyses row while all jobs got Job.score_total updated.

Requires: Postgres with migrations applied (alembic upgrade head).
Run: pytest tests/test_score_batch.py
"""

import uuid

import pytest
from sqlalchemy import select

from core.dedup import compute_dedup_hash_from_raw, normalize_company, normalize_title
from core.db.models import Company, Job, JobAnalysis, PipelineStatus
from core.db.session import get_sync_session

from apps.worker.tasks.score import score_jobs


def _make_ingested_job(
    title: str = "Senior Software Engineer",
    description: str = "Build APIs. Python, FastAPI, AWS, PostgreSQL. Fintech.",
    location: str = "Remote",
    remote_flag: bool = True,
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

        job = Job(
            source="test",
            source_job_id=unique,
            title=title,
            raw_title=title,
            normalized_title=normalize_title(title),
            company_id=company.id,
            company_name_raw=company_name,
            raw_company=company_name,
            normalized_company=normalize_company(company_name),
            location=location,
            raw_location=location,
            normalized_location=location.lower() if location else None,
            remote_flag=remote_flag,
            url=apply_url,
            apply_url=apply_url,
            description=description,
            status="NEW",
            user_status="NEW",
            pipeline_status=PipelineStatus.INGESTED.value,
            score_total=0.0,
            dedup_hash=dedup_hash,
        )
        session.add(job)
        session.flush()
        job_id = job.id
    return job_id


def _get_job_analysis(job_id: uuid.UUID) -> dict | None:
    with get_sync_session() as session:
        row = session.execute(
            select(JobAnalysis).where(JobAnalysis.job_id == job_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "total_score": row.total_score,
            "seniority_score": row.seniority_score,
            "tech_stack_score": row.tech_stack_score,
            "location_score": row.location_score,
        }


def _get_job(job_id: uuid.UUID) -> dict:
    with get_sync_session() as session:
        row = session.execute(
            select(Job.pipeline_status, Job.score_total, Job.score_breakdown_json)
            .where(Job.id == job_id)
        ).first()
        return {
            "pipeline_status": row.pipeline_status,
            "score_total": row.score_total,
            "score_breakdown_json": row.score_breakdown_json,
        }


class TestScoreBatchJobAnalysis:
    """Every scored job must get its own JobAnalysis row."""

    def test_all_jobs_get_job_analysis_rows(self):
        """Regression: score_jobs with multiple jobs must upsert JobAnalysis for each."""
        # Create two high-scoring jobs that should both PASS
        job_id_1 = _make_ingested_job(
            title="Senior Software Engineer",
            description="Python, FastAPI, AWS, PostgreSQL. Fintech payments.",
        )
        job_id_2 = _make_ingested_job(
            title="Senior Backend Engineer",
            description="Go, Kubernetes, AWS. Banking platform.",
        )

        result = score_jobs([str(job_id_1), str(job_id_2)])

        # Both jobs must have JobAnalysis rows
        ja_1 = _get_job_analysis(job_id_1)
        ja_2 = _get_job_analysis(job_id_2)

        assert ja_1 is not None, f"Job {job_id_1} missing JobAnalysis row"
        assert ja_2 is not None, f"Job {job_id_2} missing JobAnalysis row"

        # total_score on JobAnalysis must match Job.score_total
        job_1 = _get_job(job_id_1)
        job_2 = _get_job(job_id_2)

        assert ja_1["total_score"] == job_1["score_total"]
        assert ja_2["total_score"] == job_2["score_total"]

    def test_scored_jobs_get_scored_status(self):
        """High-signal jobs should reach SCORED status."""
        job_id = _make_ingested_job(
            title="Senior Software Engineer",
            description="Fintech payments. Python, FastAPI, AWS, PostgreSQL.",
            location="Remote",
            remote_flag=True,
        )
        score_jobs([str(job_id)])

        job = _get_job(job_id)
        assert job["pipeline_status"] == PipelineStatus.SCORED.value
        assert job["score_total"] > 0

    def test_rejected_job_gets_job_analysis_row(self):
        """Even rejected jobs must have a JobAnalysis row (score is canonical there)."""
        job_id = _make_ingested_job(
            title="Intern Coffee Runner",
            description="Fetch coffee. No engineering.",
            location="Unknown City",
            remote_flag=False,
        )
        score_jobs([str(job_id)])

        job = _get_job(job_id)
        assert job["pipeline_status"] == PipelineStatus.REJECTED.value

        ja = _get_job_analysis(job_id)
        assert ja is not None, "Rejected job must still have a JobAnalysis row"
        assert ja["total_score"] == job["score_total"]

    def test_mixed_pass_and_reject_batch(self):
        """Batch with both pass and reject jobs: all get JobAnalysis rows."""
        high_id = _make_ingested_job(
            title="Senior Software Engineer",
            description="Fintech payments. Python, FastAPI, AWS.",
            location="Remote",
            remote_flag=True,
        )
        low_id = _make_ingested_job(
            title="Intern Data Entry",
            description="Filing papers.",
            location="Unknown",
            remote_flag=False,
        )

        result = score_jobs([str(high_id), str(low_id)])

        high_job = _get_job(high_id)
        low_job = _get_job(low_id)

        # Pipeline status assertions
        assert high_job["pipeline_status"] == PipelineStatus.SCORED.value
        assert low_job["pipeline_status"] == PipelineStatus.REJECTED.value

        # Both must have JobAnalysis rows
        ja_high = _get_job_analysis(high_id)
        ja_low = _get_job_analysis(low_id)

        assert ja_high is not None, "Scored job missing JobAnalysis"
        assert ja_low is not None, "Rejected job missing JobAnalysis"

        # Scores must be synchronized
        assert ja_high["total_score"] == high_job["score_total"]
        assert ja_low["total_score"] == low_job["score_total"]
