from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import delete, select

from apps.worker.tasks.ats_match import ats_match_resume
from apps.worker.tasks.classify import classify_jobs
from apps.worker.tasks.discovery import run_public_board_source
from apps.worker.tasks.generation import evaluate_generation_gate
from apps.worker.tasks.score import score_jobs
from core.db.models import (
    Job,
    JobAnalysis,
    JobSourceRecord,
    PipelineStatus,
    ResolutionStatus,
    ScrapeRun,
    ScrapeRunStatus,
    SourceRole,
)
from core.db.session import get_sync_session
from core.ingestion.backends.scrapling_backend import ScraplingFetchBackend
from core.ingestion.sources.portfolio_boards.greycroft import GreycroftSourceAdapter
from core.ingestion.sources.portfolio_boards.primary_vc import PrimaryVCSourceAdapter
from core.ingestion.sources.portfolio_boards.technyc import TechNYCSourceAdapter
from core.ingestion.sources.portfolio_boards.usv import USVSourceAdapter

from tests.public_board_test_support import FakeFetchersModule, FakeResponse, fixture_text


class _DummySig:
    def __init__(self) -> None:
        self.delay_called = False

    def __or__(self, other):
        return self

    def delay(self):
        self.delay_called = True
        return None


def _create_running_discovery_run(source: str) -> str:
    with get_sync_session() as session:
        run = ScrapeRun(
            source=source,
            status=ScrapeRunStatus.RUNNING.value,
            params_json={"source": source},
        )
        session.add(run)
        session.flush()
        return str(run.id)


def _clear_source_state(source: str) -> None:
    with get_sync_session() as session:
        job_ids = session.execute(select(Job.id).where(Job.source == source)).scalars().all()
        if job_ids:
            session.execute(delete(JobAnalysis).where(JobAnalysis.job_id.in_(job_ids)))
            session.execute(delete(JobSourceRecord).where(JobSourceRecord.job_id.in_(job_ids)))
            session.execute(delete(Job).where(Job.id.in_(job_ids)))
        session.execute(delete(ScrapeRun).where(ScrapeRun.source == source))
        session.commit()


def _build_adapter(source_name: str):
    fetchers = FakeFetchersModule()
    if source_name == "technyc":
        listing_url = "https://jobs.technyc.org/jobs"
        detail_url = (
            "https://jobs.technyc.org/companies/cassidy-2-7f40bb2f-9d0a-49e4-ad1e-ca7f8498ccff/"
            "jobs/73294014-ai-solutions-consultant"
        )
        fetchers.enqueue(
            mode="simple",
            url=listing_url,
            result=FakeResponse(
                text=fixture_text("technyc", "listing.html"),
                headers={"content-type": "text/html"},
                url=listing_url,
            ),
        )
        fetchers.enqueue(
            mode="simple",
            url=detail_url,
            result=FakeResponse(
                text=fixture_text("technyc", "detail.html"),
                headers={"content-type": "text/html"},
                url=detail_url,
            ),
        )
        return TechNYCSourceAdapter(backend=ScraplingFetchBackend(fetchers_module=fetchers))

    if source_name == "primary_vc":
        listing_url = "https://jobs.primary.vc/jobs"
        detail_url = (
            "https://jobs.primary.vc/companies/inspiren-2/"
            "jobs/73287563-principal-systems-pm-perception-hardware-platform"
        )
        fetchers.enqueue(
            mode="simple",
            url=listing_url,
            result=FakeResponse(
                text=fixture_text("primary_vc", "listing.html"),
                headers={"content-type": "text/html"},
                url=listing_url,
            ),
        )
        fetchers.enqueue(
            mode="simple",
            url=detail_url,
            result=FakeResponse(
                text=fixture_text("primary_vc", "detail.html"),
                headers={"content-type": "text/html"},
                url=detail_url,
            ),
        )
        return PrimaryVCSourceAdapter(backend=ScraplingFetchBackend(fetchers_module=fetchers))

    if source_name == "greycroft":
        listing_url = "https://jobs.greycroft.com/jobs"
        detail_url = (
            "https://jobs.greycroft.com/companies/narmi-2/"
            "jobs/73299386-software-engineer-i-implementations"
        )
        fetchers.enqueue(
            mode="simple",
            url=listing_url,
            result=FakeResponse(
                text=fixture_text("greycroft", "listing.html"),
                headers={"content-type": "text/html"},
                url=listing_url,
            ),
        )
        fetchers.enqueue(
            mode="simple",
            url=detail_url,
            result=FakeResponse(
                text=fixture_text("greycroft", "detail.html"),
                headers={"content-type": "text/html"},
                url=detail_url,
            ),
        )
        return GreycroftSourceAdapter(backend=ScraplingFetchBackend(fetchers_module=fetchers))

    search_url = "https://jobs.usv.com/api-boards/search-jobs"
    fetchers.enqueue(
        mode="simple",
        url=search_url,
        result=FakeResponse(
            text=fixture_text("usv", "search_jobs.json"),
            headers={"content-type": "application/json"},
            url=search_url,
        ),
    )
    return USVSourceAdapter(backend=ScraplingFetchBackend(fetchers_module=fetchers))


@pytest.mark.parametrize(
    "source_name",
    ["technyc", "primary_vc", "greycroft", "usv"],
)
def test_portfolio_board_run_persists_jobs_and_keeps_pipeline_compatible(monkeypatch, source_name):
    _clear_source_state(source_name)
    run_id = _create_running_discovery_run(source_name)
    adapter = _build_adapter(source_name)

    from apps.worker.tasks import discovery as discovery_module

    monkeypatch.setattr(discovery_module.source_registry, "create", lambda name: adapter)
    chain_sig = _DummySig()
    monkeypatch.setattr(discovery_module.score_jobs, "s", MagicMock(return_value=chain_sig))
    monkeypatch.setattr(discovery_module.classify_jobs, "s", MagicMock(return_value=_DummySig()))
    monkeypatch.setattr(discovery_module.ats_match_resume, "s", MagicMock(return_value=_DummySig()))
    monkeypatch.setattr(discovery_module.evaluate_generation_gate, "s", MagicMock(return_value=_DummySig()))

    result = run_public_board_source.run(run_id=run_id, source_name=source_name, max_results=1)

    assert result["status"] == "SUCCESS"
    assert result["stats"]["inserted"] == 1
    assert chain_sig.delay_called is True

    with get_sync_session() as session:
        run = session.get(ScrapeRun, uuid.UUID(run_id))
        assert run is not None
        assert run.status == ScrapeRunStatus.SUCCESS.value
        assert run.items_json and run.items_json[0]["source"] == source_name
        assert run.items_json[0]["outcome"] == "inserted"

        job = session.execute(
            select(Job).where(Job.source == source_name).order_by(Job.created_at.desc())
        ).scalars().first()
        assert job is not None
        assert job.source_role == SourceRole.DISCOVERY.value
        assert job.resolution_status == ResolutionStatus.PENDING.value
        assert job.pipeline_status == PipelineStatus.INGESTED.value
        assert job.source_payload_json is not None

        source_row = session.execute(
            select(JobSourceRecord).where(
                JobSourceRecord.source_name == source_name,
                JobSourceRecord.external_id == job.source_job_id,
            )
        ).scalars().first()
        assert source_row is not None
        assert source_row.external_id == job.source_job_id

        job_id = str(job.id)

    with get_sync_session() as session:
        job = session.get(Job, uuid.UUID(job_id))
        assert job is not None
        job.description = (
            "Senior platform engineering role building Python APIs, FastAPI services, AWS infrastructure, "
            "PostgreSQL systems, and enterprise customer integrations."
        )
        job.location = "Remote"
        job.raw_location = "Remote"
        job.normalized_location = "remote"
        job.remote_flag = True
        session.commit()

    score_jobs.apply(kwargs={"job_ids": [job_id]})
    classify_jobs.apply(kwargs={"job_ids": [job_id]})
    ats_output = ats_match_resume.apply(kwargs={"job_ids": [job_id]}).get()
    gate_output = evaluate_generation_gate.apply(kwargs={"chain_output": ats_output}).get()

    assert gate_output["evaluated"] >= 1

    with get_sync_session() as session:
        job = session.get(Job, uuid.UUID(job_id))
        assert job is not None
        assert job.pipeline_status == PipelineStatus.ATS_ANALYZED.value

