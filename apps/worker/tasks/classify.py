"""Classify SCORED jobs into personas (EPIC 6).

Deterministic rules-based v1. Persists to job_analyses, updates pipeline_status to CLASSIFIED.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from apps.worker.celery_app import celery_app
from core.classification import RulesBasedClassifier
from core.observability import with_log_context, get_metrics
from core.observability.metrics import TaskTimer
from core.classification.types import ClassificationInput
from core.db.models import Job, JobAnalysis, PipelineStatus
from core.db.session import get_sync_session
from core.job_status import legacy_status_from_canonical


logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    acks_late=True,
)
def classify_jobs(self, job_ids: list[str] | None = None):
    """
    Classify SCORED jobs into BACKEND, PLATFORM_INFRA, or HYBRID.
    Updates job_analyses (matched_persona, persona_confidence, persona_rationale)
    and pipeline_status to CLASSIFIED.
    """
    with_log_context(task_name="classify_jobs")
    metrics = get_metrics()
    classifier = RulesBasedClassifier()
    classified_count = 0
    persona_counts: dict[str, int] = {}

    with get_sync_session() as session:
        if job_ids:
            uuids = [UUID(jid) for jid in job_ids]
            stmt = select(Job).where(
                Job.id.in_(uuids),
                Job.pipeline_status == PipelineStatus.SCORED.value,
            )
        else:
            stmt = select(Job).where(Job.pipeline_status == PipelineStatus.SCORED.value)
        result = session.execute(stmt)
        jobs = result.scalars().all()

        for job in jobs:
            # Build classification input from job and analysis
            analysis = _get_or_empty_analysis(session, job.id)
            inputs = ClassificationInput(
                normalized_title=job.normalized_title or job.title or "",
                description=job.description or "",
                found_keywords=analysis.get("found_keywords"),
                ats_categories=analysis.get("ats_categories"),
                score_breakdown=job.score_breakdown_json or analysis.get("persona_specific_scores"),
            )
            outcome = classifier.classify(inputs)

            job.pipeline_status = PipelineStatus.CLASSIFIED.value
            job.status = legacy_status_from_canonical(
                job.pipeline_status, job.user_status
            )

            # Format rationale for storage
            rationale_text = outcome.rationale
            if outcome.matched_signals:
                signals_str = ", ".join(
                    f"{k}={v}" for k, v in outcome.matched_signals.items()
                )
                rationale_text = f"{outcome.rationale} | Signals: {signals_str}"

            # Merge classification_signals into persona_specific_scores (preserve score breakdown)
            existing_scores = job.score_breakdown_json or analysis.get("persona_specific_scores") or {}
            if isinstance(existing_scores, dict):
                merged_scores = dict(existing_scores)
            else:
                merged_scores = {}
            merged_scores["classification_signals"] = outcome.matched_signals

            stmt_ja = (
                insert(JobAnalysis)
                .values(
                    job_id=job.id,
                    total_score=job.score_total,
                    matched_persona=outcome.persona.value,
                    persona_confidence=outcome.confidence,
                    persona_rationale=rationale_text,
                    persona_specific_scores=merged_scores,
                )
                .on_conflict_do_update(
                    index_elements=["job_id"],
                    set_={
                        "matched_persona": outcome.persona.value,
                        "persona_confidence": outcome.confidence,
                        "persona_rationale": rationale_text,
                        "persona_specific_scores": merged_scores,
                    },
                )
            )
            session.execute(stmt_ja)
            classified_count += 1
            persona_counts[outcome.persona.value] = persona_counts.get(outcome.persona.value, 0) + 1

        session.commit()

    for persona, count in persona_counts.items():
        metrics.increment("persona.distribution", value=count, tags=[f"persona:{persona}"])
    logger.info("Classified %s jobs", classified_count)
    return {"classified": classified_count}


def _get_or_empty_analysis(session, job_id) -> dict:
    """Fetch existing job_analysis row as dict for found_keywords, ats_categories."""
    stmt = select(JobAnalysis).where(JobAnalysis.job_id == job_id)
    row = session.execute(stmt).scalar_one_or_none()
    if not row:
        return {}
    return {
        "found_keywords": row.found_keywords or [],
        "ats_categories": row.ats_categories or {},
        "persona_specific_scores": row.persona_specific_scores or {},
    }
