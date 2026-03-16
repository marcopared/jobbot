"""Score NEW jobs and update status to SCORED.

Canonical score data lives in job_analyses; Job.score_total/score_breakdown_json
are transitional mirrors until readers migrate.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from apps.api.settings import Settings
from apps.worker.celery_app import celery_app
from core.db.models import Job, JobAnalysis, PipelineStatus
from core.db.session import get_sync_session
from core.job_status import legacy_status_from_canonical
from core.observability import log_context, get_metrics
from core.observability.metrics import TaskTimer
from core.scoring.scorer import score_job

settings = Settings()
logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    acks_late=True,
)
def score_jobs(self, job_ids: list[str] | None = None):
    """Score all NEW jobs or specific job_ids. Update pipeline_status only."""
    with log_context(task_name="score_jobs"):
        metrics = get_metrics()
        rejected = 0
        scored_count = 0
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
            scored_job_ids: list[str] = []
            for job in jobs:
                total, breakdown = score_job(job, master_skills_path=settings.master_skills_path)
                job.score_total = total
                job.score_breakdown_json = breakdown

                if total < settings.scoring_threshold:
                    job.pipeline_status = PipelineStatus.REJECTED.value
                    rejected += 1
                    # Do NOT set user_status; pipeline rejection stays pipeline-managed.
                else:
                    job.pipeline_status = PipelineStatus.SCORED.value
                    scored_count += 1
                    scored_job_ids.append(str(job.id))
                metrics.histogram("score.distribution", total)
                job.status = legacy_status_from_canonical(
                    job.pipeline_status, job.user_status
                )

                # Upsert job_analyses: full score breakdown, individual factor scores
                bd = breakdown if isinstance(breakdown, dict) else {}
                stmt_ja = (
                    insert(JobAnalysis)
                .values(
                    job_id=job.id,
                    total_score=total,
                    seniority_score=bd.get("seniority_fit"),
                    tech_stack_score=bd.get("tech_stack"),
                    location_score=bd.get("location_remote"),
                    persona_specific_scores=breakdown if isinstance(breakdown, dict) else None,
                )
                .on_conflict_do_update(
                    index_elements=["job_id"],
                    set_={
                        "total_score": total,
                        "seniority_score": bd.get("seniority_fit"),
                        "tech_stack_score": bd.get("tech_stack"),
                        "location_score": bd.get("location_remote"),
                        "persona_specific_scores": breakdown if isinstance(breakdown, dict) else None,
                    },
                )
            )
            session.execute(stmt_ja)
        session.commit()
    metrics.increment("jobs.scored", value=scored_count)
    metrics.increment("rejected.count", value=rejected)
    logger.info("Scored %s jobs, rejected %s", len(jobs), rejected, extra={"task_name": "score_jobs"})
    return {"scored": len(jobs), "rejected": rejected, "job_ids": scored_job_ids}
