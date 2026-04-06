"""Tests for grounded resume generator readiness (defense-in-depth).

Verifies that generate_grounded_resume fails closed when job is not analysis-ready,
even when invoked directly (bypassing API). Requires Postgres with migrations applied.
Run: pytest tests/test_grounded_generator.py
"""

import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import select

from core.db.models import Artifact, Company, Job, JobAnalysis, PipelineStatus
from core.db.session import get_sync_session
from core.dedup import compute_dedup_hash_from_raw, normalize_company, normalize_title
from core.resumes.grounded_generator import generate_grounded_resume
from core.resumes.layout_types import (
    FIT_OUTCOME_FAILED_OVERFLOW,
    FIT_OUTCOME_SUCCESS_MULTI_PAGE_FALLBACK,
)

FIT_FIXTURES = Path(__file__).parent / "fixtures"


@dataclass
class _FakeStoreResult:
    storage_key: str
    file_url: str | None = None


def _make_job(
    pipeline_status: str,
    *,
    with_analysis: bool = True,
    matched_persona: str | None = "BACKEND",
    has_ats_keywords: bool = True,
) -> uuid.UUID:
    """Create Job + optional JobAnalysis. Returns job_id."""
    unique = str(uuid.uuid4())[:8]
    company_name = f"TestGen_{unique}"
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
            source="jobspy",
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
            description="Python, AWS, APIs",
            status="NEW",
            user_status="NEW",
            pipeline_status=pipeline_status,
            score_total=75.0,
            dedup_hash=dedup_hash,
        )
        session.add(job)
        session.flush()
        if with_analysis:
            analysis = JobAnalysis(
                job_id=job.id,
                total_score=75.0,
                matched_persona=matched_persona,
                persona_confidence=0.9 if matched_persona else None,
                persona_rationale="Test" if matched_persona else None,
                found_keywords=["python", "aws"] if has_ats_keywords else None,
                missing_keywords=["postgresql"] if has_ats_keywords else None,
                ats_compatibility_score=0.85 if has_ats_keywords else None,
            )
            session.add(analysis)
            session.flush()
        job_id = job.id
    return job_id


def test_missing_analysis_fails():
    """Generator fails when JobAnalysis row does not exist."""
    job_id = _make_job(
        pipeline_status=PipelineStatus.ATS_ANALYZED.value,
        with_analysis=False,
    )
    with get_sync_session() as session:
        result = generate_grounded_resume(session=session, job_id=job_id)
    assert result.status == "failed"
    assert result.artifact is None
    assert "JobAnalysis" in (result.error or "")


def test_wrong_pipeline_status_fails():
    """Generator fails when pipeline_status is not ATS_ANALYZED or RESUME_READY."""
    for status in (PipelineStatus.SCORED.value, PipelineStatus.CLASSIFIED.value):
        job_id = _make_job(
            pipeline_status=status,
            with_analysis=True,
            matched_persona="BACKEND",
        )
        with get_sync_session() as session:
            result = generate_grounded_resume(session=session, job_id=job_id)
        assert result.status == "failed"
        assert result.artifact is None
        assert "ATS_ANALYZED" in (result.error or "") or "RESUME_READY" in (result.error or "")


def test_missing_persona_fails():
    """Generator fails when JobAnalysis.matched_persona is missing (no HYBRID fallback)."""
    job_id = _make_job(
        pipeline_status=PipelineStatus.ATS_ANALYZED.value,
        with_analysis=True,
        matched_persona=None,
        has_ats_keywords=True,
    )
    with get_sync_session() as session:
        result = generate_grounded_resume(session=session, job_id=job_id)
    assert result.status == "failed"
    assert result.artifact is None
    assert "matched_persona" in (result.error or "")
    assert "HYBRID" in (result.error or "")


def test_ats_analyzed_with_analysis_persona_succeeds():
    """Generator succeeds when job is ATS_ANALYZED with analysis and persona."""
    job_id = _make_job(
        pipeline_status=PipelineStatus.ATS_ANALYZED.value,
        with_analysis=True,
        matched_persona="BACKEND",
        has_ats_keywords=True,
    )
    with get_sync_session() as session:
        result = generate_grounded_resume(session=session, job_id=job_id)
        if result.status == "failed" and (
            "inventory" in (result.error or "").lower()
            or "Experience inventory" in (result.error or "")
        ):
            pytest.skip(
                "Experience inventory not found; run from project root with data/experience_inventory.yaml"
            )
        assert result.status == "success"
        assert result.artifact is not None
        assert "resumes/resumes/" not in (result.artifact.path or "")
        assert result.artifact.meta_json["resume_v2"]["effective_input_hash"]
        persona = result.artifact.persona_name
    assert persona == "BACKEND"


def test_resume_ready_with_analysis_persona_succeeds():
    """Generator succeeds when job is RESUME_READY with analysis and persona."""
    job_id = _make_job(
        pipeline_status=PipelineStatus.RESUME_READY.value,
        with_analysis=True,
        matched_persona="HYBRID",
        has_ats_keywords=True,
    )
    with get_sync_session() as session:
        result = generate_grounded_resume(session=session, job_id=job_id)
        if result.status == "failed" and (
            "inventory" in (result.error or "").lower()
            or "Experience inventory" in (result.error or "")
        ):
            pytest.skip(
                "Experience inventory not found; run from project root with data/experience_inventory.yaml"
            )
        assert result.status == "success"
        assert result.artifact is not None
        assert "resumes/resumes/" not in (result.artifact.path or "")
        assert result.artifact.meta_json["resume_v2"]["payload_schema_version"] == "resume-payload-v2"
        persona = result.artifact.persona_name
    assert persona == "HYBRID"


def test_multi_page_overflow_fails_closed_by_default(monkeypatch, tmp_path):
    """Two-page renders do not persist artifact success when fallback is disabled."""

    job_id = _make_job(
        pipeline_status=PipelineStatus.ATS_ANALYZED.value,
        with_analysis=True,
        matched_persona="BACKEND",
        has_ats_keywords=True,
    )
    import core.resumes.grounded_generator as generator_module

    monkeypatch.setattr(
        generator_module.settings,
        "experience_inventory_path",
        str(FIT_FIXTURES / "resume_fit" / "overflow_inventory" / "experience_inventory.yaml"),
    )
    monkeypatch.setattr(
        generator_module.settings,
        "resume_inputs_dir",
        str(tmp_path / "resume_inputs"),
    )
    monkeypatch.setattr(generator_module.settings, "resume_generation_allow_multi_page_fallback", False)
    monkeypatch.setattr(generator_module, "render_html_to_pdf_bytes", lambda html, timeout_ms: b"%PDF-1.4")
    monkeypatch.setattr(generator_module, "count_pdf_pages", lambda pdf_bytes: 2)

    def _unexpected_storage():
        raise AssertionError("storage should not be reached when overflow fails closed")

    monkeypatch.setattr(generator_module, "get_artifact_storage", _unexpected_storage)

    with get_sync_session() as session:
        result = generate_grounded_resume(session=session, job_id=job_id)
        session.rollback()

    assert result.status == "failed"
    assert result.fit_outcome == FIT_OUTCOME_FAILED_OVERFLOW
    assert result.artifact is None
    assert result.fit_diagnostics is not None
    assert result.fit_diagnostics.actual_page_count == 2

    with get_sync_session() as session:
        job = session.get(Job, job_id)
        assert job.pipeline_status == PipelineStatus.ATS_ANALYZED.value
        assert job.artifact_ready_at is None
        artifact_count = session.execute(
            select(Artifact).where(Artifact.job_id == job_id)
        ).scalars().all()
        assert artifact_count == []


def test_multi_page_fallback_succeeds_when_enabled(monkeypatch, tmp_path):
    """Explicit fallback allows persistence and records the multi-page fit outcome."""

    job_id = _make_job(
        pipeline_status=PipelineStatus.ATS_ANALYZED.value,
        with_analysis=True,
        matched_persona="BACKEND",
        has_ats_keywords=True,
    )
    import core.resumes.grounded_generator as generator_module

    monkeypatch.setattr(
        generator_module.settings,
        "experience_inventory_path",
        str(FIT_FIXTURES / "resume_fit" / "overflow_inventory" / "experience_inventory.yaml"),
    )
    monkeypatch.setattr(
        generator_module.settings,
        "resume_inputs_dir",
        str(tmp_path / "resume_inputs"),
    )
    monkeypatch.setattr(generator_module.settings, "resume_generation_allow_multi_page_fallback", True)
    monkeypatch.setattr(generator_module, "render_html_to_pdf_bytes", lambda html, timeout_ms: b"%PDF-1.4")
    monkeypatch.setattr(generator_module, "count_pdf_pages", lambda pdf_bytes: 2)

    class _FakeStorage:
        def store(self, key: str, data: bytes, content_type: str):
            assert key.endswith("_resume.pdf")
            assert data == b"%PDF-1.4"
            assert content_type == "application/pdf"
            return _FakeStoreResult(storage_key=f"resumes/{key}")

    monkeypatch.setattr(generator_module, "get_artifact_storage", lambda: _FakeStorage())

    with get_sync_session() as session:
        result = generate_grounded_resume(session=session, job_id=job_id)
        assert result.status == "success"
        assert result.fit_outcome == FIT_OUTCOME_SUCCESS_MULTI_PAGE_FALLBACK
        assert result.artifact is not None
        assert result.artifact.meta_json["fit_outcome"] == FIT_OUTCOME_SUCCESS_MULTI_PAGE_FALLBACK
        assert result.artifact.meta_json["resume_v2"]["fit_diagnostics"]["actual_page_count"] == 2
        session.commit()

    with get_sync_session() as session:
        job = session.get(Job, job_id)
        assert job.pipeline_status == PipelineStatus.RESUME_READY.value
        assert job.artifact_ready_at is not None
