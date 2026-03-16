"""Resume generation tasks. v1 uses only the grounded inventory-driven PDF path."""

import logging
from uuid import UUID

from apps.worker.celery_app import celery_app
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
def generate_grounded_resume_task(self, job_id: str):
    """
    Generate grounded PDF resume from experience inventory (EPIC 7).
    Uses job analysis (persona, ATS keywords) to select and render content.
    Returns artifact_id, status, and error if failed.
    """
    with log_context(job_id=job_id, task_name="generate_grounded_resume_task"):
        metrics = get_metrics()
        with get_sync_session() as session:
            result = generate_grounded_resume(session=session, job_id=UUID(job_id))
            if result.status == "success" and result.artifact:
                session.commit()
                metrics.increment("resume.generation.success")
                return {
                    "artifact_id": str(result.artifact.id),
                    "status": "success",
                }
            session.rollback()
            metrics.increment("resume.generation.failure")
            return {
                "artifact_id": None,
                "status": "failed",
                "error": result.error or "Unknown error",
            }
