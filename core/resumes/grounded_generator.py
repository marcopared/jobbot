"""Grounded resume generation (EPIC 7).

Load inventory, select content by job/ATS/persona, render HTML, render PDF.
No freeform LLM output; all content from structured inventory.
"""

import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.settings import Settings
from core.db.models import Artifact, ArtifactKind, Job, JobAnalysis, PipelineStatus
from core.resumes.evidence_builder import build_resume_evidence_package
from core.resumes.fit_planner import plan_resume_artifacts
from core.resumes.effective_input import ResumeEffectiveInput
from core.resumes.evidence_types import ResumeEvidencePackage
from core.resumes.html_template import TEMPLATE_VERSION, render_html
from core.resumes.layout_types import (
    FIT_OUTCOME_FAILED_OVERFLOW,
    FIT_OUTCOME_SUCCESS_MULTI_PAGE_FALLBACK,
    FIT_OUTCOME_SUCCESS_ONE_PAGE,
    FitDiagnostics,
    FitResult,
    LayoutPlan,
)
from core.resumes.payload_types import ResumePayloadV2
from core.resumes.pdf_renderer import count_pdf_pages, render_html_to_pdf_bytes
from core.storage.factory import get_artifact_storage

logger = logging.getLogger(__name__)
settings = Settings()


@dataclass
class GenerationResult:
    """Result of grounded resume generation."""

    artifact: Artifact | None
    status: str  # "success" | "failed"
    fit_outcome: str | None = None
    fit_diagnostics: FitDiagnostics | None = None
    error: str | None = None


@dataclass(frozen=True)
class ResumeGenerationArtifacts:
    """Intermediate grounded generation artifacts produced before rendering/persistence."""

    evidence_package: ResumeEvidencePackage
    fit_result: FitResult
    effective_input: ResumeEffectiveInput
    payload: ResumePayloadV2
    layout_plan: LayoutPlan
    fit_diagnostics: FitDiagnostics


def _get_job_analysis(session: Session, job_id: UUID) -> JobAnalysis | None:
    result = session.execute(select(JobAnalysis).where(JobAnalysis.job_id == job_id))
    return result.scalar_one_or_none()


def _build_target_keywords(job: Job, analysis: JobAnalysis | None) -> set[str]:
    """Combine found + missing keywords for selection (prioritize found)."""
    keywords = set()
    if analysis:
        for kw in analysis.found_keywords or []:
            keywords.add(kw.lower())
        for kw in analysis.missing_keywords or []:
            keywords.add(kw.lower())
    if job.ats_match_breakdown_json:
        for kw in job.ats_match_breakdown_json.get("found_keywords") or []:
            keywords.add(kw.lower())
        for kw in job.ats_match_breakdown_json.get("missing_keywords") or []:
            keywords.add(kw.lower())
    return keywords


def _build_generation_artifacts(
    *,
    job: Job,
    analysis: JobAnalysis,
    inventory_path: Path,
) -> ResumeGenerationArtifacts:
    evidence_package = build_resume_evidence_package(
        job,
        inventory_path=inventory_path,
        inputs_dir=settings.resume_inputs_dir,
    )

    found_keywords = {keyword.lower() for keyword in (analysis.found_keywords or [])}
    if job.ats_match_breakdown_json:
        for keyword in job.ats_match_breakdown_json.get("found_keywords") or []:
            found_keywords.add(str(keyword).lower())

    missing_keywords = {keyword.lower() for keyword in (analysis.missing_keywords or [])}
    if job.ats_match_breakdown_json:
        for keyword in job.ats_match_breakdown_json.get("missing_keywords") or []:
            missing_keywords.add(str(keyword).lower())

    planned_resume = plan_resume_artifacts(
        evidence_package,
        persona=analysis.matched_persona,
        target_keywords=_build_target_keywords(job, analysis),
        found_keywords=found_keywords,
        missing_keywords=missing_keywords,
        template_version=TEMPLATE_VERSION,
        fallback_enabled=settings.resume_generation_allow_multi_page_fallback,
    )
    return ResumeGenerationArtifacts(
        evidence_package=evidence_package,
        fit_result=planned_resume.fit_result,
        effective_input=planned_resume.effective_input,
        payload=planned_resume.payload,
        layout_plan=planned_resume.layout_plan,
        fit_diagnostics=planned_resume.fit_diagnostics,
    )


def generate_grounded_resume(session: Session, job_id: UUID) -> GenerationResult:
    """
    Generate a grounded PDF resume for a high-fit job.

    1. Load experience inventory from YAML
    2. Get job analysis (persona, ATS keywords)
    3. Select content (roles, projects, skills)
    4. Render HTML and PDF
    5. Store artifact and metadata

    Returns GenerationResult with artifact and status.
    """
    job = session.get(Job, job_id)
    if not job:
        return GenerationResult(artifact=None, status="failed", error="Job not found")

    # Strict readiness check: fail closed unless job is analysis-ready (defense-in-depth).
    # Must match API gate: pipeline_status and analysis/persona required.
    RESUME_READY_STATUSES = frozenset(
        {PipelineStatus.ATS_ANALYZED.value, PipelineStatus.RESUME_READY.value}
    )
    if job.pipeline_status not in RESUME_READY_STATUSES:
        return GenerationResult(
            artifact=None,
            status="failed",
            error=f"Resume generation requires pipeline_status ATS_ANALYZED or RESUME_READY. "
            f"Current: {job.pipeline_status}.",
        )

    analysis = _get_job_analysis(session, job_id)
    if not analysis:
        return GenerationResult(
            artifact=None,
            status="failed",
            error="Resume generation requires a JobAnalysis row. None found.",
        )

    persona = analysis.matched_persona
    if not persona or not str(persona).strip():
        return GenerationResult(
            artifact=None,
            status="failed",
            error="Resume generation requires matched_persona in JobAnalysis. "
            "Cannot fall back to HYBRID when analysis is incomplete.",
        )

    inv_path = Path(settings.experience_inventory_path)
    if not inv_path.is_file():
        logger.warning("Experience inventory not found at %s", inv_path)
        return GenerationResult(
            artifact=None,
            status="failed",
            error="Experience inventory not found",
        )

    try:
        generation_artifacts = _build_generation_artifacts(
            job=job,
            analysis=analysis,
            inventory_path=inv_path,
        )
    except Exception as e:
        logger.exception("Failed to build grounded resume artifacts")
        return GenerationResult(
            artifact=None,
            status="failed",
            error=str(e),
        )

    html = render_html(generation_artifacts.payload, generation_artifacts.layout_plan)

    try:
        pdf_bytes = render_html_to_pdf_bytes(html, timeout_ms=settings.playwright_timeout_ms)
    except Exception as e:
        logger.exception("PDF render failed for job %s", job_id)
        return GenerationResult(
            artifact=None,
            status="failed",
            fit_diagnostics=generation_artifacts.fit_diagnostics,
            error=f"PDF render failed: {e}",
        )

    try:
        actual_page_count = count_pdf_pages(pdf_bytes)
    except Exception as e:
        logger.exception("PDF validation failed for job %s", job_id)
        return GenerationResult(
            artifact=None,
            status="failed",
            fit_diagnostics=generation_artifacts.fit_diagnostics,
            error=f"PDF validation failed: {e}",
        )

    fit_diagnostics = replace(
        generation_artifacts.fit_diagnostics,
        actual_page_count=actual_page_count,
    )
    if actual_page_count < 1:
        return GenerationResult(
            artifact=None,
            status="failed",
            fit_outcome=FIT_OUTCOME_FAILED_OVERFLOW,
            fit_diagnostics=fit_diagnostics,
            error="PDF validation failed: rendered document has no pages",
        )

    if actual_page_count == 1:
        fit_outcome = FIT_OUTCOME_SUCCESS_ONE_PAGE
    elif settings.resume_generation_allow_multi_page_fallback:
        fit_outcome = FIT_OUTCOME_SUCCESS_MULTI_PAGE_FALLBACK
    else:
        return GenerationResult(
            artifact=None,
            status="failed",
            fit_outcome=FIT_OUTCOME_FAILED_OVERFLOW,
            fit_diagnostics=fit_diagnostics,
            error=(
                f"Rendered resume overflowed to {actual_page_count} pages; "
                "resume_generation_allow_multi_page_fallback=false"
            ),
        )

    # Store (storage backend: local or GCS)
    storage = get_artifact_storage()
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    # Relative key: backends apply the resumes/ prefix exactly once
    relative_key = f"{job_id}/{timestamp}_resume.pdf"

    try:
        store_result = storage.store(
            key=relative_key,
            data=pdf_bytes,
            content_type="application/pdf",
        )
    except Exception as e:
        logger.exception("Storage failed for job %s", job_id)
        return GenerationResult(
            artifact=None,
            status="failed",
            fit_outcome=fit_outcome,
            fit_diagnostics=fit_diagnostics,
            error=f"Storage failed: {e}",
        )

    filename = f"{timestamp}_resume.pdf"
    artifact = Artifact(
        job_id=job_id,
        kind=ArtifactKind.PDF.value,
        filename=filename,
        path=store_result.storage_key,
        size_bytes=len(pdf_bytes),
        persona_name=persona,
        file_url=store_result.file_url,
        format="pdf",
        version="1",
        template_version=TEMPLATE_VERSION,
        inventory_version_hash=generation_artifacts.evidence_package.inventory_version_hash,
        generation_status="success",
        meta_json={
            "grounded": True,
            "persona": persona,
            "ats_compatibility_score": analysis.ats_compatibility_score if analysis else None,
            "generated_at": datetime.now(UTC).isoformat(),
            "fit_outcome": fit_outcome,
            "resume_v2": {
                "evidence_schema_version": generation_artifacts.evidence_package.schema_version,
                "payload_schema_version": generation_artifacts.payload.schema_version,
                "fit_schema_version": generation_artifacts.fit_result.schema_version,
                "layout_schema_version": generation_artifacts.layout_plan.schema_version,
                "fit_diagnostics_schema_version": fit_diagnostics.schema_version,
                "source_kind": generation_artifacts.evidence_package.source_kind,
                "inputs_hash": generation_artifacts.evidence_package.inputs_hash,
                "evidence_hash": generation_artifacts.evidence_package.compute_hash(),
                "fit_hash": generation_artifacts.fit_result.compute_hash(),
                "payload_hash": generation_artifacts.payload.compute_hash(),
                "layout_hash": generation_artifacts.layout_plan.compute_hash(),
                "effective_input_hash": generation_artifacts.payload.effective_input_hash,
                "fit_outcome": fit_outcome,
                "fit_diagnostics": fit_diagnostics.to_dict(),
                "missing_optional_sources": list(
                    generation_artifacts.evidence_package.missing_optional_sources
                ),
                "source_metadata": [
                    {
                        "source_name": source.source_name,
                        "required": source.required,
                        "present": source.present,
                        "source_kind": source.source_kind,
                        "format": source.format,
                        "item_count": source.item_count,
                        "used_for_facts": source.used_for_facts,
                        "used_for_targeting": source.used_for_targeting,
                        "used_for_preferences": source.used_for_preferences,
                    }
                    for source in generation_artifacts.evidence_package.source_metadata
                ],
            },
        },
    )
    session.add(artifact)
    session.flush()

    job.pipeline_status = PipelineStatus.RESUME_READY.value
    job.artifact_ready_at = datetime.now(UTC)

    return GenerationResult(
        artifact=artifact,
        status="success",
        fit_outcome=fit_outcome,
        fit_diagnostics=fit_diagnostics,
    )
