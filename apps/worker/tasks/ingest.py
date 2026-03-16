"""Ingestion tasks for connector-based job fetching.

Runs connector fetch -> normalize -> persist flow, records run metadata and
item-level outcomes. Uses ScrapeRun for run tracking (source=connector name).
"""

from datetime import datetime, timezone
import json
import logging
from uuid import UUID

import redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from apps.api.settings import Settings
from core.connectors.base import CanonicalJobPayload
from core.connectors.greenhouse import create_greenhouse_connector
from core.dedup import canonicalize_apply_url, compute_dedup_hash, format_similarity_diagnostic
from core.db.models import Job, JobSourceRecord, ScrapeRun, ScrapeRunStatus
from core.db.session import get_sync_session

from apps.worker.celery_app import celery_app
from apps.worker.tasks.score import score_jobs
from apps.worker.tasks.classify import classify_jobs
from apps.worker.tasks.ats_match import ats_match_resume

from core.observability import with_log_context, get_metrics
from core.observability.metrics import TaskTimer

settings = Settings()
logger = logging.getLogger(__name__)


def _publish_log(level: str, message: str, run_id: str | None = None) -> None:
    """Publish log event to Redis for WebSocket streaming."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "task": "ingest_greenhouse",
        "message": message,
    }
    if run_id is not None:
        payload["run_id"] = run_id
    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.publish("jobbot:logs", json.dumps(payload))
        client.close()
    except Exception:
        logger.debug("Failed to publish ingestion log to Redis", exc_info=True)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    acks_late=True,
)
def ingest_greenhouse(
    self,
    run_id: str,
    board_token: str,
    company_name: str,
):
    """
    Fetch Greenhouse jobs, normalize, persist with run metadata.

    Creates ScrapeRun (source=greenhouse), fetches via connector, inserts
    Jobs and JobSourceRecords, records item-level outcomes in items_json.
    """
    with_log_context(run_id=run_id, source_name="greenhouse", task_name="ingest_greenhouse")
    metrics = get_metrics()

    if not settings.greenhouse_enabled:
        logger.info("Skipping Greenhouse ingest run_id=%s (greenhouse disabled)", run_id)
        return {"status": "skipped", "reason": "GREENHOUSE_ENABLED=false"}

    connector = create_greenhouse_connector(
        board_token=board_token.strip(),
        company_name=company_name.strip(),
    )
    logger.info(
        "Starting Greenhouse ingest run_id=%s board=%s company=%s",
        run_id,
        board_token,
        company_name,
    )
    _publish_log(
        "INFO",
        f"Greenhouse ingest started board={board_token} company={company_name}",
        run_id=run_id,
    )
    try:
        with TaskTimer("ingestion.latency", tags=["source:greenhouse"]):
            result = connector.fetch_raw_jobs(include_content=True)
    except Exception as e:
        metrics.increment("ingestion.failure", tags=["source:greenhouse"])
        logger.exception("Greenhouse fetch failed for run_id=%s", run_id)
        _publish_log("ERROR", f"Greenhouse fetch failed: {e}", run_id=run_id)
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            with get_sync_session() as session:
                run = session.get(ScrapeRun, UUID(run_id))
                if run:
                    run.status = ScrapeRunStatus.FAILED.value
                    run.finished_at = datetime.now(timezone.utc)
                    run.error_text = str(e)
                    run.stats_json = {"fetched": 0, "inserted": 0, "duplicates": 0, "errors": 1}
                    run.items_json = []
                    session.commit()
            raise

    if result.error:
        logger.error("Greenhouse fetch error run_id=%s error=%s", run_id, result.error)
        _publish_log("ERROR", f"Greenhouse fetch error: {result.error}", run_id=run_id)
        with get_sync_session() as session:
            run = session.get(ScrapeRun, UUID(run_id))
            if run:
                run.status = ScrapeRunStatus.FAILED.value
                run.finished_at = datetime.now(timezone.utc)
                run.error_text = result.error
                run.stats_json = {"fetched": 0, "inserted": 0, "duplicates": 0, "errors": 1}
                run.items_json = []
                session.commit()
        return {"run_id": run_id, "status": "FAILED", "error": result.error}

    inserted = 0
    duplicates = 0
    run_items: list[dict] = []

    with get_sync_session() as session:
        # Build exact URL lookup for strong duplicate signal (SPEC §9)
        apply_url_to_job_id: dict[str, UUID] = {}
        for row in session.execute(
            select(Job.id, Job.apply_url).where(Job.apply_url.isnot(None))
        ).all():
            job_id, apply_url = row[0], row[1]
            if apply_url:
                canonical_url = canonicalize_apply_url(apply_url)
                if canonical_url and canonical_url not in apply_url_to_job_id:
                    apply_url_to_job_id[canonical_url] = job_id

        for index, raw_with_prov in enumerate(result.raw_jobs, start=1):
            raw_job = raw_with_prov.raw_payload
            canonical = connector.normalize(raw_job)
            if canonical is None:
                run_items.append(
                    {
                        "index": index,
                        "outcome": "skipped",
                        "reason": "normalize_failed",
                        "external_id": str(raw_job.get("id", "")),
                    }
                )
                continue

            url_for_dedup = canonical.apply_url or canonical.source_url or ""
            canonical_apply_url = canonicalize_apply_url(url_for_dedup)
            dedup_hash = compute_dedup_hash(
                normalized_company=canonical.normalized_company,
                normalized_title=canonical.normalized_title,
                normalized_location=canonical.normalized_location or "",
                apply_url=url_for_dedup or None,
            )
            provenance = raw_with_prov.provenance

            # Strong exact signal: normalized apply URL match
            job_id_for_source: UUID | None = None
            inserted_job_id: UUID | None = None
            existing_job: tuple | None = None
            dedup_reason: str = "inserted"
            if canonical_apply_url and canonical_apply_url in apply_url_to_job_id:
                job_id_for_source = apply_url_to_job_id[canonical_apply_url]
                dedup_reason = "exact_url"
                existing_job = (job_id_for_source,)

            if job_id_for_source is None:
                stmt = (
                insert(Job)
                .values(
                    source="greenhouse",
                    source_job_id=canonical.external_id,
                    title=canonical.title,
                    raw_title=canonical.title,
                    normalized_title=canonical.normalized_title,
                    raw_company=canonical.company,
                    normalized_company=canonical.normalized_company,
                    company_name_raw=canonical.company,
                    raw_location=canonical.location,
                    normalized_location=canonical.normalized_location,
                    location=canonical.location,
                    url=canonical.source_url or canonical.apply_url or "",
                    apply_url=canonical.apply_url,
                    description=canonical.description,
                    posted_at=canonical.posted_at,
                    ats_type="greenhouse",
                    status="NEW",
                    user_status="NEW",
                    pipeline_status="INGESTED",
                    score_total=0.0,
                    source_payload_json=canonical.raw_payload,
                    dedup_hash=dedup_hash,
                )
                .on_conflict_do_nothing(index_elements=["dedup_hash"])
                .returning(Job.id)
            )
            inserted_job_id = session.execute(stmt).scalar_one_or_none()
            job_id_for_source = inserted_job_id
            existing_job = None
            if inserted_job_id is None:
                existing_job = (
                    session.execute(
                        select(Job.id).where(Job.dedup_hash == dedup_hash)
                    ).first()
                )
                if existing_job:
                    job_id_for_source = existing_job[0]
                    dedup_reason = "dedup_hash"

            if job_id_for_source is not None:
                ext_id = canonical.external_id
                provenance_meta = {
                    "fetch_timestamp": provenance.fetch_timestamp,
                    "source_url": provenance.source_url,
                    "connector_version": provenance.connector_version,
                }
                session.execute(
                    insert(JobSourceRecord)
                    .values(
                        job_id=job_id_for_source,
                        source_name="greenhouse",
                        external_id=ext_id,
                        raw_data=canonical.raw_payload,
                        provenance_metadata=provenance_meta,
                    )
                    .on_conflict_do_nothing(index_elements=["source_name", "external_id"])
                )

            if inserted_job_id is not None:
                inserted += 1
                if canonical_apply_url and job_id_for_source:
                    apply_url_to_job_id[canonical_apply_url] = job_id_for_source
                run_items.append(
                    {
                        "index": index,
                        "outcome": "inserted",
                        "dedup_reason": dedup_reason,
                        "job_id": str(inserted_job_id),
                        "dedup_hash": dedup_hash,
                        "external_id": canonical.external_id,
                        "title": canonical.title,
                        "company": canonical.company,
                        "location": canonical.location,
                        "apply_url": canonical.apply_url,
                    }
                )
            else:
                duplicates += 1
                existing_job_id = str(existing_job[0]) if existing_job else None
                # Fuzzy diagnostics only - never used for merge (v1)
                if existing_job and format_similarity_diagnostic(
                    canonical.company,
                    canonical.company,
                    canonical.title,
                    canonical.title,
                ):
                    logger.info(
                        "Dedup duplicate run_id=%s external_id=%s reason=%s existing_job_id=%s",
                        run_id,
                        canonical.external_id,
                        dedup_reason,
                        existing_job_id,
                    )
                run_items.append(
                    {
                        "index": index,
                        "outcome": "duplicate",
                        "dedup_reason": dedup_reason,
                        "job_id": existing_job_id,
                        "dedup_hash": dedup_hash,
                        "external_id": canonical.external_id,
                        "title": canonical.title,
                        "company": canonical.company,
                        "location": canonical.location,
                        "apply_url": canonical.apply_url,
                    }
                )

        run = session.get(ScrapeRun, UUID(run_id))
        if run:
            run.status = ScrapeRunStatus.SUCCESS.value
            run.finished_at = datetime.now(timezone.utc)
            run.stats_json = {
                "fetched": result.stats.get("fetched", 0),
                "inserted": inserted,
                "duplicates": duplicates,
                "errors": result.stats.get("errors", 0),
            }
            run.items_json = run_items
            session.commit()

    metrics.increment("jobs.ingested", value=inserted, tags=["source:greenhouse"])
    metrics.increment("duplicates.suppressed", value=duplicates, tags=["source:greenhouse"])
    logger.info(
        "Greenhouse ingest completed run_id=%s fetched=%s inserted=%s duplicates=%s",
        run_id,
        result.stats.get("fetched", 0),
        inserted,
        duplicates,
    )
    _publish_log(
        "INFO",
        f"Greenhouse ingest finished fetched={result.stats.get('fetched', 0)} inserted={inserted} duplicates={duplicates}",
        run_id=run_id,
    )
    (score_jobs.s() | classify_jobs.s() | ats_match_resume.si()).delay()
    logger.debug(
        "Queued post-ingest chain score_jobs -> classify_jobs -> ats_match_resume for run_id=%s",
        run_id,
    )
    return {
        "run_id": run_id,
        "status": "SUCCESS",
        "stats": {
            "fetched": result.stats.get("fetched", 0),
            "inserted": inserted,
            "duplicates": duplicates,
        },
    }
