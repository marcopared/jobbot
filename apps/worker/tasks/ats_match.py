"""Compute ATS match for CLASSIFIED jobs (EPIC 5).

Canonical ATS data lives in job_analyses. Deterministic keyword extraction from
job description with synonym mapping; compares against master_skills. No LLM.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from apps.api.settings import Settings
from apps.worker.celery_app import celery_app
from core.ats.extraction import extract_ats_signals
from core.db.models import Job, JobAnalysis, PipelineStatus
from core.db.session import get_sync_session
from core.job_status import legacy_status_from_canonical
from core.observability import log_context, get_metrics
from core.observability.metrics import TaskTimer

logger = logging.getLogger(__name__)
settings = Settings()


@celery_app.task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    acks_late=True,
)
def ats_match_resume(self, job_ids: list[str] | dict | None = None):
    """
    Deterministic ATS extraction for CLASSIFIED jobs. Extracts keywords from JD,
    compares against master_skills, stores found/missing/categories.
    job_ids: list of job ids, or dict from chain (e.g. {"job_ids": [...]}), or None for all CLASSIFIED.
    """
    # Accept chain output from classify_jobs
    ids: list[str] | None = None
    if isinstance(job_ids, dict) and "job_ids" in job_ids:
        ids = job_ids["job_ids"]
    elif isinstance(job_ids, list):
        ids = job_ids

    with log_context(task_name="ats_match_resume"):
        metrics = get_metrics()
        matched_count = 0
        matched_job_ids: list[str] = []
        with get_sync_session() as session:
            if ids:
                uuids = [UUID(jid) for jid in ids]
                stmt = select(Job).where(
                    Job.id.in_(uuids),
                    Job.pipeline_status == PipelineStatus.CLASSIFIED.value,
                )
            else:
                stmt = select(Job).where(Job.pipeline_status == PipelineStatus.CLASSIFIED.value)
            result = session.execute(stmt)
            jobs = result.scalars().all()

            for job in jobs:
                if not job.description:
                    continue
                with log_context(job_id=str(job.id)):
                    result_ = extract_ats_signals(
                        job.description, user_skills_path=settings.master_skills_path
                    )
                    job.ats_match_score = result_.ats_compatibility_score
                    job.ats_match_breakdown_json = {
                        "found_keywords": result_.found_keywords,
                        "missing_keywords": result_.missing_keywords,
                        "ats_categories": result_.ats_categories,
                        "ats_compatibility_score": result_.ats_compatibility_score,
                    }

                    # Upsert job_analyses: ATS fields; preserve score columns
                    stmt_ja = (
                        insert(JobAnalysis)
                        .values(
                            job_id=job.id,
                            total_score=job.score_total,
                            ats_compatibility_score=result_.ats_compatibility_score,
                            found_keywords=result_.found_keywords,
                            missing_keywords=result_.missing_keywords,
                            ats_categories=result_.ats_categories,
                        )
                        .on_conflict_do_update(
                            index_elements=["job_id"],
                            set_={
                                "ats_compatibility_score": result_.ats_compatibility_score,
                                "found_keywords": result_.found_keywords,
                                "missing_keywords": result_.missing_keywords,
                                "ats_categories": result_.ats_categories,
                            },
                        )
                    )
                    session.execute(stmt_ja)
                    job.pipeline_status = PipelineStatus.ATS_ANALYZED.value
                    job.status = legacy_status_from_canonical(job.pipeline_status, job.user_status)
                    matched_count += 1
                    matched_job_ids.append(str(job.id))

            session.commit()

        metrics.increment("ats.analysis.success", value=matched_count)
        logger.info("ATS matched %s jobs", matched_count, extra={"task_name": "ats_match_resume"})
        return {"matched": matched_count, "job_ids": matched_job_ids}
