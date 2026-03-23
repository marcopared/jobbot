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
from core.connectors.base import CanonicalJobPayload, FetchResult, RawJobWithProvenance
from core.connectors.ashby import create_ashby_connector
from core.connectors.greenhouse import create_greenhouse_connector
from core.connectors.lever import create_lever_connector
from core.connectors.url_provider import parse_supported_url
from core.dedup import canonicalize_apply_url, compute_dedup_hash, format_similarity_diagnostic
from core.db.models import Job, JobSourceRecord, ScrapeRun, ScrapeRunStatus, SourceRole
from core.db.session import get_sync_session

from apps.worker.celery_app import celery_app
from apps.worker.tasks.run_helpers import mark_run_skipped
from apps.worker.tasks.score import score_jobs
from apps.worker.tasks.classify import classify_jobs
from apps.worker.tasks.ats_match import ats_match_resume
from apps.worker.tasks.generation import evaluate_generation_gate

from core.observability import log_context, get_metrics
from core.observability.metrics import TaskTimer
from core.run_items import make_run_item

settings = Settings()
logger = logging.getLogger(__name__)


def _provider_disabled_reason(provider: str) -> str | None:
    """Return the feature-flag reason when a provider is disabled."""
    if provider == "greenhouse" and not settings.greenhouse_enabled:
        return "GREENHOUSE_ENABLED=false"
    if provider == "lever" and not settings.lever_enabled:
        return "LEVER_ENABLED=false"
    if provider == "ashby" and not settings.ashby_enabled:
        return "ASHBY_ENABLED=false"
    return None


def _skip_run_for_disabled_provider(run_id: str, provider: str) -> dict | None:
    """Persist a terminal SKIPPED run when the provider is disabled."""
    reason = _provider_disabled_reason(provider)
    if reason is None:
        return None
    logger.info("Skipping %s ingest run_id=%s (%s)", provider, run_id, reason)
    mark_run_skipped(run_id, reason)
    return {"status": "skipped", "reason": reason}


def _provider_slug_metadata(parsed) -> dict[str, str]:
    """Preserve provider-specific URL identifiers as metadata, not company."""
    metadata: dict[str, str] = {}
    if parsed.provider == "greenhouse" and parsed.board_token:
        metadata["board_token"] = parsed.board_token
    elif parsed.provider == "lever" and parsed.client_name:
        metadata["client_name"] = parsed.client_name
    elif parsed.provider == "ashby" and parsed.job_board_name:
        metadata["job_board_name"] = parsed.job_board_name
    return metadata


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
    with log_context(run_id=run_id, source_name="greenhouse", task_name="ingest_greenhouse"):
        metrics = get_metrics()

        skip_result = _skip_run_for_disabled_provider(run_id, "greenhouse")
        if skip_result is not None:
            return skip_result

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
    inserted_job_ids: list[str] = []
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
                    make_run_item(
                        index=index,
                        outcome="skipped",
                        job_id=None,
                        dedup_hash=None,
                        source="greenhouse",
                        source_job_id=str(raw_job.get("id", "")) or None,
                        title=raw_job.get("title"),
                        company_name=company_name,
                        location=None,
                        url=raw_job.get("absolute_url"),
                        apply_url=raw_job.get("absolute_url"),
                        ats_type="greenhouse",
                        raw_payload_json=raw_job,
                        reason="normalize_failed",
                    )
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
                inserted_job_ids.append(str(inserted_job_id))
                if canonical_apply_url and job_id_for_source:
                    apply_url_to_job_id[canonical_apply_url] = job_id_for_source
                run_items.append(
                    make_run_item(
                        index=index,
                        outcome="inserted",
                        job_id=str(inserted_job_id),
                        dedup_hash=dedup_hash,
                        source="greenhouse",
                        source_job_id=canonical.external_id,
                        title=canonical.title,
                        company_name=canonical.company,
                        location=canonical.location,
                        url=canonical.source_url or canonical.apply_url,
                        apply_url=canonical.apply_url,
                        ats_type="greenhouse",
                        raw_payload_json=canonical.raw_payload,
                        dedup_reason=dedup_reason,
                    )
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
                    make_run_item(
                        index=index,
                        outcome="duplicate",
                        job_id=existing_job_id,
                        dedup_hash=dedup_hash,
                        source="greenhouse",
                        source_job_id=canonical.external_id,
                        title=canonical.title,
                        company_name=canonical.company,
                        location=canonical.location,
                        url=canonical.source_url or canonical.apply_url,
                        apply_url=canonical.apply_url,
                        ats_type="greenhouse",
                        raw_payload_json=canonical.raw_payload,
                        dedup_reason=dedup_reason,
                    )
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
    if inserted_job_ids:
        (score_jobs.s(inserted_job_ids) | classify_jobs.s() | ats_match_resume.s() | evaluate_generation_gate.s()).delay()
    logger.debug(
        "Queued post-ingest chain score -> classify -> ats_match -> generation_gate for run_id=%s",
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


def _run_canonical_ingest(
    run_id: str,
    source_name: str,
    connector,
    result,
    task_name: str,
    source_role_override: SourceRole | None = None,
    provider_metadata: dict | None = None,
) -> dict:
    """
    Shared persist+chain logic for canonical connectors.
    Returns status dict. Caller handles fetch and error paths.
    """
    if result.error:
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
    inserted_job_ids: list[str] = []
    run_items: list[dict] = []

    with get_sync_session() as session:
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
                    make_run_item(
                        index=index,
                        outcome="skipped",
                        job_id=None,
                        dedup_hash=None,
                        source=source_name,
                        source_job_id=str(raw_job.get("id", raw_job.get("jobUrl", ""))) or None,
                        title=raw_job.get("title"),
                        company_name=raw_job.get("company"),
                        location=raw_job.get("location"),
                        url=raw_job.get("jobUrl") or raw_job.get("hostedUrl") or raw_job.get("absolute_url"),
                        apply_url=raw_job.get("jobUrl") or raw_job.get("hostedUrl") or raw_job.get("absolute_url"),
                        ats_type=source_name,
                        raw_payload_json=raw_job,
                        reason="normalize_failed",
                    )
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
                        source=source_name,
                        source_role=(source_role_override or SourceRole.CANONICAL).value,
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
                        ats_type=source_name,
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
                provenance_meta = {
                    "fetch_timestamp": provenance.fetch_timestamp,
                    "source_url": provenance.source_url,
                    "connector_version": provenance.connector_version,
                }
                if provider_metadata:
                    provenance_meta["provider_metadata"] = provider_metadata
                session.execute(
                    insert(JobSourceRecord)
                    .values(
                        job_id=job_id_for_source,
                        source_name=source_name,
                        external_id=canonical.external_id,
                        raw_data=canonical.raw_payload,
                        provenance_metadata=provenance_meta,
                    )
                    .on_conflict_do_nothing(index_elements=["source_name", "external_id"])
                )

            if inserted_job_id is not None:
                inserted += 1
                inserted_job_ids.append(str(inserted_job_id))
                if canonical_apply_url and job_id_for_source:
                    apply_url_to_job_id[canonical_apply_url] = job_id_for_source
                run_items.append(
                    make_run_item(
                        index=index,
                        outcome="inserted",
                        job_id=str(inserted_job_id),
                        dedup_hash=dedup_hash,
                        source=source_name,
                        source_job_id=canonical.external_id,
                        title=canonical.title,
                        company_name=canonical.company,
                        location=canonical.location,
                        url=canonical.source_url or canonical.apply_url,
                        apply_url=canonical.apply_url,
                        ats_type=source_name,
                        raw_payload_json=canonical.raw_payload,
                        dedup_reason=dedup_reason,
                    )
                )
            else:
                duplicates += 1
                existing_job_id = str(existing_job[0]) if existing_job else None
                run_items.append(
                    make_run_item(
                        index=index,
                        outcome="duplicate",
                        job_id=existing_job_id,
                        dedup_hash=dedup_hash,
                        source=source_name,
                        source_job_id=canonical.external_id,
                        title=canonical.title,
                        company_name=canonical.company,
                        location=canonical.location,
                        url=canonical.source_url or canonical.apply_url,
                        apply_url=canonical.apply_url,
                        ats_type=source_name,
                        raw_payload_json=canonical.raw_payload,
                        dedup_reason=dedup_reason,
                    )
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

    get_metrics().increment("jobs.ingested", value=inserted, tags=[f"source:{source_name}"])
    get_metrics().increment("duplicates.suppressed", value=duplicates, tags=[f"source:{source_name}"])
    if inserted_job_ids:
        (score_jobs.s(inserted_job_ids) | classify_jobs.s() | ats_match_resume.s() | evaluate_generation_gate.s()).delay()
    return {
        "run_id": run_id,
        "status": "SUCCESS",
        "stats": {
            "fetched": result.stats.get("fetched", 0),
            "inserted": inserted,
            "duplicates": duplicates,
        },
    }


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    acks_late=True,
)
def ingest_lever(self, run_id: str, client_name: str, company_name: str):
    """Fetch Lever jobs, normalize, persist. Same pipeline as Greenhouse."""
    with log_context(run_id=run_id, source_name="lever", task_name="ingest_lever"):
        skip_result = _skip_run_for_disabled_provider(run_id, "lever")
        if skip_result is not None:
            return skip_result
        connector = create_lever_connector(
            client_name=client_name.strip(),
            company_name=company_name.strip() or None,
        )
        _publish_log("INFO", f"Lever ingest started client={client_name}", run_id=run_id)
        try:
            with TaskTimer("ingestion.latency", tags=["source:lever"]):
                result = connector.fetch_raw_jobs()
        except Exception as e:
            get_metrics().increment("ingestion.failure", tags=["source:lever"])
            _publish_log("ERROR", f"Lever fetch failed: {e}", run_id=run_id)
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
        return _run_canonical_ingest(
            run_id=run_id,
            source_name="lever",
            connector=connector,
            result=result,
            task_name="ingest_lever",
        )


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    acks_late=True,
)
def ingest_ashby(self, run_id: str, job_board_name: str, company_name: str):
    """Fetch Ashby jobs, normalize, persist. Same pipeline as Greenhouse."""
    with log_context(run_id=run_id, source_name="ashby", task_name="ingest_ashby"):
        skip_result = _skip_run_for_disabled_provider(run_id, "ashby")
        if skip_result is not None:
            return skip_result
        connector = create_ashby_connector(
            job_board_name=job_board_name.strip(),
            company_name=company_name.strip() or None,
        )
        _publish_log("INFO", f"Ashby ingest started board={job_board_name}", run_id=run_id)
        try:
            with TaskTimer("ingestion.latency", tags=["source:ashby"]):
                result = connector.fetch_raw_jobs()
        except Exception as e:
            get_metrics().increment("ingestion.failure", tags=["source:ashby"])
            _publish_log("ERROR", f"Ashby fetch failed: {e}", run_id=run_id)
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
        return _run_canonical_ingest(
            run_id=run_id,
            source_name="ashby",
            connector=connector,
            result=result,
            task_name="ingest_ashby",
        )


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    acks_late=True,
)
def ingest_url(self, run_id: str, url: str):
    """Ingest single job from supported ATS URL. Fetches all, filters to match."""
    from core.connectors.base import FetchResult, RawJobWithProvenance

    with log_context(run_id=run_id, source_name="url_ingest", task_name="ingest_url"):
        if not settings.url_ingest_enabled:
            mark_run_skipped(run_id, "URL_INGEST_ENABLED=false")
            return {"status": "skipped", "reason": "URL_INGEST_ENABLED=false"}
        parsed = parse_supported_url(url)
        if parsed is None:
            with get_sync_session() as session:
                run = session.get(ScrapeRun, UUID(run_id))
                if run:
                    run.status = ScrapeRunStatus.FAILED.value
                    run.finished_at = datetime.now(timezone.utc)
                    run.error_text = "Unsupported job URL"
                    run.stats_json = {"fetched": 0, "inserted": 0, "duplicates": 0, "errors": 1}
                    run.items_json = []
                    session.commit()
            return {"run_id": run_id, "status": "FAILED", "error": "Unsupported job URL"}

        skip_result = _skip_run_for_disabled_provider(run_id, parsed.provider)
        if skip_result is not None:
            return skip_result

        if parsed.provider == "greenhouse":
            connector = create_greenhouse_connector(
                board_token=parsed.board_token or "",
                company_name=None,
            )
        elif parsed.provider == "lever":
            connector = create_lever_connector(
                client_name=parsed.client_name or "",
                company_name=None,
            )
        elif parsed.provider == "ashby":
            connector = create_ashby_connector(
                job_board_name=parsed.job_board_name or "",
                company_name=None,
            )
        else:
            with get_sync_session() as session:
                run = session.get(ScrapeRun, UUID(run_id))
                if run:
                    run.status = ScrapeRunStatus.FAILED.value
                    run.finished_at = datetime.now(timezone.utc)
                    run.error_text = "Unsupported provider"
                    run.stats_json = {"fetched": 0, "inserted": 0, "duplicates": 0, "errors": 1}
                    run.items_json = []
                    session.commit()
            return {"run_id": run_id, "status": "FAILED", "error": "Unsupported provider"}

        try:
            with TaskTimer("ingestion.latency", tags=["source:url_ingest"]):
                result = connector.fetch_raw_jobs()
        except Exception as e:
            get_metrics().increment("ingestion.failure", tags=["source:url_ingest"])
            _publish_log("ERROR", f"URL ingest fetch failed: {e}", run_id=run_id)
            with get_sync_session() as session:
                run = session.get(ScrapeRun, UUID(run_id))
                if run:
                    run.status = ScrapeRunStatus.FAILED.value
                    run.finished_at = datetime.now(timezone.utc)
                    run.error_text = str(e)
                    run.stats_json = {"fetched": 0, "inserted": 0, "duplicates": 0, "errors": 1}
                    run.items_json = []
                    session.commit()
            return {"run_id": run_id, "status": "FAILED", "error": str(e)}

        if result.error:
            return _run_canonical_ingest(
                run_id=run_id,
                source_name=parsed.provider,
                connector=connector,
                result=result,
                task_name="ingest_url",
                source_role_override=SourceRole.URL_INGEST,
                provider_metadata=_provider_slug_metadata(parsed),
            )

        # Filter to job matching URL
        matching: list = []
        for rw in result.raw_jobs:
            raw = rw.raw_payload
            if parsed.provider == "greenhouse":
                if str(raw.get("id")) == parsed.job_id:
                    matching.append(rw)
                    break
            elif parsed.provider == "lever":
                if raw.get("id") == parsed.job_id or (raw.get("hostedUrl") or "").rstrip("/").endswith(f"/{parsed.job_id}"):
                    matching.append(rw)
                    break
            elif parsed.provider == "ashby":
                job_url = raw.get("jobUrl") or ""
                if parsed.job_id in job_url or job_url.rstrip("/").endswith(f"/{parsed.job_slug}"):
                    matching.append(rw)
                    break

        filtered = FetchResult(
            raw_jobs=matching,
            stats={"fetched": len(matching), "errors": 0},
            error=None,
        )
        if not matching:
            with get_sync_session() as session:
                run = session.get(ScrapeRun, UUID(run_id))
                if run:
                    run.status = ScrapeRunStatus.FAILED.value
                    run.finished_at = datetime.now(timezone.utc)
                    run.error_text = "Job not found at URL"
                    run.stats_json = {"fetched": result.stats.get("fetched", 0), "inserted": 0, "duplicates": 0, "errors": 0}
                    run.items_json = [
                        make_run_item(
                            index=1,
                            outcome="skipped",
                            job_id=None,
                            dedup_hash=None,
                            source="url_ingest",
                            source_job_id=None,
                            title=None,
                            company_name=None,
                            location=None,
                            url=url,
                            apply_url=url,
                            ats_type=parsed.provider,
                            raw_payload_json={"reason": "job_not_found_at_url", "requested_url": url},
                            reason="job_not_found_at_url",
                        )
                    ]
                    session.commit()
            return {"run_id": run_id, "status": "FAILED", "error": "Job not found at URL"}

        return _run_canonical_ingest(
            run_id=run_id,
            source_name=parsed.provider,
            connector=connector,
            result=filtered,
            task_name="ingest_url",
            source_role_override=SourceRole.URL_INGEST,
            provider_metadata=_provider_slug_metadata(parsed),
        )


@celery_app.task(acks_late=True)
def manual_ingest_pipeline(job_ids: list[str]):
    """Kick off downstream pipeline for manually-ingested jobs."""
    if not job_ids:
        return {"status": "no_jobs"}
    (score_jobs.s(job_ids) | classify_jobs.s() | ats_match_resume.s() | evaluate_generation_gate.s()).delay()
    return {"status": "chained", "job_ids": job_ids}
