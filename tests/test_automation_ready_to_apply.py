"""Ready-to-apply endpoint tests (PR5, ARCH §11.2).

Tests GET /api/jobs/ready-to-apply returns artifact-ready jobs with
pipeline_status=RESUME_READY, artifact_ready_at set, user_status=NEW.
"""

import uuid
from datetime import datetime, timezone

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select

from apps.api.main import app
from core.db.models import Job, PipelineStatus, UserStatus
from core.db.session import get_sync_session
from core.dedup import compute_dedup_hash_from_raw, normalize_company, normalize_title


def _make_ready_to_apply_job(
    *,
    pipeline_status: str = PipelineStatus.RESUME_READY.value,
    user_status: str = UserStatus.NEW.value,
    artifact_ready_at=None,
) -> uuid.UUID:
    """Create a job that qualifies for ready-to-apply feed."""
    from core.db.models import Company

    unique = str(uuid.uuid4())[:8]
    company_name = f"ReadyApply_{unique}"
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
            source="greenhouse",
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
            description="Build APIs.",
            status="NEW",
            user_status=user_status,
            pipeline_status=pipeline_status,
            score_total=75.0,
            dedup_hash=dedup_hash,
            artifact_ready_at=artifact_ready_at or datetime.now(timezone.utc),
        )
        session.add(job)
        session.flush()
        return job.id


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def ready_job():
    """Create a job that appears in ready-to-apply feed."""
    return _make_ready_to_apply_job()


async def test_ready_to_apply_returns_paginated_structure(client):
    """GET /api/jobs/ready-to-apply returns items, total, page, per_page."""
    resp = await client.get("/api/jobs/ready-to-apply")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert isinstance(data["items"], list)
    assert data["page"] >= 1
    assert data["per_page"] >= 1


async def test_ready_to_apply_includes_artifact_ready_jobs(client, ready_job):
    """Ready-to-apply feed includes jobs with artifact_ready_at and RESUME_READY."""
    resp = await client.get("/api/jobs/ready-to-apply?per_page=100")
    assert resp.status_code == 200
    data = resp.json()
    ids = [i["id"] for i in data["items"]]
    assert str(ready_job) in ids


async def test_ready_to_apply_excludes_applied_jobs(client):
    """Jobs with user_status=APPLIED are not in ready-to-apply (they need NEW)."""
    from core.db.models import Company

    unique = str(uuid.uuid4())[:8]
    company_name = f"Applied_{unique}"
    dedup_hash = compute_dedup_hash_from_raw(
        company=company_name,
        title="Applied Job",
        location="Remote",
        apply_url=f"https://example.com/{unique}",
    )
    with get_sync_session() as session:
        company = Company(name=company_name)
        session.add(company)
        session.flush()
        job = Job(
            source="greenhouse",
            source_job_id=unique,
            title="Applied Job",
            raw_title="Applied Job",
            normalized_title=normalize_title("Applied Job"),
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
            description="Build APIs.",
            status="APPLIED",
            user_status=UserStatus.APPLIED.value,
            pipeline_status=PipelineStatus.RESUME_READY.value,
            score_total=75.0,
            dedup_hash=dedup_hash,
            artifact_ready_at=datetime.now(timezone.utc),
        )
        session.add(job)
        session.flush()
        applied_job_id = job.id

    resp = await client.get("/api/jobs/ready-to-apply?per_page=100")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert str(applied_job_id) not in ids
