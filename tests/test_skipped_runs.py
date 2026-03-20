"""Regression tests: disabled feature flags must not leave ScrapeRun in RUNNING.

When a worker task exits early because its source/feature flag is disabled,
the ScrapeRun created by the API must be moved to a terminal SKIPPED state.

Requires: Postgres with migrations applied (alembic upgrade head).
Run: pytest tests/test_skipped_runs.py
"""

import uuid
from unittest.mock import patch

import pytest

from core.db.models import ScrapeRun, ScrapeRunStatus
from core.db.session import get_sync_session


def _create_running_run(source: str) -> str:
    """Insert a ScrapeRun with status=RUNNING. Returns run_id as string."""
    with get_sync_session() as session:
        run = ScrapeRun(
            source=source,
            status=ScrapeRunStatus.RUNNING.value,
            params_json={},
        )
        session.add(run)
        session.commit()
        return str(run.id)


def _get_run(run_id: str) -> dict:
    """Fetch a ScrapeRun and return its key fields as a dict."""
    with get_sync_session() as session:
        run = session.get(ScrapeRun, uuid.UUID(run_id))
        assert run is not None, f"ScrapeRun {run_id} not found"
        return {
            "status": run.status,
            "finished_at": run.finished_at,
            "error_text": run.error_text,
            "stats_json": run.stats_json,
            "items_json": run.items_json,
        }


class TestSkippedJobspy:
    def test_disabled_jobspy_marks_run_skipped(self):
        """scrape_jobspy with JOBSPY_ENABLED=false marks the run SKIPPED."""
        from apps.worker.tasks.scrape import scrape_jobspy

        run_id = _create_running_run("jobspy")

        with patch("apps.worker.tasks.scrape.settings") as mock_settings:
            mock_settings.jobspy_enabled = False
            result = scrape_jobspy(run_id=run_id)

        assert result["status"] == "skipped"

        run = _get_run(run_id)
        assert run["status"] == ScrapeRunStatus.SKIPPED.value
        assert run["finished_at"] is not None
        assert run["error_text"] == "JOBSPY_ENABLED=false"


class TestSkippedDiscovery:
    def test_disabled_agg1_marks_run_skipped(self):
        """run_discovery(agg1) with ENABLE_AGG1_DISCOVERY=false marks the run SKIPPED."""
        from apps.worker.tasks.discovery import run_discovery

        run_id = _create_running_run("agg1")

        with patch("apps.worker.tasks.discovery.settings") as mock_settings:
            mock_settings.enable_agg1_discovery = False
            result = run_discovery(run_id=run_id, connector="agg1")

        assert result["status"] == "skipped"

        run = _get_run(run_id)
        assert run["status"] == ScrapeRunStatus.SKIPPED.value
        assert run["finished_at"] is not None
        assert run["error_text"] == "ENABLE_AGG1_DISCOVERY=false"

    def test_disabled_serp1_marks_run_skipped(self):
        """run_discovery(serp1) with ENABLE_SERP1_DISCOVERY=false marks the run SKIPPED."""
        from apps.worker.tasks.discovery import run_discovery

        run_id = _create_running_run("serp1")

        with patch("apps.worker.tasks.discovery.settings") as mock_settings:
            mock_settings.enable_serp1_discovery = False
            result = run_discovery(run_id=run_id, connector="serp1")

        assert result["status"] == "skipped"

        run = _get_run(run_id)
        assert run["status"] == ScrapeRunStatus.SKIPPED.value
        assert run["finished_at"] is not None
        assert run["error_text"] == "ENABLE_SERP1_DISCOVERY=false"


class TestSkippedIngest:
    def test_disabled_greenhouse_marks_run_skipped(self):
        """ingest_greenhouse with GREENHOUSE_ENABLED=false marks the run SKIPPED."""
        from apps.worker.tasks.ingest import ingest_greenhouse

        run_id = _create_running_run("greenhouse")

        with patch("apps.worker.tasks.ingest.settings") as mock_settings:
            mock_settings.greenhouse_enabled = False
            result = ingest_greenhouse(
                run_id=run_id, board_token="test", company_name="TestCo"
            )

        assert result["status"] == "skipped"

        run = _get_run(run_id)
        assert run["status"] == ScrapeRunStatus.SKIPPED.value
        assert run["finished_at"] is not None
        assert run["error_text"] == "GREENHOUSE_ENABLED=false"

    def test_disabled_lever_marks_run_skipped(self):
        """ingest_lever with LEVER_ENABLED=false marks the run SKIPPED."""
        from apps.worker.tasks.ingest import ingest_lever

        run_id = _create_running_run("lever")

        with patch("apps.worker.tasks.ingest.settings") as mock_settings:
            mock_settings.lever_enabled = False
            result = ingest_lever(
                run_id=run_id, client_name="test", company_name="TestCo"
            )

        assert result["status"] == "skipped"

        run = _get_run(run_id)
        assert run["status"] == ScrapeRunStatus.SKIPPED.value
        assert run["finished_at"] is not None
        assert run["error_text"] == "LEVER_ENABLED=false"

    def test_disabled_ashby_marks_run_skipped(self):
        """ingest_ashby with ASHBY_ENABLED=false marks the run SKIPPED."""
        from apps.worker.tasks.ingest import ingest_ashby

        run_id = _create_running_run("ashby")

        with patch("apps.worker.tasks.ingest.settings") as mock_settings:
            mock_settings.ashby_enabled = False
            result = ingest_ashby(
                run_id=run_id, job_board_name="test", company_name="TestCo"
            )

        assert result["status"] == "skipped"

        run = _get_run(run_id)
        assert run["status"] == ScrapeRunStatus.SKIPPED.value
        assert run["finished_at"] is not None
        assert run["error_text"] == "ASHBY_ENABLED=false"

    def test_disabled_url_ingest_marks_run_skipped(self):
        """ingest_url with URL_INGEST_ENABLED=false marks the run SKIPPED."""
        from apps.worker.tasks.ingest import ingest_url

        run_id = _create_running_run("url_ingest")

        with patch("apps.worker.tasks.ingest.settings") as mock_settings:
            mock_settings.url_ingest_enabled = False
            result = ingest_url(
                run_id=run_id, url="https://boards.greenhouse.io/test/jobs/123"
            )

        assert result["status"] == "skipped"

        run = _get_run(run_id)
        assert run["status"] == ScrapeRunStatus.SKIPPED.value
        assert run["finished_at"] is not None
        assert run["error_text"] == "URL_INGEST_ENABLED=false"
