"""Resume generation tasks. v1 uses only the grounded inventory-driven PDF path."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from apps.worker.celery_app import celery_app
from core.db.models import GenerationRun, GenerationRunStatus, Job
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
    When generation_run_id is provided (auto-triggered), updates GenerationRun
    and Job (artifact_ready_at, auto_generated_at).
    Returns artifact_id, status, and error if failed.
    """
    with log_context(job_id=job_id, task_name="generate_grounded_resume_task"):
        metrics = get_metrics()
        with get_sync_session() as session:
            if generation_run_id:
                run = session.get(GenerationRun, UUID(generation_run_id))
                if run:
                    run.status = GenerationRunStatus.RUNNING.value

            result = generate_grounded_resume(session=session, job_id=UUID(job_id))
            if result.status == "success" and result.artifact:
                metrics.increment("resume.generation.success")
                out = {
                    "artifact_id": str(result.artifact.id),
                    "status": "success",
                }
                if generation_run_id:
                    run = session.get(GenerationRun, UUID(generation_run_id))
                    if run:
                        run.status = GenerationRunStatus.SUCCESS.value
                        run.artifact_id = result.artifact.id
                        run.finished_at = datetime.now(timezone.utc)
                    job = session.get(Job, UUID(job_id))
                    if job:
                        job.auto_generated_at = datetime.now(timezone.utc)
                return out
            if generation_run_id:
                run = session.get(GenerationRun, UUID(generation_run_id))
                if run:
                    run.status = GenerationRunStatus.FAILED.value
                    run.failure_reason = result.error
                    run.finished_at = datetime.now(timezone.utc)
            metrics.increment("resume.generation.failure")
            return {
                "artifact_id": None,
                "status": "failed",
                "error": result.error or "Unknown error",
            }
