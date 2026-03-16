"""Grounded resume generation (EPIC 7).

Load inventory, select content by job/ATS/persona, render HTML, render PDF.
No freeform LLM output; all content from structured inventory.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.settings import Settings
from core.db.models import Artifact, ArtifactKind, Job, JobAnalysis, PipelineStatus
from core.inventory.loader import compute_inventory_hash, load_inventory
from core.inventory.types import ExperienceInventory
from core.resumes.html_template import RenderedResumeData, TEMPLATE_VERSION, render_html
from core.resumes.pdf_renderer import render_html_to_pdf_bytes
from core.resumes.rewrite import apply_conservative_rewrite
from core.resumes.selection import (
    select_projects,
    select_roles,
    select_skills,
)
from core.storage.factory import get_artifact_storage

logger = logging.getLogger(__name__)
settings = Settings()


@dataclass
class GenerationResult:
    """Result of grounded resume generation."""

    artifact: Artifact | None
    status: str  # "success" | "failed"
    error: str | None = None


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


def _format_dates(start: str, end: str) -> str:
    if not start and not end:
        return ""
    return f"{start or '?'} – {end or 'present'}"


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

    target_keywords = _build_target_keywords(job, analysis)

    # Load inventory
    inv_path = Path(settings.experience_inventory_path)
    if not inv_path.is_file():
        logger.warning("Experience inventory not found at %s", inv_path)
        return GenerationResult(
            artifact=None,
            status="failed",
            error="Experience inventory not found",
        )

    try:
        inventory: ExperienceInventory = load_inventory(inv_path)
    except Exception as e:
        logger.exception("Failed to load experience inventory")
        return GenerationResult(
            artifact=None,
            status="failed",
            error=str(e),
        )

    inv_hash = compute_inventory_hash(inventory)

    # Select content
    selected_roles = select_roles(inventory, target_keywords, persona)
    selected_projects = select_projects(inventory, target_keywords, persona)
    selected_skills = select_skills(inventory, target_keywords)

    summary = inventory.summary_variants.get(persona) or inventory.summary_variants.get(
        "HYBRID"
    ) or ""

    missing_kw = set()
    if analysis and analysis.missing_keywords:
        missing_kw = {k.lower() for k in analysis.missing_keywords}
    elif job.ats_match_breakdown_json:
        for k in job.ats_match_breakdown_json.get("missing_keywords") or []:
            missing_kw.add(k.lower())

    # Build role/project structures for template
    roles_data = []
    for role, bullets in selected_roles:
        rewritten = [apply_conservative_rewrite(b, missing_kw) for b in bullets]
        roles_data.append(
            {
                "company": role.company,
                "title": role.title,
                "dates": _format_dates(role.start, role.end),
                "bullets": rewritten,
            }
        )

    projects_data = []
    for proj, bullets in selected_projects:
        rewritten = [apply_conservative_rewrite(b, missing_kw) for b in bullets]
        projects_data.append({"name": proj.name, "bullets": rewritten})

    resume_data = RenderedResumeData(
        contact_name=inventory.contact.name,
        contact_email=inventory.contact.email,
        contact_location=inventory.contact.location,
        summary=summary,
        skills=selected_skills,
        roles=roles_data,
        projects=projects_data,
        education=inventory.education or [],
    )

    html = render_html(resume_data)

    try:
        pdf_bytes = render_html_to_pdf_bytes(html, timeout_ms=settings.playwright_timeout_ms)
    except Exception as e:
        logger.exception("PDF render failed for job %s", job_id)
        return GenerationResult(
            artifact=None,
            status="failed",
            error=f"PDF render failed: {e}",
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
        inventory_version_hash=inv_hash,
        generation_status="success",
        meta_json={
            "grounded": True,
            "persona": persona,
            "ats_compatibility_score": analysis.ats_compatibility_score if analysis else None,
            "generated_at": datetime.now(UTC).isoformat(),
        },
    )
    session.add(artifact)
    session.flush()

    job.pipeline_status = PipelineStatus.RESUME_READY.value

    return GenerationResult(artifact=artifact, status="success")
