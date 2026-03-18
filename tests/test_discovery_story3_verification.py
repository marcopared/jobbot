"""Story 3 verification tests for discovery end-to-end behavior.

Covers:
- POST /api/jobs/run-discovery route wiring (agg1, serp1)
- Discovery persistence semantics (source_role, resolution_status, confidence, raw payload)
- Downstream chain trigger (score -> classify -> ATS -> generation gate)
- Safe provider timeout/failure behavior
- Adzuna smoke: discovery-originated job reaches artifact-ready and ready-to-apply
- DataForSEO smoke: discovery-originated job reaches ATS + generation gate evaluation
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select

from apps.api.main import app
from apps.worker.tasks.ats_match import ats_match_resume
from apps.worker.tasks.classify import classify_jobs
from apps.worker.tasks.discovery import run_discovery
from apps.worker.tasks.generation import evaluate_generation_gate
from apps.worker.tasks.score import score_jobs
from core.connectors.base import (
    CanonicalJobPayload,
    FetchResult,
    ProvenanceMetadata,
    RawJobWithProvenance,
)
from core.db.models import (
    Artifact,
    GenerationRun,
    GenerationRunStatus,
    Job,
    JobSourceRecord,
    PipelineStatus,
    ResolutionStatus,
    ScrapeRun,
    ScrapeRunStatus,
    SourceRole,
)
from core.db.session import get_sync_session


@dataclass
class _DelayCall:
    kwargs: dict[str, Any]


class _DummySig:
    """Minimal Celery-signature-like object for chain interception in tests."""

    def __init__(self):
        self.delay_called = False

    def __or__(self, other):
        return self

    def delay(self):
        self.delay_called = True
        return None


class _FakeDiscoveryConnector:
    def __init__(
        self, source_name: str, raw_jobs: list[dict[str, Any]], error: str | None = None
    ):
        self._source_name = source_name
        self._raw_jobs = raw_jobs
        self._error = error

    @property
    def source_name(self) -> str:
        return self._source_name

    def fetch_raw_jobs(self, **params: Any) -> FetchResult:
        if self._error:
            return FetchResult(
                raw_jobs=[], stats={"fetched": 0, "errors": 1}, error=self._error
            )

        prov = ProvenanceMetadata(
            fetch_timestamp="2026-03-17T00:00:00Z",
            source_url=f"https://{self._source_name}.example/jobs",
            connector_version="test",
        )
        wrapped = [
            RawJobWithProvenance(raw_payload=r, provenance=prov) for r in self._raw_jobs
        ]
        return FetchResult(
            raw_jobs=wrapped, stats={"fetched": len(wrapped), "errors": 0}, error=None
        )

    def normalize(
        self, raw_job: dict[str, Any], **context: Any
    ) -> CanonicalJobPayload | None:
        title = str(raw_job.get("title") or "").strip()
        if not title:
            return None

        company = str(raw_job.get("company") or "Unknown")
        location = str(raw_job.get("location") or "Remote")
        description = str(raw_job.get("description") or "")
        apply_url = (
            str(raw_job.get("apply_url") or raw_job.get("source_url") or "").strip()
            or None
        )
        source_url = str(raw_job.get("source_url") or apply_url or "").strip() or None
        posted_at = datetime.now(UTC)

        return CanonicalJobPayload(
            source_name=self._source_name,
            external_id=str(
                raw_job.get("id")
                or raw_job.get("job_id")
                or f"{self._source_name}-{uuid.uuid4()}"
            ),
            title=title,
            company=company,
            location=location,
            employment_type=str(raw_job.get("contract_type") or "") or None,
            description=description,
            apply_url=apply_url,
            source_url=source_url,
            posted_at=posted_at,
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


def _latest_job_for_source(source: str) -> dict[str, Any]:
    with get_sync_session() as session:
        row = (
            session.execute(
                select(Job).where(Job.source == source).order_by(Job.created_at.desc())
            )
            .scalars()
            .first()
        )
        assert row is not None
        return {
            "id": str(row.id),
            "source_role": row.source_role,
            "resolution_status": row.resolution_status,
            "source_confidence": row.source_confidence,
            "source_payload_json": row.source_payload_json,
        }


async def test_post_run_discovery_enqueues_agg1_with_expected_params(
    client, monkeypatch
):
    from apps.api.routes import jobs as jobs_route

    calls: list[_DelayCall] = []

    def _fake_delay(**kwargs):
        calls.append(_DelayCall(kwargs=kwargs))
        return MagicMock(id="task-agg1")

    monkeypatch.setattr(jobs_route.settings, "enable_agg1_discovery", True)
    monkeypatch.setattr(jobs_route.run_discovery, "delay", _fake_delay)

    resp = await client.post(
        "/api/jobs/run-discovery",
        json={
            "connector": "agg1",
            "query": "backend engineer",
            "location": "Austin, TX",
            "results_per_page": 25,
            "max_pages": 2,
            "max_results": 30,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["connector"] == "agg1"
    assert data["status"] == "RUNNING"
    assert data["task_id"] == "task-agg1"
    assert calls and calls[0].kwargs["connector"] == "agg1"
    assert calls[0].kwargs["query"] == "backend engineer"
    assert calls[0].kwargs["results_per_page"] == 25


async def test_post_run_discovery_enqueues_serp1_with_expected_params(
    client, monkeypatch
):
    from apps.api.routes import jobs as jobs_route

    calls: list[_DelayCall] = []

    def _fake_delay(**kwargs):
        calls.append(_DelayCall(kwargs=kwargs))
        return MagicMock(id="task-serp1")

    monkeypatch.setattr(jobs_route.settings, "enable_serp1_discovery", True)
    monkeypatch.setattr(jobs_route.run_discovery, "delay", _fake_delay)

    resp = await client.post(
        "/api/jobs/run-discovery",
        json={"connector": "serp1", "query": "platform engineer", "location": "Remote"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["connector"] == "serp1"
    assert data["status"] == "RUNNING"
    assert data["task_id"] == "task-serp1"
    assert calls and calls[0].kwargs["connector"] == "serp1"


def test_discovery_persistence_semantics_and_chain_trigger(monkeypatch):
    unique = str(uuid.uuid4())[:8]
    raw = {
        "id": f"adzuna-{unique}",
        "title": "Senior Backend Engineer",
        "company": "Acme Discovery",
        "location": "Remote",
        "description": "Python AWS PostgreSQL " + ("high quality " * 40),
        "apply_url": f"https://apply.example.com/jobs/adzuna-{unique}",
        "source_url": f"https://source.example.com/jobs/adzuna-{unique}",
        "provider_extra": {"foo": "bar", "n": 7},
    }
    run_id = _create_running_discovery_run("agg1")
    connector = _FakeDiscoveryConnector("agg1", [raw])

    chain_sig = _DummySig()
    score_sig = MagicMock(return_value=chain_sig)
    classify_sig = MagicMock(return_value=_DummySig())
    ats_sig = MagicMock(return_value=_DummySig())
    gate_sig = MagicMock(return_value=_DummySig())

    monkeypatch.setattr(
        "apps.worker.tasks.discovery.create_agg1_connector", lambda **kwargs: connector
    )
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.settings.enable_agg1_discovery", True
    )
    monkeypatch.setattr("apps.worker.tasks.discovery.score_jobs.s", score_sig)
    monkeypatch.setattr("apps.worker.tasks.discovery.classify_jobs.s", classify_sig)
    monkeypatch.setattr("apps.worker.tasks.discovery.ats_match_resume.s", ats_sig)
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.evaluate_generation_gate.s", gate_sig
    )

    out = run_discovery.apply(
        kwargs={
            "run_id": run_id,
            "connector": "agg1",
            "query": "backend engineer",
            "location": "Remote",
            "max_pages": 1,
            "max_results": 5,
        }
    ).get()

    assert out["status"] == "SUCCESS"
    assert out["stats"]["inserted"] == 1
    assert score_sig.call_count == 1
    inserted_ids = score_sig.call_args.args[0]
    assert isinstance(inserted_ids, list)
    assert len(inserted_ids) == 1
    assert chain_sig.delay_called is True

    job = _latest_job_for_source("agg1")
    assert job["source_role"] == SourceRole.DISCOVERY.value
    assert job["resolution_status"] == ResolutionStatus.PENDING.value
    assert (job["source_confidence"] or 0.0) > 0.7
    assert isinstance(job["source_payload_json"], dict)
    assert job["source_payload_json"].get("provider_extra", {}).get("foo") == "bar"

    with get_sync_session() as session:
        source_rows = (
            session.execute(
                select(JobSourceRecord).where(
                    JobSourceRecord.job_id == uuid.UUID(job["id"])
                )
            )
            .scalars()
            .all()
        )
        assert source_rows
        assert source_rows[0].source_name == "agg1"
        assert source_rows[0].raw_data.get("provider_extra", {}).get("n") == 7


def test_discovery_safe_timeout_failure_marks_run_failed(monkeypatch):
    run_id = _create_running_discovery_run("serp1")
    connector = _FakeDiscoveryConnector(
        "serp1", raw_jobs=[], error="DataForSEO readiness timeout"
    )

    score_sig = MagicMock(return_value=_DummySig())
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.create_serp1_connector", lambda **kwargs: connector
    )
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.settings.enable_serp1_discovery", True
    )
    monkeypatch.setattr("apps.worker.tasks.discovery.score_jobs.s", score_sig)

    out = run_discovery.apply(
        kwargs={
            "run_id": run_id,
            "connector": "serp1",
            "query": "platform engineer",
            "location": "Remote",
        }
    ).get()

    assert out["status"] == "FAILED"
    assert "timeout" in out["error"].lower()
    assert score_sig.call_count == 0

    with get_sync_session() as session:
        run = session.get(ScrapeRun, uuid.UUID(run_id))
        assert run is not None
        assert run.status == ScrapeRunStatus.FAILED.value
        assert run.error_text is not None
        assert "timeout" in run.error_text.lower()


def _fake_generation_delay(job_id: str, generation_run_id: str | None = None):
    """Synchronous test replacement for generate task delay."""
    with get_sync_session() as session:
        job = session.get(Job, uuid.UUID(job_id))
        assert job is not None

        artifact = Artifact(
            job_id=job.id,
            kind="pdf",
            filename="test_resume.pdf",
            path=f"storage/artifacts/{job_id}/test_resume.pdf",
            size_bytes=12345,
            generation_status="success",
            file_url="/api/artifacts/fake/download",
        )
        session.add(artifact)
        session.flush()

        job.pipeline_status = PipelineStatus.RESUME_READY.value
        job.artifact_ready_at = datetime.now(UTC)
        job.auto_generated_at = datetime.now(UTC)

        if generation_run_id:
            run = session.get(GenerationRun, uuid.UUID(generation_run_id))
            if run:
                run.status = GenerationRunStatus.SUCCESS.value
                run.artifact_id = artifact.id
                run.finished_at = datetime.now(UTC)

    return MagicMock(id="fake-generation-task")


async def test_adzuna_discovery_e2e_smoke_to_artifact_ready_and_ready_to_apply(
    client, monkeypatch
):
    unique = str(uuid.uuid4())[:8]
    raw = {
        "id": f"adzuna-smoke-{unique}",
        "title": "Senior Backend Platform Engineer",
        "company": "Adzuna Smoke Co",
        "location": "Remote",
        "description": (
            "Python FastAPI PostgreSQL AWS Redis Kubernetes CI/CD monitoring ownership "
            "" + ("distributed systems reliability performance security " * 15)
        ),
        "apply_url": f"https://apply.example.com/jobs/adzuna-smoke-{unique}",
        "source_url": f"https://source.example.com/jobs/adzuna-smoke-{unique}",
    }

    run_id = _create_running_discovery_run("agg1")
    connector = _FakeDiscoveryConnector("agg1", [raw])

    chain_sig = _DummySig()
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.create_agg1_connector", lambda **kwargs: connector
    )
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.settings.enable_agg1_discovery", True
    )
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.score_jobs.s", MagicMock(return_value=chain_sig)
    )
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.classify_jobs.s",
        MagicMock(return_value=_DummySig()),
    )
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.ats_match_resume.s",
        MagicMock(return_value=_DummySig()),
    )
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.evaluate_generation_gate.s",
        MagicMock(return_value=_DummySig()),
    )

    out = run_discovery.apply(
        kwargs={
            "run_id": run_id,
            "connector": "agg1",
            "query": "backend engineer",
            "location": "Remote",
            "max_pages": 1,
            "max_results": 5,
        }
    ).get()
    assert out["status"] == "SUCCESS"

    inserted_job_id = out["stats"]["inserted"]
    assert inserted_job_id == 1

    job = _latest_job_for_source("agg1")
    job_id = job["id"]

    # Explicitly drive the downstream chain synchronously in test.
    score_jobs.apply(kwargs={"job_ids": [job_id]})
    classify_jobs.apply(kwargs={"job_ids": [job_id]})
    ats_out = ats_match_resume.apply(kwargs={"job_ids": [job_id]}).get()

    # Ensure gate eligibility for this discovery smoke by setting a robust score.
    with get_sync_session() as session:
        j = session.get(Job, uuid.UUID(job_id))
        assert j is not None
        j.score_total = max(80.0, j.score_total or 0.0)

    from apps.worker.tasks import generation as generation_task

    monkeypatch.setattr(generation_task.settings, "enable_auto_resume_generation", True)
    monkeypatch.setattr(
        generation_task.generate_grounded_resume_task, "delay", _fake_generation_delay
    )

    gate_out = evaluate_generation_gate.apply(kwargs={"chain_output": ats_out}).get()
    assert gate_out["evaluated"] >= 1
    assert gate_out["queued"] >= 1

    with get_sync_session() as session:
        j = session.get(Job, uuid.UUID(job_id))
        assert j is not None
        assert j.pipeline_status == PipelineStatus.RESUME_READY.value
        assert j.artifact_ready_at is not None

    ready_resp = await client.get("/api/jobs/ready-to-apply?per_page=100")
    assert ready_resp.status_code == 200
    ready_ids = [item["id"] for item in ready_resp.json()["items"]]
    assert job_id in ready_ids

    detail_resp = await client.get(f"/api/jobs/{job_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert (
        detail["apply_url"] == f"https://apply.example.com/jobs/adzuna-smoke-{unique}"
    )


async def test_dataforseo_discovery_e2e_smoke_to_ats_and_generation_gate(monkeypatch):
    unique = str(uuid.uuid4())[:8]
    raw = {
        "job_id": f"dfs-smoke-{unique}",
        "title": "Platform Engineer",
        "company": "DataForSEO Smoke Co",
        "location": "Remote",
        "description": "Platform work with APIs and infra " + ("reliability " * 30),
        "apply_url": f"https://apply.example.com/jobs/dfs-smoke-{unique}",
        "source_url": f"https://source.example.com/jobs/dfs-smoke-{unique}",
        "timestamp": "2026-03-17T10:00:00Z",
    }

    run_id = _create_running_discovery_run("serp1")
    connector = _FakeDiscoveryConnector("serp1", [raw])

    chain_sig = _DummySig()
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.create_serp1_connector", lambda **kwargs: connector
    )
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.settings.enable_serp1_discovery", True
    )
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.score_jobs.s", MagicMock(return_value=chain_sig)
    )
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.classify_jobs.s",
        MagicMock(return_value=_DummySig()),
    )
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.ats_match_resume.s",
        MagicMock(return_value=_DummySig()),
    )
    monkeypatch.setattr(
        "apps.worker.tasks.discovery.evaluate_generation_gate.s",
        MagicMock(return_value=_DummySig()),
    )

    out = run_discovery.apply(
        kwargs={
            "run_id": run_id,
            "connector": "serp1",
            "query": "platform engineer",
            "location": "Remote",
        }
    ).get()
    assert out["status"] == "SUCCESS"
    assert out["stats"]["inserted"] == 1

    job = _latest_job_for_source("serp1")
    job_id = job["id"]

    # SERP confidence must remain lower than AGG-1/canonical semantics.
    assert (job["source_confidence"] or 1.0) <= 0.69
    assert job["source_role"] == SourceRole.DISCOVERY.value
    assert job["resolution_status"] == ResolutionStatus.PENDING.value

    score_jobs.apply(kwargs={"job_ids": [job_id]})
    classify_jobs.apply(kwargs={"job_ids": [job_id]})
    ats_out = ats_match_resume.apply(kwargs={"job_ids": [job_id]}).get()

    gate_out = evaluate_generation_gate.apply(kwargs={"chain_output": ats_out}).get()
    assert gate_out["evaluated"] >= 1
    # Default setting keeps auto generation disabled; verify safe no-queue behavior.
    assert gate_out["queued"] == 0

    with get_sync_session() as session:
        j = session.get(Job, uuid.UUID(job_id))
        assert j is not None
        assert j.pipeline_status == PipelineStatus.ATS_ANALYZED.value
