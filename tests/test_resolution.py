"""Tests for discovery-to-canonical resolution (POST /api/jobs/{id}/resolve).

Requires: Postgres with migrations applied.
Run: alembic upgrade head && pytest tests/test_resolution.py
"""

import uuid

import httpx
import pytest
from httpx import ASGITransport
from unittest.mock import patch, MagicMock

from sqlalchemy import select

from apps.api.main import app
from core.connectors.base import CanonicalJobPayload, FetchResult, RawJobWithProvenance
from core.connectors.base import ProvenanceMetadata
from core.db.models import (
    Company,
    Job,
    JobAnalysis,
    JobResolutionAttempt,
    JobSourceRecord,
    PipelineStatus,
    ResolutionStatus,
    SourceRole,
)
from core.db.session import get_sync_session
from core.dedup import compute_dedup_hash_from_raw, normalize_company, normalize_title
from apps.worker.tasks.resolution import resolve_discovery_job
from apps.worker.tasks.score import score_jobs
from apps.worker.tasks.classify import classify_jobs
from apps.worker.tasks.ats_match import ats_match_resume


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _make_discovery_job(
    apply_url: str,
    *,
    resolution_status: str | None = ResolutionStatus.PENDING.value,
    source_role: str = SourceRole.DISCOVERY.value,
) -> uuid.UUID:
    """Create a discovery job. Returns job_id."""
    unique = str(uuid.uuid4())[:8]
    company_name = f"TestDiscovery_{unique}"
    dedup_hash = compute_dedup_hash_from_raw(
        company=company_name,
        title="Engineer",
        location="Remote",
        apply_url=apply_url or f"https://example.com/{unique}",
    )
    with get_sync_session() as session:
        company = Company(name=company_name)
        session.add(company)
        session.flush()
        job = Job(
            source="agg1",
            source_job_id=unique,
            source_role=source_role,
            source_confidence=0.6,
            resolution_status=resolution_status,
            title="Engineer",
            raw_title="Engineer",
            normalized_title=normalize_title("Engineer"),
            company_id=company.id,
            company_name_raw=company_name,
            raw_company=company_name,
            normalized_company=normalize_company(company_name),
            location="Remote",
            raw_location="Remote",
            normalized_location="remote",
            remote_flag=True,
            url=apply_url or "",
            apply_url=apply_url or None,
            description="Minimal",
            status="NEW",
            user_status="NEW",
            pipeline_status="INGESTED",
            score_total=0.0,
            dedup_hash=dedup_hash,
        )
        session.add(job)
        session.flush()
        return job.id


async def test_resolve_404(client):
    """POST /api/jobs/{id}/resolve returns 404 for non-existent job."""
    fake_id = uuid.uuid4()
    resp = await client.post(f"/api/jobs/{fake_id}/resolve")
    assert resp.status_code == 404


async def test_resolve_400_not_discovery(client):
    """POST /api/jobs/{id}/resolve returns 400 for non-discovery job."""
    job_id = _make_discovery_job(
        "https://boards.greenhouse.io/acme/jobs/123",
        source_role=SourceRole.CANONICAL.value,
    )
    resp = await client.post(f"/api/jobs/{job_id}/resolve")
    assert resp.status_code == 400
    assert "discovery" in resp.json().get("detail", "").lower()


async def test_resolve_200_already_resolved(client):
    """POST /api/jobs/{id}/resolve returns 200 with no-op when already resolved."""
    job_id = _make_discovery_job(
        "https://boards.greenhouse.io/acme/jobs/123",
        resolution_status=ResolutionStatus.RESOLVED_CANONICAL.value,
    )
    resp = await client.post(f"/api/jobs/{job_id}/resolve")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "already_resolved"
    assert data.get("task_id") is None


async def test_resolve_400_no_url(client):
    """POST /api/jobs/{id}/resolve returns 400 when job has no apply_url or url."""
    unique = str(uuid.uuid4())[:8]
    dedup_hash = compute_dedup_hash_from_raw(
        company=f"NoUrl_{unique}",
        title="Engineer",
        location="Remote",
        apply_url=f"https://example.com/{unique}",
    )
    with get_sync_session() as session:
        company = Company(name=f"NoUrl_{unique}")
        session.add(company)
        session.flush()
        job = Job(
            source="agg1",
            source_job_id=unique,
            source_role=SourceRole.DISCOVERY.value,
            resolution_status=ResolutionStatus.PENDING.value,
            title="Engineer",
            raw_title="Engineer",
            normalized_title="engineer",
            company_id=company.id,
            company_name_raw=company.name,
            raw_company=company.name,
            normalized_company=normalize_company(company.name),
            dedup_hash=dedup_hash,
            apply_url=None,
            url="",
            status="NEW",
            user_status="NEW",
            pipeline_status="INGESTED",
            score_total=0.0,
        )
        session.add(job)
        session.flush()
        job_id = job.id

    resp = await client.post(f"/api/jobs/{job_id}/resolve")
    assert resp.status_code == 400
    assert "url" in resp.json().get("detail", "").lower()


def test_resolve_task_unsupported_url():
    """resolve_discovery_job records attempt and returns unsupported for non-ATS URL."""
    job_id = _make_discovery_job("https://linkedin.com/jobs/view/12345")
    result = resolve_discovery_job(str(job_id))
    assert result["status"] == "unsupported"
    assert result.get("reason") == "url_not_greenhouse_lever_ashby"

    from sqlalchemy import select

    with get_sync_session() as session:
        result = session.execute(
            select(JobResolutionAttempt).where(JobResolutionAttempt.job_id == job_id)
        )
        attempts = result.scalars().all()
        assert len(attempts) == 1
        assert attempts[0].resolution_status == ResolutionStatus.FAILED.value
        assert attempts[0].failure_reason == "unsupported_url"


@patch("apps.worker.tasks.resolution.create_greenhouse_connector")
def test_resolve_task_success_mocked(mock_create_connector):
    """resolve_discovery_job enriches job when URL maps to Greenhouse and fetch succeeds."""
    # Use unique job id to avoid JobSourceRecord (source_name, external_id) collision across test runs
    import random
    unique_id = str(900000000 + random.randint(0, 99999999))
    job_id = _make_discovery_job(f"https://boards.greenhouse.io/acme/jobs/{unique_id}")

    mock_connector = MagicMock()
    mock_connector.normalize.return_value = CanonicalJobPayload(
        source_name="greenhouse",
        external_id=unique_id,
        title="Senior Backend Engineer",
        company="Acme Corp",
        location="San Francisco, CA",
        employment_type=None,
        description="Full job description from Greenhouse",
        apply_url=f"https://boards.greenhouse.io/acme/jobs/{unique_id}",
        source_url=f"https://boards.greenhouse.io/acme/jobs/{unique_id}",
        posted_at=None,
        raw_payload={"id": int(unique_id), "title": "Senior Backend Engineer"},
        normalized_title="senior backend engineer",
        normalized_company="acme corp",
        normalized_location="san francisco, ca",
    )
    mock_connector.fetch_raw_jobs.return_value = FetchResult(
        raw_jobs=[
            RawJobWithProvenance(
                raw_payload={"id": int(unique_id), "title": "Senior Backend Engineer"},
                provenance=ProvenanceMetadata(
                    fetch_timestamp="2024-01-01T00:00:00Z",
                    source_url="https://boards.greenhouse.io/acme/jobs",
                    connector_version="v1",
                ),
            )
        ],
        stats={"fetched": 1, "errors": 0},
        error=None,
    )
    mock_create_connector.return_value = mock_connector

    result = resolve_discovery_job(str(job_id))
    assert result["status"] == "resolved"
    assert result.get("canonical_source") == "greenhouse"
    assert result.get("canonical_external_id") == unique_id

    with get_sync_session() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.resolution_status == ResolutionStatus.RESOLVED_CANONICAL.value
        assert job.canonical_source_name == "greenhouse"
        assert job.canonical_external_id == unique_id
        assert job.description == "Full job description from Greenhouse"
        assert job.source_confidence == 1.0

        result = session.execute(
            select(JobResolutionAttempt).where(JobResolutionAttempt.job_id == job_id)
        )
        attempts = result.scalars().all()
        assert len(attempts) == 1
        assert attempts[0].resolution_status == ResolutionStatus.RESOLVED_CANONICAL.value
        assert attempts[0].confidence == 1.0

        result = session.execute(
            select(JobSourceRecord).where(JobSourceRecord.job_id == job_id)
        )
        sources = result.scalars().all()
        source_names = {s.source_name for s in sources}
        assert "greenhouse" in source_names


@patch("apps.worker.tasks.resolution.create_greenhouse_connector")
def test_resolved_job_past_ingested_gets_reprocessed(mock_create_connector):
    """Regression: a discovery job already past INGESTED (e.g. ATS_ANALYZED)
    is resolved to canonical data and then rescored/reclassified/re-ATS-analyzed
    with the enriched content."""
    import random

    unique_id = str(900000000 + random.randint(0, 99999999))

    # 1. Create a discovery job and push it through scoring/classify/ATS so it's
    #    past INGESTED (simulates a job that was already processed as discovery).
    job_id = _make_discovery_job(
        f"https://boards.greenhouse.io/acme/jobs/{unique_id}",
    )

    # Run the pipeline so the job reaches ATS_ANALYZED with its weak discovery data
    jids = [str(job_id)]
    score_jobs.apply(kwargs={"job_ids": jids})
    classify_jobs.apply(kwargs={"job_ids": jids})
    ats_match_resume.apply(kwargs={"job_ids": jids})

    with get_sync_session() as session:
        job = session.get(Job, job_id)
        assert job.pipeline_status == PipelineStatus.ATS_ANALYZED.value
        old_score = job.score_total
        old_description = job.description
        old_ats_score = job.ats_match_score

    # 2. Mock the canonical connector to return richer data
    canonical_description = (
        "We are hiring a Senior Backend Engineer to build scalable APIs. "
        "Python, FastAPI, AWS, PostgreSQL, Kubernetes, Docker, Redis, CI/CD. "
        "Remote-first fintech company."
    )
    mock_connector = MagicMock()
    mock_connector.normalize.return_value = CanonicalJobPayload(
        source_name="greenhouse",
        external_id=unique_id,
        title="Senior Backend Engineer",
        company="Acme Corp",
        location="Remote",
        employment_type=None,
        description=canonical_description,
        apply_url=f"https://boards.greenhouse.io/acme/jobs/{unique_id}",
        source_url=f"https://boards.greenhouse.io/acme/jobs/{unique_id}",
        posted_at=None,
        raw_payload={"id": int(unique_id), "title": "Senior Backend Engineer"},
        normalized_title="senior backend engineer",
        normalized_company="acme corp",
        normalized_location="remote",
    )
    mock_connector.fetch_raw_jobs.return_value = FetchResult(
        raw_jobs=[
            RawJobWithProvenance(
                raw_payload={"id": int(unique_id), "title": "Senior Backend Engineer"},
                provenance=ProvenanceMetadata(
                    fetch_timestamp="2024-01-01T00:00:00Z",
                    source_url="https://boards.greenhouse.io/acme/jobs",
                    connector_version="v1",
                ),
            )
        ],
        stats={"fetched": 1, "errors": 0},
        error=None,
    )
    mock_create_connector.return_value = mock_connector

    # 3. Resolve — this should reset pipeline_status to INGESTED
    result = resolve_discovery_job(str(job_id))
    assert result["status"] == "resolved"

    with get_sync_session() as session:
        job = session.get(Job, job_id)
        assert job.pipeline_status == PipelineStatus.INGESTED.value, (
            f"Expected INGESTED after resolution reset, got {job.pipeline_status}"
        )
        assert job.description == canonical_description

    # 4. Re-run the downstream chain (simulates what the Celery chain does)
    score_out = score_jobs.apply(kwargs={"job_ids": jids}).get()
    assert str(job_id) in score_out["job_ids"], (
        "Resolved job should be rescored (pipeline_status was reset to INGESTED)"
    )

    classify_out = classify_jobs.apply(kwargs={"job_ids": jids}).get()
    assert str(job_id) in classify_out["job_ids"], (
        "Resolved job should be reclassified"
    )

    ats_out = ats_match_resume.apply(kwargs={"job_ids": jids}).get()
    assert str(job_id) in ats_out["job_ids"], (
        "Resolved job should be re-ATS-analyzed"
    )

    # 5. Verify the job reached ATS_ANALYZED with updated canonical data
    with get_sync_session() as session:
        job = session.get(Job, job_id)
        assert job.pipeline_status == PipelineStatus.ATS_ANALYZED.value
        assert job.description == canonical_description
        assert job.resolution_status == ResolutionStatus.RESOLVED_CANONICAL.value
        assert job.source_confidence == 1.0

        # Score and ATS analysis should reflect the richer canonical description
        analysis = session.execute(
            select(JobAnalysis).where(JobAnalysis.job_id == job_id)
        ).scalar_one_or_none()
        assert analysis is not None
        assert analysis.ats_compatibility_score is not None
        assert analysis.matched_persona is not None
