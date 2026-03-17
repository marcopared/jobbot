"""Generation gate evaluation and auto-generation queue (PR5, ARCH §10).

Evaluates ATS_ANALYZED jobs against generation gate; queues generate_grounded_resume_task
for eligible jobs. Tracks runs via GenerationRun.
"""

from datetime import datetime, timezone
import logging
from uuid import UUID

from sqlalchemy import select

from apps.api.settings import Settings
from apps.worker.celery_app import celery_app
from core.automation.generation_gate import evaluate_generation_eligibility, gate_config_from_settings
from core.db.models import GenerationRun, GenerationRunStatus, Job
from core.db.session import get_sync_session
from core.observability import log_context, get_metrics

from apps.worker.tasks.resume import generate_grounded_resume_task

logger = logging.getLogger(__name__)
settings = Settings()


@celery_app.task(
    bind=True,
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=120,
    acks_late=True,
)
def evaluate_generation_gate(self, chain_output: dict | None = None):
    """
    Evaluate generation gate for ATS_ANALYZED jobs. Queue generation for eligible ones.

    chain_output: dict from ats_match_resume with {"matched": N, "job_ids": [...]}.
    """
    ids: list[str] = []
    if isinstance(chain_output, dict) and chain_output.get("job_ids"):
        ids = chain_output["job_ids"]
    elif isinstance(chain_output, list):
        ids = chain_output

    if not ids:
        logger.debug("evaluate_generation_gate: no job_ids to evaluate")
        return {"evaluated": 0, "queued": 0}

    config = gate_config_from_settings(settings)
    with log_context(task_name="evaluate_generation_gate"):
        metrics = get_metrics()
        queued = 0
        with get_sync_session() as session:
            uuids = [UUID(jid) for jid in ids]
            stmt = select(Job).where(Job.id.in_(uuids))
            result = session.execute(stmt)
            jobs = result.scalars().all()

            runs_to_queue: list[tuple[str, str, str]] = []
            for job in jobs:
                eligible, reason = evaluate_generation_eligibility(job, config)
                if not eligible:
                    logger.debug(
                        "Job %s not eligible: %s",
                        job.id,
                        reason,
                        extra={"job_id": str(job.id), "reason": reason},
                    )
                    continue

                run = GenerationRun(
                    job_id=job.id,
                    status=GenerationRunStatus.QUEUED.value,
                    triggered_by="auto",
                )
                session.add(run)
                session.flush()
                runs_to_queue.append((str(job.id), str(run.id), reason))

        # Queue after commit so GenerationRun rows are visible to workers
        for job_id, run_id, reason in runs_to_queue:
            generate_grounded_resume_task.delay(
                job_id,
                generation_run_id=run_id,
            )
            queued += 1
            metrics.increment("generation.queued", tags=["trigger:auto"])
            logger.info(
                "Queued auto-generation for job %s (reason=%s)",
                job_id,
                reason,
                extra={"job_id": job_id, "reason": reason},
            )

        metrics.increment("generation.gate.evaluated", value=len(jobs))
        logger.info(
            "Generation gate evaluated %s jobs, queued %s",
            len(jobs),
            queued,
            extra={"task_name": "evaluate_generation_gate"},
        )
        return {"evaluated": len(jobs), "queued": queued}
