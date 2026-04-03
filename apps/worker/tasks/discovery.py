"""Discovery tasks for broad multi-company job fetching.

Runs discovery connector fetch -> normalize -> persist with source_role=discovery,
resolution_status=pending. Minimal provenance wiring. No auto-generation in this PR.
"""

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from apps.api.settings import Settings
from apps.worker.celery_app import celery_app
from apps.worker.tasks.run_helpers import mark_run_skipped
from apps.worker.tasks.ats_match import ats_match_resume
from apps.worker.tasks.classify import classify_jobs
from apps.worker.tasks.generation import evaluate_generation_gate
from apps.worker.tasks.score import score_jobs
from core.connectors.agg1 import create_agg1_connector
from core.connectors.base import CanonicalJobPayload, FetchResult
from core.connectors.serp import create_serp1_connector
from core.db.models import (
    Job,
    JobSourceRecord,
    ResolutionStatus,
    ScrapeRun,
    ScrapeRunStatus,
    SourceRole,
)
from core.db.session import get_sync_session
from core.dedup import canonicalize_apply_url, compute_dedup_hash
from core.ingestion import get_source_policy, source_registry
from core.ingestion.sources.base import SourceAdapter
from core.ingestion.types import AcquisitionBatch, AcquisitionRecord
from core.observability import get_metrics, log_context
from core.observability.metrics import TaskTimer
from core.run_items import make_run_item

settings = Settings()
logger = logging.getLogger(__name__)


def _compute_source_confidence(payload: CanonicalJobPayload, source_name: str) -> float:
    """Heuristic: base 0.5 + bonuses for description, apply_url, location."""
    score = 0.5
    if payload.description and len(payload.description) > 100:
        score += 0.2
    if payload.apply_url:
        score += 0.2
    if payload.location:
        score += 0.1
    # SERP1 must remain lower-confidence than AGG-1 in alpha semantics.
    if source_name == "serp1":
        return min(score, 0.69)
    return min(score, 1.0)


def _publish_discovery_log(level: str, message: str, run_id: str | None = None) -> None:
    """Publish log event to Redis for WebSocket streaming."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "task": "run_discovery",
        "message": message,
    }
    if run_id is not None:
        payload["run_id"] = run_id
    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.publish("jobbot:logs", json.dumps(payload))
        client.close()
    except Exception:
        logger.debug("Failed to publish discovery log to Redis", exc_info=True)


def _setting_name_for_feature_flag(flag_key: str | None) -> str | None:
    if not flag_key:
        return None
    return flag_key.lower()


def _source_disabled_reason(source_name: str) -> str | None:
    try:
        policy = get_source_policy(source_name)
    except KeyError:
        return None
    setting_name = _setting_name_for_feature_flag(policy.feature_flag_key)
    if not setting_name:
        return None
    if getattr(settings, setting_name, True):
        return None
    return f"{policy.feature_flag_key}=false"


def _skip_run_for_disabled_source(run_id: str, source_name: str) -> dict | None:
    reason = _source_disabled_reason(source_name)
    if reason is None:
        return None
    logger.info("Skipping %s discovery run_id=%s (%s)", source_name, run_id, reason)
    mark_run_skipped(run_id, reason)
    return {"status": "skipped", "reason": reason}


def _run_discovery_persist(
    run_id: str,
    source_name: str,
    connector,
    result: FetchResult,
) -> dict:
    """Persist discovery results with source_role=discovery, resolution_status=pending."""
    if result.error:
        with get_sync_session() as session:
            run = session.get(ScrapeRun, UUID(run_id))
            if run:
                run.status = ScrapeRunStatus.FAILED.value
                run.finished_at = datetime.now(timezone.utc)
                run.error_text = result.error
                run.stats_json = {
                    "fetched": 0,
                    "inserted": 0,
                    "duplicates": 0,
                    "errors": 1,
                }
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
                        source_job_id=str(raw_job.get("id", raw_job.get("url", ""))) or None,
                        title=raw_job.get("title"),
                        company_name=raw_job.get("company"),
                        location=raw_job.get("location"),
                        url=raw_job.get("url") or raw_job.get("redirect_url"),
                        apply_url=raw_job.get("redirect_url") or raw_job.get("url"),
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
            source_confidence = _compute_source_confidence(canonical, source_name)

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
                        source_job_id=canonical.external_id,
                        source_role=SourceRole.DISCOVERY.value,
                        source_confidence=source_confidence,
                        resolution_status=ResolutionStatus.PENDING.value,
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
                        ats_type="unknown",
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
                    existing_job = session.execute(
                        select(Job.id).where(Job.dedup_hash == dedup_hash)
                    ).first()
                    if existing_job:
                        job_id_for_source = existing_job[0]
                        dedup_reason = "dedup_hash"

            if job_id_for_source is not None:
                provenance_meta = {
                    "fetch_timestamp": provenance.fetch_timestamp,
                    "source_url": provenance.source_url,
                    "connector_version": provenance.connector_version,
                }
                session.execute(
                    insert(JobSourceRecord)
                    .values(
                        job_id=job_id_for_source,
                        source_name=source_name,
                        external_id=canonical.external_id,
                        raw_data=canonical.raw_payload,
                        provenance_metadata=provenance_meta,
                    )
                    .on_conflict_do_nothing(
                        index_elements=["source_name", "external_id"]
                    )
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
                        source_confidence=source_confidence,
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

    get_metrics().increment(
        "jobs.discovered", value=inserted, tags=[f"source:{source_name}"]
    )
    get_metrics().increment(
        "duplicates.suppressed", value=duplicates, tags=[f"source:{source_name}"]
    )
    if inserted_job_ids:
        (
            score_jobs.s(inserted_job_ids)
            | classify_jobs.s()
            | ats_match_resume.s()
            | evaluate_generation_gate.s()
        ).delay()
    return {
        "run_id": run_id,
        "status": "SUCCESS",
        "stats": {
            "fetched": result.stats.get("fetched", 0),
            "inserted": inserted,
            "duplicates": duplicates,
        },
    }


def _finalize_failed_run(run_id: str, *, source_name: str, error: str) -> dict:
    with get_sync_session() as session:
        run = session.get(ScrapeRun, UUID(run_id))
        if run:
            run.status = ScrapeRunStatus.FAILED.value
            run.finished_at = datetime.now(timezone.utc)
            run.error_text = error
            run.stats_json = {
                "fetched": 0,
                "inserted": 0,
                "duplicates": 0,
                "errors": 1,
            }
            run.items_json = []
            session.commit()
    return {"run_id": run_id, "status": "FAILED", "error": error}


def _run_source_adapter_persist(
    run_id: str,
    *,
    source_name: str,
    source_adapter: SourceAdapter,
    result: AcquisitionBatch,
) -> dict:
    if result.error and not result.records:
        return _finalize_failed_run(run_id, source_name=source_name, error=result.error)

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

        for index, acquired in enumerate(result.records, start=1):
            canonical = source_adapter.normalize(acquired)
            raw_payload = acquired.raw_payload if isinstance(acquired, AcquisitionRecord) else {}
            raw_source_job_id = None
            if isinstance(raw_payload, dict):
                raw_source_job_id = raw_payload.get("external_id")

            if canonical is None:
                run_items.append(
                    make_run_item(
                        index=index,
                        outcome="skipped",
                        job_id=None,
                        dedup_hash=None,
                        source=source_name,
                        source_job_id=str(raw_source_job_id) if raw_source_job_id else None,
                        title=raw_payload.get("title") if isinstance(raw_payload, dict) else None,
                        company_name=raw_payload.get("company") if isinstance(raw_payload, dict) else None,
                        location=raw_payload.get("location") if isinstance(raw_payload, dict) else None,
                        url=raw_payload.get("source_url") if isinstance(raw_payload, dict) else None,
                        apply_url=raw_payload.get("apply_url") if isinstance(raw_payload, dict) else None,
                        ats_type=source_name,
                        raw_payload_json=raw_payload,
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
            provenance = acquired.provenance
            source_confidence = _compute_source_confidence(canonical, source_name)

            job_id_for_source: UUID | None = None
            inserted_job_id: UUID | None = None
            existing_job: tuple | None = None
            dedup_reason = "inserted"
            if canonical_apply_url and canonical_apply_url in apply_url_to_job_id:
                job_id_for_source = apply_url_to_job_id[canonical_apply_url]
                dedup_reason = "exact_url"
                existing_job = (job_id_for_source,)

            if job_id_for_source is None:
                stmt = (
                    insert(Job)
                    .values(
                        source=source_name,
                        source_job_id=canonical.external_id,
                        source_role=SourceRole.DISCOVERY.value,
                        source_confidence=source_confidence,
                        resolution_status=ResolutionStatus.PENDING.value,
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
                        ats_type="unknown",
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
                if inserted_job_id is None:
                    existing_job = session.execute(
                        select(Job.id).where(Job.dedup_hash == dedup_hash)
                    ).first()
                    if existing_job:
                        job_id_for_source = existing_job[0]
                        dedup_reason = "dedup_hash"

            if job_id_for_source is not None:
                provenance_meta = {
                    "fetch_timestamp": provenance.fetch_timestamp,
                    "source_url": provenance.source_url,
                    "connector_version": provenance.connector_version,
                    "capture_metadata": dict(acquired.capture_metadata or {}),
                    "debug_metadata": dict(acquired.debug_metadata or {}),
                }
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
                        source_confidence=source_confidence,
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
            run.error_text = result.error
            session.commit()

    get_metrics().increment("jobs.discovered", value=inserted, tags=[f"source:{source_name}"])
    get_metrics().increment("duplicates.suppressed", value=duplicates, tags=[f"source:{source_name}"])
    if inserted_job_ids:
        (
            score_jobs.s(inserted_job_ids)
            | classify_jobs.s()
            | ats_match_resume.s()
            | evaluate_generation_gate.s()
        ).delay()
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
def run_discovery(
    self,
    run_id: str,
    connector: str,
    query: str | None = None,
    location: str | None = None,
    results_per_page: int = 20,
    distance: int | None = None,
    max_days_old: int | None = None,
    sort_by: str | None = "date",
    salary_min: int | None = None,
    salary_max: int | None = None,
    full_time: bool | None = None,
    part_time: bool | None = None,
    contract: bool | None = None,
    permanent: bool | None = None,
    category: str | None = None,
    max_pages: int | None = None,
    max_results: int | None = None,
):
    """
    Run broad discovery via AGG-1 or SERP1 connector.

    Persists with source_role=discovery, resolution_status=pending.
    Chains to score -> classify -> ats_match. No auto-generation in this PR.
    """
    with log_context(run_id=run_id, source_name=connector, task_name="run_discovery"):
        if connector == "agg1":
            if not settings.enable_agg1_discovery:
                logger.info(
                    "Skipping AGG-1 discovery run_id=%s (ENABLE_AGG1_DISCOVERY=false)",
                    run_id,
                )
                mark_run_skipped(run_id, "ENABLE_AGG1_DISCOVERY=false")
                return {"status": "skipped", "reason": "ENABLE_AGG1_DISCOVERY=false"}
            conn = create_agg1_connector(
                app_id=settings.adzuna_app_id or "",
                app_key=settings.adzuna_app_key or "",
                country=settings.adzuna_country or "us",
            )
        elif connector == "serp1":
            if not settings.enable_serp1_discovery:
                logger.info(
                    "Skipping SERP1 discovery run_id=%s (ENABLE_SERP1_DISCOVERY=false)",
                    run_id,
                )
                mark_run_skipped(run_id, "ENABLE_SERP1_DISCOVERY=false")
                return {"status": "skipped", "reason": "ENABLE_SERP1_DISCOVERY=false"}
            conn = create_serp1_connector()
        else:
            with get_sync_session() as session:
                run = session.get(ScrapeRun, UUID(run_id))
                if run:
                    run.status = ScrapeRunStatus.FAILED.value
                    run.finished_at = datetime.now(timezone.utc)
                    run.error_text = f"Unsupported discovery connector: {connector}"
                    run.stats_json = {
                        "fetched": 0,
                        "inserted": 0,
                        "duplicates": 0,
                        "errors": 1,
                    }
                    run.items_json = []
                    session.commit()
            return {
                "run_id": run_id,
                "status": "FAILED",
                "error": f"Unsupported connector: {connector}",
            }

        _publish_discovery_log(
            "INFO", f"Discovery started connector={connector}", run_id=run_id
        )
        try:
            with TaskTimer("discovery.latency", tags=[f"source:{connector}"]):
                if connector == "agg1":
                    result = conn.fetch_raw_jobs(
                        query=query or settings.default_search_query,
                        location=location or settings.default_location,
                        results_per_page=results_per_page,
                        distance=distance,
                        max_days_old=max_days_old,
                        sort_by=sort_by or "date",
                        salary_min=salary_min,
                        salary_max=salary_max,
                        full_time=full_time,
                        part_time=part_time,
                        contract=contract,
                        permanent=permanent,
                        category=category,
                        max_pages=max_pages,
                        max_results=max_results,
                    )
                else:
                    result = conn.fetch_raw_jobs(
                        query=query or settings.default_search_query,
                        location=location or settings.default_location,
                    )
        except Exception as e:
            get_metrics().increment("discovery.failure", tags=[f"source:{connector}"])
            _publish_discovery_log(
                "ERROR", f"Discovery fetch failed: {e}", run_id=run_id
            )
            try:
                raise self.retry(exc=e)
            except self.MaxRetriesExceededError:
                with get_sync_session() as session:
                    run = session.get(ScrapeRun, UUID(run_id))
                    if run:
                        run.status = ScrapeRunStatus.FAILED.value
                        run.finished_at = datetime.now(timezone.utc)
                        run.error_text = str(e)
                        run.stats_json = {
                            "fetched": 0,
                            "inserted": 0,
                            "duplicates": 0,
                            "errors": 1,
                        }
                        run.items_json = []
                        session.commit()
                raise

        out = _run_discovery_persist(
            run_id=run_id,
            source_name=connector,
            connector=conn,
            result=result,
        )
        _publish_discovery_log(
            "INFO",
            f"Discovery finished connector={connector} fetched={result.stats.get('fetched', 0)} inserted={out.get('stats', {}).get('inserted', 0)}",
            run_id=run_id,
        )
        return out


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    acks_late=True,
)
def run_public_board_source(
    self,
    run_id: str,
    source_name: str,
    max_results: int | None = 25,
):
    with log_context(run_id=run_id, source_name=source_name, task_name="run_public_board_source"):
        skip_result = _skip_run_for_disabled_source(run_id, source_name)
        if skip_result is not None:
            return skip_result

        try:
            source_adapter = source_registry.create(source_name)
        except Exception as exc:
            return _finalize_failed_run(
                run_id,
                source_name=source_name,
                error=f"Unsupported public-board source: {source_name} ({exc})",
            )

        _publish_discovery_log(
            "INFO",
            f"Public-board discovery started source={source_name}",
            run_id=run_id,
        )
        try:
            with TaskTimer("discovery.latency", tags=[f"source:{source_name}"]):
                result = source_adapter.acquire(max_results=max_results or 25)
        except Exception as exc:
            get_metrics().increment("discovery.failure", tags=[f"source:{source_name}"])
            _publish_discovery_log(
                "ERROR",
                f"Public-board acquisition failed source={source_name}: {exc}",
                run_id=run_id,
            )
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return _finalize_failed_run(run_id, source_name=source_name, error=str(exc))

        output = _run_source_adapter_persist(
            run_id,
            source_name=source_name,
            source_adapter=source_adapter,
            result=result,
        )
        _publish_discovery_log(
            "INFO",
            f"Public-board discovery finished source={source_name} fetched={result.stats.get('fetched', 0)} inserted={output.get('stats', {}).get('inserted', 0)}",
            run_id=run_id,
        )
        return output
