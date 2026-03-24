from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from apps.api.main import app
from apps.worker.tasks.discovery import run_discovery
from apps.worker.tasks.ingest import ingest_greenhouse
from apps.worker.tasks.scrape import scrape_jobspy
from core.connectors.base import (
    CanonicalJobPayload,
    FetchResult,
    ProvenanceMetadata,
    RawJobWithProvenance,
)
from core.db.models import JobSource, ScrapeRun, ScrapeRunStatus
from core.db.session import get_sync_session
from core.run_items import normalize_run_item
from core.scraping.base import NormalizedJob, ScrapeResult


CANONICAL_FIELDS = {
    "index",
    "outcome",
    "job_id",
    "dedup_hash",
    "source",
    "source_job_id",
    "title",
    "company_name",
    "location",
    "url",
    "apply_url",
    "ats_type",
    "raw_payload_json",
}


class _DummySig:
    def __or__(self, other):
        return self

    def delay(self):
        return None


class _FakeTask:
    def s(self, *args, **kwargs):
        return _DummySig()


@dataclass
class _FakeJobSpyScraper:
    result: ScrapeResult

    def scrape(self, params):
        return self.result


class _FakeConnector:
    def __init__(self, source_name: str, raw_jobs: list[dict[str, Any]]):
        self.source_name = source_name
        self._raw_jobs = raw_jobs

    def fetch_raw_jobs(self, **params: Any) -> FetchResult:
        provenance = ProvenanceMetadata(
            fetch_timestamp="2026-03-22T10:00:00Z",
            source_url=f"https://{self.source_name}.example/jobs",
            connector_version="test",
        )
        return FetchResult(
            raw_jobs=[
                RawJobWithProvenance(raw_payload=raw_job, provenance=provenance)
                for raw_job in self._raw_jobs
            ],
            stats={"fetched": len(self._raw_jobs), "errors": 0},
            error=None,
        )

    def normalize(self, raw_job: dict[str, Any], **context: Any) -> CanonicalJobPayload | None:
        title = str(raw_job.get("title") or "").strip()
        if not title:
            return None

        company = str(raw_job.get("company") or "Unknown Co").strip()
        location = str(raw_job.get("location") or "Remote").strip()
        apply_url = str(raw_job.get("apply_url") or raw_job.get("source_url") or "").strip() or None
        source_url = str(raw_job.get("source_url") or apply_url or "").strip() or None
        external_id = str(raw_job.get("id") or raw_job.get("job_id") or uuid.uuid4())

        return CanonicalJobPayload(
            source_name=self.source_name,
            external_id=external_id,
            title=title,
            company=company,
            location=location,
            employment_type=None,
            description=str(raw_job.get("description") or "").strip() or None,
            apply_url=apply_url,
            source_url=source_url,
            posted_at=datetime.now(UTC),
            raw_payload=raw_job,
            normalized_title=title.lower(),
            normalized_company=company.lower(),
            normalized_location=location.lower(),
        )


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _create_running_run(source: str, params_json: dict[str, Any] | None = None) -> str:
    with get_sync_session() as session:
        run = ScrapeRun(
            source=source,
            status=ScrapeRunStatus.RUNNING.value,
            params_json=params_json or {},
        )
        session.add(run)
        session.commit()
        return str(run.id)


def _get_first_run_item(run_id: str) -> dict[str, Any]:
    with get_sync_session() as session:
        run = session.get(ScrapeRun, uuid.UUID(run_id))
        assert run is not None
        assert isinstance(run.items_json, list) and run.items_json
        return run.items_json[0]


def _assert_canonical_item(item: dict[str, Any], *, source: str, company_name: str) -> None:
    normalized = normalize_run_item(item, run_source=source, default_index=1)
    missing = CANONICAL_FIELDS - set(item.keys())
    assert not missing, f"Stored run item missing canonical fields: {missing}"
    assert item == normalized, "Run item should already be stored in canonical form"
    assert item["source"] == source
    assert item["company_name"] == company_name
    assert item["url"]
    assert item["ats_type"]
    assert isinstance(item["raw_payload_json"], (dict, list)) or item["raw_payload_json"] is None


def _patch_pipeline(monkeypatch, module) -> None:
    fake_task = _FakeTask()
    monkeypatch.setattr(module, "score_jobs", fake_task)
    monkeypatch.setattr(module, "classify_jobs", fake_task)
    monkeypatch.setattr(module, "ats_match_resume", fake_task)
    monkeypatch.setattr(module, "evaluate_generation_gate", fake_task)


async def test_manual_ingest_writes_canonical_run_item_schema(client, monkeypatch):
    from apps.api.routes import jobs as jobs_route

    monkeypatch.setattr(
        jobs_route.manual_ingest_pipeline,
        "delay",
        lambda job_ids: type("TaskResult", (), {"id": "manual-task"})(),
    )

    unique = str(uuid.uuid4())[:8]
    resp = await client.post(
        "/api/jobs/manual-ingest",
        json={
            "title": f"Manual Schema {unique}",
            "company": "Manual Schema Co",
            "location": "Remote",
            "apply_url": f"https://example.com/manual-{unique}",
            "description": "Manual schema regression test.",
        },
    )
    assert resp.status_code == 200

    item = _get_first_run_item(resp.json()["run_id"])
    _assert_canonical_item(item, source="manual_intake", company_name="Manual Schema Co")
    assert item["raw_payload_json"]["intake_source"] == "manual_intake"


def test_jobspy_scrape_writes_canonical_run_item_schema(monkeypatch):
    from apps.worker.tasks import scrape as scrape_module

    monkeypatch.setattr(scrape_module.settings, "jobspy_enabled", True)
    monkeypatch.setattr(scrape_module.settings, "default_search_query", "backend engineer")
    monkeypatch.setattr(scrape_module.settings, "default_location", "Remote")
    monkeypatch.setattr(scrape_module.settings, "scrape_hours_old", 24)
    monkeypatch.setattr(scrape_module.settings, "scrape_results_wanted", 10)
    monkeypatch.setattr(
        scrape_module,
        "JobSpyScraper",
        lambda: _FakeJobSpyScraper(
            ScrapeResult(
                jobs=[
                    NormalizedJob(
                        title="JobSpy Engineer",
                        company_name="JobSpy Co",
                        location="Remote",
                        url="https://jobspy.example/jobs/1",
                        apply_url="https://jobspy.example/apply/1",
                        description="A detailed jobspy posting",
                        salary_min=None,
                        salary_max=None,
                        posted_at=datetime.now(UTC),
                        remote_flag=True,
                        source=JobSource.JOBSPY,
                        source_job_id="jobspy-1",
                        raw_payload={"job_board": "jobspy"},
                    )
                ],
                stats={"fetched": 1, "errors": 0},
                error=None,
            )
        ),
    )
    _patch_pipeline(monkeypatch, scrape_module)

    run_id = _create_running_run("jobspy")
    result = scrape_jobspy(run_id=run_id, query="backend engineer", location="Remote")

    assert result["status"] == "SUCCESS"
    item = _get_first_run_item(run_id)
    _assert_canonical_item(item, source="jobspy", company_name="JobSpy Co")


def test_canonical_ingest_writes_canonical_run_item_schema(monkeypatch):
    from apps.worker.tasks import ingest as ingest_module

    monkeypatch.setattr(ingest_module.settings, "greenhouse_enabled", True)
    monkeypatch.setattr(
        ingest_module,
        "create_greenhouse_connector",
        lambda board_token, company_name: _FakeConnector(
            "greenhouse",
            [
                {
                    "id": "gh-1",
                    "title": "Canonical Engineer",
                    "company": "Canonical Co",
                    "location": "New York, NY",
                    "source_url": "https://boards.greenhouse.io/canonical/jobs/1",
                    "apply_url": "https://boards.greenhouse.io/canonical/jobs/1#app",
                    "description": "Canonical ingest regression test",
                }
            ],
        ),
    )
    _patch_pipeline(monkeypatch, ingest_module)

    run_id = _create_running_run("greenhouse")
    result = ingest_greenhouse(run_id=run_id, board_token="canonical", company_name="Canonical Co")

    assert result["status"] == "SUCCESS"
    item = _get_first_run_item(run_id)
    _assert_canonical_item(item, source="greenhouse", company_name="Canonical Co")


def test_discovery_ingest_writes_canonical_run_item_schema(monkeypatch):
    from apps.worker.tasks import discovery as discovery_module

    monkeypatch.setattr(discovery_module.settings, "enable_agg1_discovery", True)
    monkeypatch.setattr(
        discovery_module,
        "create_agg1_connector",
        lambda *args, **kwargs: _FakeConnector(
            "agg1",
            [
                {
                    "id": "agg1-1",
                    "title": "Discovery Engineer",
                    "company": "Discovery Co",
                    "location": "Austin, TX",
                    "source_url": "https://agg1.example/jobs/1",
                    "apply_url": "https://agg1.example/apply/1",
                    "description": "Discovery regression test",
                }
            ],
        ),
    )
    _patch_pipeline(monkeypatch, discovery_module)

    run_id = _create_running_run("agg1", {"connector": "agg1"})
    result = run_discovery(run_id=run_id, connector="agg1", query="engineer", location="Austin, TX")

    assert result["status"] == "SUCCESS"
    item = _get_first_run_item(run_id)
    _assert_canonical_item(item, source="agg1", company_name="Discovery Co")
