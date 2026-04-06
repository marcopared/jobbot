"""Grounded resume generation (EPIC 7).

Load evidence, run authoritative resume-v2 selection semantics, render HTML,
render PDF, and persist deterministic artifacts. No freeform LLM output; all
content comes from grounded structured evidence.
"""

import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.settings import Settings
from core.db.models import Artifact, ArtifactKind, Job, JobAnalysis, PipelineStatus
from core.resumes._serialization import canonical_json_dumps
from core.resumes.artifact_metadata import (
    RESUME_ARTIFACT_ROLE_DIAGNOSTICS,
    RESUME_ARTIFACT_ROLE_PAYLOAD,
    RESUME_ARTIFACT_ROLE_PRIMARY,
    build_resume_sidecar_documents,
)
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


@dataclass(frozen=True)
class StoredResumeArtifact:
    """Prepared storage payload for one persisted resume-generation artifact."""

    role: str
    kind: str
    filename: str
    content_type: str
    format: str
    version: str
    data: bytes
    meta_json: dict[str, object]


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


def _prepare_resume_artifacts(
    *,
    job_id: UUID,
    persona: str,
    analysis: JobAnalysis,
    generation_artifacts: ResumeGenerationArtifacts,
    fit_outcome: str,
    fit_diagnostics: FitDiagnostics,
    pdf_bytes: bytes,
) -> list[StoredResumeArtifact]:
    generated_at = datetime.now(UTC)
    timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
    stem = f"{timestamp}_resume"
    bundle_id = str(uuid4())
    common_meta, payload_document, diagnostics_document = build_resume_sidecar_documents(
        job_id=job_id,
        persona=persona,
        generated_at=generated_at,
        artifact_bundle_id=bundle_id,
        analysis=analysis,
        evidence_package=generation_artifacts.evidence_package,
        payload=generation_artifacts.payload,
        fit_result=generation_artifacts.fit_result,
        layout_plan=generation_artifacts.layout_plan,
        fit_diagnostics=fit_diagnostics,
        fit_outcome=fit_outcome,
    )

    payload_bytes = canonical_json_dumps(payload_document).encode("utf-8")
    diagnostics_bytes = canonical_json_dumps(diagnostics_document).encode("utf-8")

    return [
        StoredResumeArtifact(
            role=RESUME_ARTIFACT_ROLE_PRIMARY,
            kind=ArtifactKind.PDF.value,
            filename=f"{stem}.pdf",
            content_type="application/pdf",
            format="pdf",
            version="1",
            data=pdf_bytes,
            meta_json={
                **common_meta,
                "artifact_role": RESUME_ARTIFACT_ROLE_PRIMARY,
                "fit_outcome": fit_outcome,
                "sidecar_filenames": {
                    RESUME_ARTIFACT_ROLE_PAYLOAD: f"{stem}_payload.json",
                    RESUME_ARTIFACT_ROLE_DIAGNOSTICS: f"{stem}_diagnostics.json",
                },
            },
        ),
        StoredResumeArtifact(
            role=RESUME_ARTIFACT_ROLE_PAYLOAD,
            kind=ArtifactKind.OTHER.value,
            filename=f"{stem}_payload.json",
            content_type="application/json",
            format="json",
            version="resume-payload-sidecar-v1",
            data=payload_bytes,
            meta_json={
                **common_meta,
                "artifact_role": RESUME_ARTIFACT_ROLE_PAYLOAD,
                "fit_outcome": fit_outcome,
            },
        ),
        StoredResumeArtifact(
            role=RESUME_ARTIFACT_ROLE_DIAGNOSTICS,
            kind=ArtifactKind.OTHER.value,
            filename=f"{stem}_diagnostics.json",
            content_type="application/json",
            format="json",
            version="resume-diagnostics-sidecar-v1",
            data=diagnostics_bytes,
            meta_json={
                **common_meta,
                "artifact_role": RESUME_ARTIFACT_ROLE_DIAGNOSTICS,
                "fit_outcome": fit_outcome,
            },
        ),
    ]


def generate_grounded_resume(session: Session, job_id: UUID) -> GenerationResult:
    """
    Generate a grounded PDF resume for a high-fit job.

    1. Load experience inventory from YAML
    2. Get job analysis (persona, ATS keywords)
    3. Select content through the v2 fit planner/pipeline
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
    stored_artifacts = _prepare_resume_artifacts(
        job_id=job_id,
        persona=persona,
        analysis=analysis,
        generation_artifacts=generation_artifacts,
        fit_outcome=fit_outcome,
        fit_diagnostics=fit_diagnostics,
        pdf_bytes=pdf_bytes,
    )

    try:
        store_results = {
            prepared.role: storage.store(
                key=f"{job_id}/{prepared.filename}",
                data=prepared.data,
                content_type=prepared.content_type,
            )
            for prepared in stored_artifacts
        }
    except Exception as e:
        logger.exception("Storage failed for job %s", job_id)
        return GenerationResult(
            artifact=None,
            status="failed",
            fit_outcome=fit_outcome,
            fit_diagnostics=fit_diagnostics,
            error=f"Storage failed: {e}",
        )

    persisted_artifacts: dict[str, Artifact] = {}
    for prepared in stored_artifacts:
        store_result = store_results[prepared.role]
        artifact = Artifact(
            job_id=job_id,
            kind=prepared.kind,
            filename=prepared.filename,
            path=store_result.storage_key,
            size_bytes=len(prepared.data),
            persona_name=persona,
            file_url=store_result.file_url,
            format=prepared.format,
            version=prepared.version,
            template_version=TEMPLATE_VERSION,
            inventory_version_hash=generation_artifacts.evidence_package.inventory_version_hash,
            generation_status="success",
            meta_json=prepared.meta_json,
        )
        session.add(artifact)
        persisted_artifacts[prepared.role] = artifact

    session.flush()

    job.pipeline_status = PipelineStatus.RESUME_READY.value
    job.artifact_ready_at = datetime.now(UTC)

    return GenerationResult(
        artifact=persisted_artifacts[RESUME_ARTIFACT_ROLE_PRIMARY],
        status="success",
        fit_outcome=fit_outcome,
        fit_diagnostics=fit_diagnostics,
    )
