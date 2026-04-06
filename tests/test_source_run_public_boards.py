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
from core.ingestion.sources.public_boards.builtin_nyc import BuiltInNYCSourceAdapter
from core.ingestion.sources.public_boards.common import UnsupportedPublicBoardSourceAdapter
from core.ingestion.sources.public_boards.startupjobs_nyc import StartupJobsNYCSourceAdapter
from core.ingestion.sources.public_boards.welcome_to_the_jungle import (
    WelcomeToTheJungleSourceAdapter,
)

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
    if source_name == "startupjobs_nyc":
        listing_url = "https://startupjobs.nyc/"
        detail_url = "https://startupjobs.nyc/jobs/openai-manager-solutions-engineering"
        fetchers.enqueue(
            mode="simple",
            url=listing_url,
            result=FakeResponse(
                text=fixture_text("startupjobs_nyc", "listing.html"),
                headers={"content-type": "text/html"},
                url=listing_url,
            ),
        )
        fetchers.enqueue(
            mode="simple",
            url=detail_url,
            result=FakeResponse(
                text=fixture_text("startupjobs_nyc", "detail.html"),
                headers={"content-type": "text/html"},
                url=detail_url,
            ),
        )
        return StartupJobsNYCSourceAdapter(backend=ScraplingFetchBackend(fetchers_module=fetchers))
    if source_name == "builtin_nyc":
        listing_url = "https://www.builtinnyc.com/jobs"
        detail_url = "https://www.builtinnyc.com/job/vp-customer-success/8956308"
        fetchers.enqueue(
            mode="simple",
            url=listing_url,
            result=FakeResponse(
                text=fixture_text("builtin_nyc", "listing.html"),
                headers={"content-type": "text/html"},
                url=listing_url,
            ),
        )
        fetchers.enqueue(
            mode="simple",
            url=detail_url,
            result=FakeResponse(
                text=fixture_text("builtin_nyc", "detail.html"),
                headers={"content-type": "text/html"},
                url=detail_url,
            ),
        )
        return BuiltInNYCSourceAdapter(backend=ScraplingFetchBackend(fetchers_module=fetchers))

    listing_url = "https://www.welcometothejungle.com/en/jobs"
    detail_url = "https://www.welcometothejungle.com/en/companies/maki/jobs/digital-marketing-manager_new-york"
    fetchers.enqueue(
        mode="simple",
        url=listing_url,
        result=FakeResponse(
            text=fixture_text("wttj", "listing.html"),
            headers={"content-type": "text/html"},
            url=listing_url,
        ),
    )
    fetchers.enqueue(
        mode="simple",
        url=detail_url,
        result=FakeResponse(
            text=fixture_text("wttj", "detail.html"),
            headers={"content-type": "text/html"},
            url=detail_url,
        ),
    )
    return WelcomeToTheJungleSourceAdapter(backend=ScraplingFetchBackend(fetchers_module=fetchers))


@pytest.mark.parametrize(
    "source_name",
    ["startupjobs_nyc", "builtin_nyc", "welcome_to_the_jungle"],
)
def test_public_board_run_persists_jobs_and_keeps_pipeline_compatible(monkeypatch, source_name):
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


def test_public_board_run_skips_when_source_flag_disabled():
    from apps.worker.tasks import discovery as discovery_module

    run_id = _create_running_discovery_run("startupjobs_nyc")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(discovery_module.settings, "startupjobs_nyc_enabled", False)
        result = run_public_board_source.run(
            run_id=run_id,
            source_name="startupjobs_nyc",
            max_results=1,
        )

    assert result["status"] == "skipped"
    assert result["reason"] == "STARTUPJOBS_NYC_ENABLED=false"

    with get_sync_session() as session:
        run = session.get(ScrapeRun, uuid.UUID(run_id))
        assert run is not None
        assert run.status == ScrapeRunStatus.SKIPPED.value
        assert run.items_json == []


def test_public_board_run_fails_durably_when_adapter_is_unsupported(monkeypatch):
    from apps.worker.tasks import discovery as discovery_module

    run_id = _create_running_discovery_run("trueup")
    adapter = UnsupportedPublicBoardSourceAdapter(
        source_name="trueup",
        reason="Source adapter is registered but currently unsupported.",
    )

    monkeypatch.setattr(discovery_module.settings, "trueup_enabled", True)
    monkeypatch.setattr(discovery_module.source_registry, "create", lambda name: adapter)

    result = run_public_board_source.run(
        run_id=run_id,
        source_name="trueup",
        max_results=1,
    )

    assert result["status"] == "FAILED"
    assert "unsupported" in result["error"].lower()

    with get_sync_session() as session:
        run = session.get(ScrapeRun, uuid.UUID(run_id))
        assert run is not None
        assert run.status == ScrapeRunStatus.FAILED.value
        assert run.items_json == []
        assert "unsupported" in (run.error_text or "").lower()
