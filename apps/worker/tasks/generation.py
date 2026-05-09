"""Recommendation gate for the local MVP.

The current MVP does not generate custom resumes. After a job reaches
ATS_ANALYZED, this task chooses the best existing resume from data/resumes.yaml,
stores the suggestion on the job analysis row, and marks the job RESUME_READY
(meaning "resume recommendation ready" for the manual-apply queue).
"""

from datetime import datetime, timezone
import logging
from uuid import UUID

from sqlalchemy import select

from apps.api.settings import Settings
from apps.worker.celery_app import celery_app
from core.db.models import Job, PipelineStatus
from core.db.session import get_sync_session
from core.job_status import legacy_status_from_canonical
from core.observability import get_metrics, log_context
from core.resume_matching import suggest_resume_for_job

logger = logging.getLogger(__name__)
settings = Settings()


@celery_app.task(
    bind=True,
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=120,
    acks_late=True,
)
def evaluate_generation_gate(self, chain_output: dict | list[str] | None = None):
    """Compatibility task name for the old generation gate.

    It now evaluates existing-resume recommendation readiness. Keeping the task
    name avoids a broad Celery-chain rename while the architecture is being
    simplified.
    """
    ids: list[str] = []
    if isinstance(chain_output, dict) and chain_output.get("job_ids"):
        ids = chain_output["job_ids"]
    elif isinstance(chain_output, list):
        ids = chain_output

    if not ids:
        logger.debug("recommendation gate: no job_ids to evaluate")
        return {"evaluated": 0, "recommended": 0, "queued": 0}

    with log_context(task_name="evaluate_generation_gate"):
        metrics = get_metrics()
        recommended = 0
        with get_sync_session() as session:
            uuids = [UUID(jid) for jid in ids]
            jobs = session.execute(select(Job).where(Job.id.in_(uuids))).scalars().all()

            for job in jobs:
                if job.pipeline_status != PipelineStatus.ATS_ANALYZED.value:
                    continue
                analysis = job.analyses[0] if job.analyses else None
                matched_persona = analysis.matched_persona if analysis else None
                suggestion = suggest_resume_for_job(
                    title=job.title or job.normalized_title,
                    description=job.description,
                    matched_persona=matched_persona,
                )
                if suggestion is None:
                    job.generation_eligibility = "ineligible"
                    job.generation_reason = "No existing resume catalog found at data/resumes.yaml."
                    continue

                suggestion_payload = suggestion.to_dict()
                job.generation_eligibility = "eligible"
                job.generation_reason = suggestion.rationale
                job.artifact_ready_at = datetime.now(timezone.utc)
                job.pipeline_status = PipelineStatus.RESUME_READY.value
                job.status = legacy_status_from_canonical(job.pipeline_status, job.user_status)

                if analysis is not None:
                    existing = analysis.persona_specific_scores or {}
                    if not isinstance(existing, dict):
                        existing = {}
                    existing["resume_suggestion"] = suggestion_payload
                    analysis.persona_specific_scores = existing

                recommended += 1

            session.commit()

        metrics.increment("recommendation.ready", value=recommended)
        logger.info(
            "Recommendation gate evaluated %s jobs, marked %s ready",
            len(ids),
            recommended,
            extra={"task_name": "evaluate_generation_gate"},
        )
        return {"evaluated": len(ids), "recommended": recommended, "queued": 0}
