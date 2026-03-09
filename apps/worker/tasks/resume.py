from uuid import UUID

from apps.worker.celery_app import celery_app
from core.db.session import get_sync_session
from core.resumes.manager import prepare_resume


@celery_app.task
def prepare_resume_task(job_id: str):
    """Prepare resume artifact for a job and return artifact ID."""
    with get_sync_session() as session:
        artifact = prepare_resume(session=session, job_id=UUID(job_id))
        if artifact is None:
            return {"artifact_id": None}
        return {"artifact_id": str(artifact.id)}
