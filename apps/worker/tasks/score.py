"""Score NEW jobs and update status to SCORED.

Canonical score data lives in job_analyses; Job.score_total/score_breakdown_json
are transitional mirrors until readers migrate.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from apps.api.settings import Settings
from apps.worker.celery_app import celery_app
from core.db.models import Job, JobAnalysis, PipelineStatus, UserStatus
from core.db.session import get_sync_session
from core.job_status import legacy_status_from_canonical
from core.scoring.scorer import score_job

settings = Settings()


@celery_app.task
def score_jobs(job_ids: list[str] | None = None):
    """Score all NEW jobs or specific job_ids. Update pipeline_status only."""
    with get_sync_session() as session:
        if job_ids:
            uuids = [UUID(jid) for jid in job_ids]
            stmt = select(Job).where(
                Job.id.in_(uuids),
                Job.pipeline_status == PipelineStatus.INGESTED.value,
            )
        else:
            stmt = select(Job).where(Job.pipeline_status == PipelineStatus.INGESTED.value)
        result = session.execute(stmt)
        jobs = result.scalars().all()
        for job in jobs:
            total, breakdown = score_job(job)
            job.score_total = total
            job.score_breakdown_json = breakdown

            if total < settings.scoring_threshold:
                job.pipeline_status = PipelineStatus.REJECTED.value
                # Do NOT set user_status; pipeline rejection stays pipeline-managed.
            else:
                job.pipeline_status = PipelineStatus.SCORED.value
            job.status = legacy_status_from_canonical(
                job.pipeline_status, job.user_status
            )

            # Upsert job_analyses: score task owns total_score, location_score, persona_specific_scores
            location_score = breakdown.get("location") if isinstance(breakdown, dict) else None
            stmt_ja = (
                insert(JobAnalysis)
                .values(
                    job_id=job.id,
                    total_score=total,
                    location_score=location_score,
                    persona_specific_scores=breakdown if isinstance(breakdown, dict) else None,
                )
                .on_conflict_do_update(
                    index_elements=["job_id"],
                    set_={
                        "total_score": total,
                        "location_score": location_score,
                        "persona_specific_scores": breakdown if isinstance(breakdown, dict) else None,
                    },
                )
            )
            session.execute(stmt_ja)
        session.commit()
    return {"scored": len(jobs)}
