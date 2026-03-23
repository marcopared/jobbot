"""Regression tests for URL-based company canonicalization."""

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from apps.worker.tasks.ingest import ingest_url
from apps.worker.tasks.resolution import resolve_discovery_job
from core.connectors.ashby import create_ashby_connector
from core.connectors.base import FetchResult, ProvenanceMetadata, RawJobWithProvenance
from core.connectors.greenhouse import create_greenhouse_connector
from core.connectors.lever import create_lever_connector
from core.db.models import (
    Company,
    Job,
    JobSourceRecord,
    ResolutionStatus,
    ScrapeRun,
    ScrapeRunStatus,
    SourceRole,
)
from core.db.session import get_sync_session
from core.dedup import compute_dedup_hash_from_raw, normalize_company, normalize_title


class _FakeSig:
    """Minimal Celery signature stand-in for chain construction in tests."""

    def __or__(self, other):
        return self

    def delay(self):
        return None


def _patch_pipeline_chain(monkeypatch, module_path: str) -> None:
    """Replace downstream Celery tasks with inert signatures."""
    fake_task = MagicMock()
    fake_task.s = MagicMock(return_value=_FakeSig())
    monkeypatch.setattr(f"{module_path}.score_jobs", fake_task)
    monkeypatch.setattr(f"{module_path}.classify_jobs", fake_task)
    monkeypatch.setattr(f"{module_path}.ats_match_resume", fake_task)
    monkeypatch.setattr(f"{module_path}.evaluate_generation_gate", fake_task)


def _create_running_run(source: str) -> str:
    """Insert a RUNNING scrape run and return its id."""
    with get_sync_session() as session:
        run = ScrapeRun(
            source=source,
            status=ScrapeRunStatus.RUNNING.value,
            params_json={},
        )
        session.add(run)
        session.commit()
        return str(run.id)


def _make_discovery_job(apply_url: str) -> uuid.UUID:
    """Create a discovery job to exercise resolution."""
    unique = str(uuid.uuid4())[:8]
    company_name = f"Discovery_{unique}"
    dedup_hash = compute_dedup_hash_from_raw(
        company=company_name,
        title="Engineer",
        location="Remote",
        apply_url=apply_url,
    )
    with get_sync_session() as session:
        company = Company(name=company_name)
        session.add(company)
        session.flush()
        job = Job(
            source="agg1",
            source_job_id=unique,
            source_role=SourceRole.DISCOVERY.value,
            source_confidence=0.6,
            resolution_status=ResolutionStatus.PENDING.value,
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
            url=apply_url,
            apply_url=apply_url,
            description="Discovery payload",
            status="NEW",
            user_status="NEW",
            pipeline_status="INGESTED",
            score_total=0.0,
            dedup_hash=dedup_hash,
        )
        session.add(job)
        session.commit()
        return job.id


def _fetch_result(raw_payload: dict, source_url: str) -> FetchResult:
    """Wrap a raw payload in the connector fetch result shape."""
    return FetchResult(
        raw_jobs=[
            RawJobWithProvenance(
                raw_payload=raw_payload,
                provenance=ProvenanceMetadata(
                    fetch_timestamp="2024-01-01T00:00:00Z",
                    source_url=source_url,
                    connector_version="test",
                ),
            )
        ],
        stats={"fetched": 1, "errors": 0},
        error=None,
    )


@pytest.mark.parametrize(
    "provider,url,connector_factory,patch_target,raw_payload,expected_company,expected_metadata",
    [
        (
            "greenhouse",
            "https://boards.greenhouse.io/acme/jobs/12345",
            lambda: create_greenhouse_connector(board_token="acme", company_name=None),
            "apps.worker.tasks.ingest.create_greenhouse_connector",
            {
                "id": 12345,
                "title": "Backend Engineer",
                "company_name": "Acme Corporation",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
                "location": {"name": "Remote"},
                "content": "Build APIs",
            },
            "Acme Corporation",
            {"board_token": "acme"},
        ),
        (
            "lever",
            "https://jobs.lever.co/acme/lever-123",
            lambda: create_lever_connector(client_name="acme", company_name=None),
            "apps.worker.tasks.ingest.create_lever_connector",
            {
                "id": "lever-123",
                "text": "Backend Engineer",
                "company": "Acme Corporation",
                "hostedUrl": "https://jobs.lever.co/acme/lever-123",
                "applyUrl": "https://jobs.lever.co/acme/lever-123/apply",
                "descriptionPlain": "Build APIs",
            },
            "Acme Corporation",
            {"client_name": "acme"},
        ),
        (
            "ashby",
            "https://jobs.ashbyhq.com/acme/platform-engineer",
            lambda: create_ashby_connector(job_board_name="acme", company_name=None),
            "apps.worker.tasks.ingest.create_ashby_connector",
            "raw_payload",
            "Acme Corporation",
            {"job_board_name": "acme"},
        ),
    ],
)
def test_ingest_url_uses_payload_company_not_slug(
    monkeypatch,
    provider,
    url,
    connector_factory,
    patch_target,
    raw_payload,
    expected_company,
    expected_metadata,
):
    """URL ingest keeps provider slugs in metadata instead of canonical company."""
    if raw_payload == "raw_payload":
        raw_payload = {
            "title": "Backend Engineer",
            "companyName": "Acme Corporation",
            "jobUrl": "https://jobs.ashbyhq.com/acme/platform-engineer",
            "applyUrl": "https://jobs.ashbyhq.com/acme/platform-engineer/apply",
            "descriptionPlain": "Build APIs",
        }

    run_id = _create_running_run("url_ingest")
    connector = connector_factory()
    connector.fetch_raw_jobs = MagicMock(
        return_value=_fetch_result(raw_payload, source_url=url.rsplit("/", 1)[0])
    )
    _patch_pipeline_chain(monkeypatch, "apps.worker.tasks.ingest")
    monkeypatch.setattr("apps.worker.tasks.ingest.settings.url_ingest_enabled", True)
    monkeypatch.setattr(patch_target, lambda **kwargs: connector)

    result = ingest_url(run_id=run_id, url=url)

    assert result["status"] == "SUCCESS"

    with get_sync_session() as session:
        job = session.execute(select(Job).where(Job.apply_url == connector.normalize(raw_payload).apply_url)).scalar_one()
        assert job.company_name_raw == expected_company
        assert job.raw_company == expected_company
        assert job.company_name_raw.lower() != "acme"
        assert job.source_role == SourceRole.URL_INGEST.value

        source = session.execute(
            select(JobSourceRecord).where(
                JobSourceRecord.job_id == job.id,
                JobSourceRecord.source_name == provider,
            )
        ).scalar_one()
        assert source.provenance_metadata["provider_metadata"] == expected_metadata


@pytest.mark.parametrize(
    "provider,url,connector_factory,patch_target,raw_payload,expected_company,expected_metadata",
    [
        (
            "greenhouse",
            "https://boards.greenhouse.io/acme/jobs/22345",
            lambda: create_greenhouse_connector(board_token="acme", company_name=None),
            "apps.worker.tasks.resolution.create_greenhouse_connector",
            {
                "id": 22345,
                "title": "Backend Engineer",
                "company_name": "Acme Corporation",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/22345",
                "location": {"name": "Remote"},
                "content": "Build APIs",
            },
            "Acme Corporation",
            {"board_token": "acme"},
        ),
        (
            "lever",
            "https://jobs.lever.co/acme/lever-223",
            lambda: create_lever_connector(client_name="acme", company_name=None),
            "apps.worker.tasks.resolution.create_lever_connector",
            {
                "id": "lever-223",
                "text": "Backend Engineer",
                "company": "Acme Corporation",
                "hostedUrl": "https://jobs.lever.co/acme/lever-223",
                "applyUrl": "https://jobs.lever.co/acme/lever-223/apply",
                "descriptionPlain": "Build APIs",
            },
            "Acme Corporation",
            {"client_name": "acme"},
        ),
        (
            "ashby",
            "https://jobs.ashbyhq.com/acme/platform-engineer-2",
            lambda: create_ashby_connector(job_board_name="acme", company_name=None),
            "apps.worker.tasks.resolution.create_ashby_connector",
            {
                "title": "Backend Engineer",
                "companyName": "Acme Corporation",
                "jobUrl": "https://jobs.ashbyhq.com/acme/platform-engineer-2",
                "applyUrl": "https://jobs.ashbyhq.com/acme/platform-engineer-2/apply",
                "descriptionPlain": "Build APIs",
            },
            "Acme Corporation",
            {"job_board_name": "acme"},
        ),
    ],
)
def test_resolution_uses_payload_company_not_slug(
    monkeypatch,
    provider,
    url,
    connector_factory,
    patch_target,
    raw_payload,
    expected_company,
    expected_metadata,
):
    """Resolution keeps provider slugs in metadata instead of canonical company."""
    job_id = _make_discovery_job(url)
    connector = connector_factory()
    connector.fetch_raw_jobs = MagicMock(
        return_value=_fetch_result(raw_payload, source_url=url.rsplit("/", 1)[0])
    )
    _patch_pipeline_chain(monkeypatch, "apps.worker.tasks.resolution")
    monkeypatch.setattr(patch_target, lambda **kwargs: connector)

    result = resolve_discovery_job(str(job_id))

    assert result["status"] == "resolved"

    with get_sync_session() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.company_name_raw == expected_company
        assert job.raw_company == expected_company
        assert job.company_name_raw.lower() != "acme"
        assert job.resolution_status == ResolutionStatus.RESOLVED_CANONICAL.value

        source = session.execute(
            select(JobSourceRecord).where(
                JobSourceRecord.job_id == job.id,
                JobSourceRecord.source_name == provider,
            )
        ).scalar_one()
        assert source.provenance_metadata["provider_metadata"] == expected_metadata
