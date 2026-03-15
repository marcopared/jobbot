"""Compute ATS resume match score for SCORED jobs."""

import logging
import os
from uuid import UUID

from sqlalchemy import select

from apps.api.settings import Settings
from apps.worker.celery_app import celery_app
from core.db.models import Job, JobStatus, PipelineStatus
from core.db.session import get_sync_session
from core.resumes.ats_scorer import compute_ats_match
from core.resumes.parser import extract_text_from_pdf

logger = logging.getLogger(__name__)
settings = Settings()


@celery_app.task
def ats_match_resume(job_ids: list[str] | None = None):
    """
    Compute ATS match score for SCORED jobs. Runs after score_jobs.
    Parses base resume once (cached per run), then compares against
    each job's description.
    """
    resume_path = settings.base_resume_path
    if not os.path.isfile(resume_path):
        logger.warning("Base resume not found at %s — skipping ATS matching", resume_path)
        return {"matched": 0, "skipped_no_resume": True}

    resume_text = extract_text_from_pdf(resume_path)
    if not resume_text.strip():
        logger.warning("Base resume is empty — skipping ATS matching")
        return {"matched": 0, "skipped_empty_resume": True}

    matched_count = 0
    with get_sync_session() as session:
        if job_ids:
            uuids = [UUID(jid) for jid in job_ids]
            stmt = select(Job).where(Job.id.in_(uuids))
        else:
            stmt = select(Job).where(Job.pipeline_status == PipelineStatus.SCORED.value)
        result = session.execute(stmt)
        jobs = result.scalars().all()

        for job in jobs:
            if not job.description:
                continue
            score, breakdown = compute_ats_match(resume_text, job.description)
            job.ats_match_score = score
            job.ats_match_breakdown_json = breakdown
            matched_count += 1

        session.commit()

    return {"matched": matched_count}
