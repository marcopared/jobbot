"""Score NEW jobs and update status to SCORED."""

from uuid import UUID

from sqlalchemy import select

from apps.api.settings import Settings
from apps.worker.celery_app import celery_app
from core.db.models import Job, JobStatus, PipelineStatus, UserStatus
from core.db.session import get_sync_session
from core.scoring.scorer import score_job

settings = Settings()

@celery_app.task
def score_jobs(job_ids: list[str] | None = None):
    """Score all NEW jobs or specific job_ids. Update status to SCORED."""
    with get_sync_session() as session:
        if job_ids:
            uuids = [UUID(jid) for jid in job_ids]
            stmt = select(Job).where(
                Job.id.in_(uuids),
                Job.user_status == UserStatus.NEW.value,
            )
        else:
            stmt = select(Job).where(Job.user_status == UserStatus.NEW.value)
        result = session.execute(stmt)
        jobs = result.scalars().all()
        for job in jobs:
            total, breakdown = score_job(job)
            job.score_total = total
            job.score_breakdown_json = breakdown
            if total < settings.scoring_threshold:
                job.pipeline_status = PipelineStatus.REJECTED.value
                # If pipeline rejects it, we archive it for the user so it doesn't clutter their "NEW" feed.
                job.user_status = UserStatus.ARCHIVED.value
                job.status = JobStatus.REJECTED.value
            else:
                job.pipeline_status = PipelineStatus.SCORED.value
                # It passed the pipeline threshold, so keep it NEW for user review.
                job.user_status = UserStatus.NEW.value
                job.status = JobStatus.SCORED.value
        session.commit()
    return {"scored": len(jobs)}
