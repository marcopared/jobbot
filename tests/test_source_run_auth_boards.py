from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import delete, select

from apps.worker.tasks.ats_match import ats_match_resume
from apps.worker.tasks.classify import classify_jobs
from apps.worker.tasks.discovery import run_auth_board_source
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
from core.ingestion.backends.bb_browser_backend import BbBrowserSessionBackend
from core.ingestion.backends.bb_browser_client import BbBrowserPageCapture
from core.ingestion.sources.auth_boards.linkedin_jobs import LinkedInJobsSourceAdapter
from core.ingestion.sources.auth_boards.wellfound import WellfoundSourceAdapter
from core.ingestion.sources.auth_boards.yc_jobs import YCJobsSourceAdapter

from tests.bb_browser_test_support import FakeBbBrowserClient, fixture_text


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
    if source_name == "linkedin_jobs":
        listing_url = "https://www.linkedin.com/jobs/search/"
        detail_url = "https://www.linkedin.com/jobs/view/li-123/"
        captures = {
            listing_url: BbBrowserPageCapture(
                requested_url=listing_url,
                final_url=listing_url,
                status_code=200,
                html=fixture_text("linkedin_jobs", "listing.html"),
                content_type="text/html",
                session_name="linkedin-session",
            ),
            detail_url: BbBrowserPageCapture(
                requested_url=detail_url,
                final_url=detail_url,
                status_code=200,
                html=fixture_text("linkedin_jobs", "detail.html"),
                content_type="text/html",
                session_name="linkedin-session",
            ),
        }
        return LinkedInJobsSourceAdapter(
            backend=BbBrowserSessionBackend(client=FakeBbBrowserClient(captures))
        )

    if source_name == "wellfound":
        listing_url = "https://wellfound.com/jobs"
        detail_url = "https://wellfound.com/company/acme-ai/jobs/wf-456-senior-platform-engineer"
        captures = {
            listing_url: BbBrowserPageCapture(
                requested_url=listing_url,
                final_url=listing_url,
                status_code=200,
                html=fixture_text("wellfound", "listing.html"),
                content_type="text/html",
                session_name="wellfound-session",
            ),
            detail_url: BbBrowserPageCapture(
                requested_url=detail_url,
                final_url=detail_url,
                status_code=200,
                html=fixture_text("wellfound", "detail.html"),
                content_type="text/html",
                session_name="wellfound-session",
            ),
        }
        return WellfoundSourceAdapter(
            backend=BbBrowserSessionBackend(client=FakeBbBrowserClient(captures))
        )

    listing_url = "https://www.workatastartup.com/jobs"
    detail_url = "https://www.workatastartup.com/jobs/yc-789-platform-engineer"
    captures = {
        listing_url: BbBrowserPageCapture(
            requested_url=listing_url,
            final_url=listing_url,
            status_code=200,
            html=fixture_text("yc_jobs", "listing.html"),
            content_type="text/html",
            session_name="yc-session",
        ),
        detail_url: BbBrowserPageCapture(
            requested_url=detail_url,
            final_url=detail_url,
            status_code=200,
            html=fixture_text("yc_jobs", "detail.html"),
            content_type="text/html",
            session_name="yc-session",
        ),
    }
    return YCJobsSourceAdapter(
        backend=BbBrowserSessionBackend(client=FakeBbBrowserClient(captures))
    )


@pytest.mark.parametrize("source_name", ["linkedin_jobs", "wellfound", "yc"])
def test_auth_board_run_persists_jobs_and_keeps_pipeline_compatible(monkeypatch, source_name):
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
    monkeypatch.setattr(discovery_module.settings, "bb_browser_enabled", True)
    if source_name == "linkedin_jobs":
        monkeypatch.setattr(discovery_module.settings, "linkedin_jobs_enabled", True)
    elif source_name == "wellfound":
        monkeypatch.setattr(discovery_module.settings, "wellfound_enabled", True)
    else:
        monkeypatch.setattr(discovery_module.settings, "yc_enabled", True)

    result = run_auth_board_source.run(run_id=run_id, source_name=source_name, max_results=1)

    assert result["status"] == "SUCCESS"
    assert result["stats"]["inserted"] == 1
    assert chain_sig.delay_called is True

    with get_sync_session() as session:
        run = session.get(ScrapeRun, uuid.UUID(run_id))
        assert run is not None
        assert run.status == ScrapeRunStatus.SUCCESS.value
        assert run.items_json and run.items_json[0]["source"] == source_name

        job = session.execute(
            select(Job).where(Job.source == source_name).order_by(Job.created_at.desc())
        ).scalars().first()
        assert job is not None
        assert job.source_role == SourceRole.DISCOVERY.value
        assert job.resolution_status == ResolutionStatus.PENDING.value
        assert job.pipeline_status == PipelineStatus.INGESTED.value

        source_row = session.execute(
            select(JobSourceRecord).where(
                JobSourceRecord.source_name == source_name,
                JobSourceRecord.external_id == job.source_job_id,
            )
        ).scalars().first()
        assert source_row is not None
        assert source_row.provenance_metadata["capture_metadata"]["acquisition_mode"] == "browser_session"


def test_auth_board_run_skips_when_source_flag_disabled():
    from apps.worker.tasks import discovery as discovery_module

    run_id = _create_running_discovery_run("linkedin_jobs")

    with patch.object(discovery_module, "settings") as mock_settings:
        mock_settings.linkedin_jobs_enabled = False
        mock_settings.bb_browser_enabled = True
        result = run_auth_board_source.run(
            run_id=run_id,
            source_name="linkedin_jobs",
            max_results=1,
        )

    assert result["status"] == "skipped"
    assert result["reason"] == "LINKEDIN_JOBS_ENABLED=false"


def test_auth_board_run_skips_when_bb_browser_backend_disabled():
    from apps.worker.tasks import discovery as discovery_module

    run_id = _create_running_discovery_run("wellfound")

    with patch.object(discovery_module, "settings") as mock_settings:
        mock_settings.wellfound_enabled = True
        mock_settings.bb_browser_enabled = False
        result = run_auth_board_source.run(
            run_id=run_id,
            source_name="wellfound",
            max_results=1,
        )

    assert result["status"] == "skipped"
    assert result["reason"] == "BB_BROWSER_ENABLED=false"
