"""Resume generation tasks. v1 uses only the grounded inventory-driven PDF path."""

import logging
from uuid import UUID

from apps.worker.celery_app import celery_app
from apps.worker.tasks.generation_runs import (
    mark_generation_run_failed,
    mark_generation_run_running,
    mark_generation_run_success,
)
from core.db.session import get_sync_session
from core.observability import log_context, get_metrics
from core.resumes.grounded_generator import generate_grounded_resume

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    acks_late=True,
)
def generate_grounded_resume_task(
    self,
    job_id: str,
    generation_run_id: str | None = None,
    triggered_by: str = "manual",
):
    """
    Generate grounded PDF resume from experience inventory (EPIC 7).
    Uses job analysis (persona, ATS keywords) to select and render content.
    When generation_run_id is provided, updates GenerationRun durably for
    manual and auto-triggered generation. Auto-triggered runs also update the
    Job's auto_generated_at timestamp.
    Returns artifact_id, status, and error if failed.
    """
    with log_context(job_id=job_id, task_name="generate_grounded_resume_task"):
        metrics = get_metrics()
        with get_sync_session() as session:
            mark_generation_run_running(session, generation_run_id)
            try:
                result = generate_grounded_resume(session=session, job_id=UUID(job_id))
            except Exception as exc:
                mark_generation_run_failed(
                    session,
                    generation_run_id,
                    str(exc) or exc.__class__.__name__,
                )
                session.commit()
                metrics.increment("resume.generation.failure")
                logger.exception("generate_grounded_resume_task crashed for job_id=%s", job_id)
                raise
            if result.status == "success" and result.artifact:
                metrics.increment("resume.generation.success")
                mark_generation_run_success(
                    session,
                    generation_run_id,
                    result.artifact.id,
                    triggered_by=triggered_by,
                    job_id=job_id,
                )
                out = {
                    "artifact_id": str(result.artifact.id),
                    "status": "success",
                }
                return out
            mark_generation_run_failed(
                session,
                generation_run_id,
                result.error or "Unknown error",
            )
            metrics.increment("resume.generation.failure")
            return {
                "artifact_id": None,
                "status": "failed",
                "error": result.error or "Unknown error",
            }
