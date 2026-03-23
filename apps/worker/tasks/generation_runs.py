"""Shared helpers for GenerationRun creation and lifecycle updates."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from core.db.models import GenerationRun, GenerationRunStatus, Job


def build_generation_run(job_id: UUID, triggered_by: str) -> GenerationRun:
    """Create a queued GenerationRun model for manual or auto generation."""
    return GenerationRun(
        job_id=job_id,
        status=GenerationRunStatus.QUEUED.value,
        triggered_by=triggered_by,
    )


def mark_generation_run_running(
    session: Session, generation_run_id: str | UUID | None
) -> GenerationRun | None:
    """Move a GenerationRun into RUNNING when a worker starts processing it."""
    run = _get_run(session, generation_run_id)
    if run is None:
        return None
    run.status = GenerationRunStatus.RUNNING.value
    run.finished_at = None
    run.failure_reason = None
    return run


def mark_generation_run_success(
    session: Session,
    generation_run_id: str | UUID | None,
    artifact_id: UUID,
    *,
    triggered_by: str,
    job_id: str | UUID,
) -> GenerationRun | None:
    """Finalize a GenerationRun as SUCCESS and attach the artifact."""
    run = _get_run(session, generation_run_id)
    if run is None:
        return None
    run.status = GenerationRunStatus.SUCCESS.value
    run.artifact_id = artifact_id
    run.failure_reason = None
    run.finished_at = datetime.now(timezone.utc)
    if triggered_by == "auto":
        job = session.get(Job, UUID(str(job_id)))
        if job is not None:
            job.auto_generated_at = datetime.now(timezone.utc)
    return run


def mark_generation_run_failed(
    session: Session,
    generation_run_id: str | UUID | None,
    reason: str,
) -> GenerationRun | None:
    """Finalize a GenerationRun as FAILED with a stored reason."""
    run = _get_run(session, generation_run_id)
    if run is None:
        return None
    run.status = GenerationRunStatus.FAILED.value
    run.failure_reason = reason
    run.finished_at = datetime.now(timezone.utc)
    return run


def _get_run(
    session: Session, generation_run_id: str | UUID | None
) -> GenerationRun | None:
    if generation_run_id is None:
        return None
    return session.get(GenerationRun, UUID(str(generation_run_id)))
