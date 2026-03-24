"""Resolution tasks for discovery-to-canonical enrichment.

When a discovery job's apply URL maps to Greenhouse, Lever, or Ashby,
fetches canonical data and enriches the job in place. Records resolution
attempts in job_resolution_attempts. Preserves provenance.
"""

import logging
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from core.connectors.ashby import create_ashby_connector
from core.connectors.greenhouse import create_greenhouse_connector
from core.connectors.lever import create_lever_connector
from core.connectors.url_provider import parse_supported_url
from core.db.models import (
    Job,
    JobResolutionAttempt,
    JobSourceRecord,
    PipelineStatus,
    ResolutionStatus,
)
from core.db.session import get_sync_session
from core.job_status import legacy_status_from_canonical

from apps.api.settings import Settings
from apps.worker.celery_app import celery_app
from apps.worker.tasks.ats_match import ats_match_resume
from apps.worker.tasks.classify import classify_jobs
from apps.worker.tasks.generation import evaluate_generation_gate
from apps.worker.tasks.score import score_jobs

from core.observability import log_context, get_metrics

settings = Settings()
logger = logging.getLogger(__name__)


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


def _create_connector_for_provider(parsed):
    """Create connector for parsed URL. Caller ensures parsed is not None."""
    if parsed.provider == "greenhouse":
        return create_greenhouse_connector(
            board_token=parsed.board_token or "",
            company_name=None,
        )
    if parsed.provider == "lever":
        return create_lever_connector(
            client_name=parsed.client_name or "",
            company_name=None,
        )
    if parsed.provider == "ashby":
        return create_ashby_connector(
            job_board_name=parsed.job_board_name or "",
            company_name=None,
        )
    return None


def _filter_matching_job(raw_jobs, parsed):
    """Filter raw_jobs to the one matching the parsed URL. Same logic as ingest_url."""
    matching = []
    for rw in raw_jobs:
        raw = rw.raw_payload
        if parsed.provider == "greenhouse":
            if str(raw.get("id")) == parsed.job_id:
                matching.append(rw)
                break
        elif parsed.provider == "lever":
            if raw.get("id") == parsed.job_id or (
                (raw.get("hostedUrl") or "").rstrip("/").endswith(f"/{parsed.job_id}")
            ):
                matching.append(rw)
                break
        elif parsed.provider == "ashby":
            job_url = raw.get("jobUrl") or ""
            if parsed.job_id in job_url or job_url.rstrip("/").endswith(
                f"/{parsed.job_slug or parsed.job_id}"
            ):
                matching.append(rw)
                break
    return matching


def _reset_for_reprocessing(job: Job) -> None:
    """Rewind a resolved discovery job so the standard downstream chain will rerun it."""
    job.pipeline_status = PipelineStatus.INGESTED.value
    job.status = legacy_status_from_canonical(job.pipeline_status, job.user_status)


@celery_app.task(bind=True, acks_late=True)
def resolve_discovery_job(self, job_id: str):
    """
    Resolve a discovery job to canonical ATS data when its URL maps to
    Greenhouse, Lever, or Ashby. Enriches the job in place, preserves provenance,
    records resolution attempts. Chains to score -> classify -> ats_match -> gate.
    """
    with log_context(job_id=job_id, task_name="resolve_discovery_job"):
        metrics = get_metrics()
        with get_sync_session() as session:
            job = session.get(Job, UUID(job_id))
            if not job:
                logger.warning("resolve_discovery_job job_id=%s not found", job_id)
                return {"status": "not_found", "job_id": job_id}

            if job.source_role != "discovery":
                logger.info(
                    "resolve_discovery_job job_id=%s source_role=%s not discovery, skipping",
                    job_id,
                    job.source_role,
                )
                return {"status": "no_op", "reason": "not_discovery"}

            if job.resolution_status == ResolutionStatus.RESOLVED_CANONICAL.value:
                logger.info(
                    "resolve_discovery_job job_id=%s already resolved, skipping",
                    job_id,
                )
                return {"status": "no_op", "reason": "already_resolved"}

            url_to_resolve = (job.apply_url or job.url or "").strip()
            if not url_to_resolve:
                attempt = JobResolutionAttempt(
                    job_id=job.id,
                    resolution_status=ResolutionStatus.FAILED.value,
                    failure_reason="no_url",
                )
                session.add(attempt)
                session.commit()
                metrics.increment("resolution.attempted", tags=["outcome:no_url"])
                return {"status": "failed", "reason": "no_url"}

            parsed = parse_supported_url(url_to_resolve)
            if parsed is None:
                attempt = JobResolutionAttempt(
                    job_id=job.id,
                    resolution_status=ResolutionStatus.FAILED.value,
                    failure_reason="unsupported_url",
                    canonical_url=url_to_resolve,
                )
                session.add(attempt)
                session.commit()
                metrics.increment("resolution.attempted", tags=["outcome:unsupported"])
                return {"status": "unsupported", "reason": "url_not_greenhouse_lever_ashby"}

            connector = _create_connector_for_provider(parsed)
            if not connector:
                attempt = JobResolutionAttempt(
                    job_id=job.id,
                    resolution_status=ResolutionStatus.FAILED.value,
                    failure_reason="connector_unavailable",
                    canonical_source_name=parsed.provider,
                    canonical_url=url_to_resolve,
                )
                session.add(attempt)
                session.commit()
                return {"status": "failed", "reason": "connector_unavailable"}

        try:
            result = connector.fetch_raw_jobs()
        except Exception as e:
            logger.exception("resolve_discovery_job job_id=%s fetch failed", job_id)
            with get_sync_session() as session:
                job = session.get(Job, UUID(job_id))
                if job:
                    attempt = JobResolutionAttempt(
                        job_id=job.id,
                        resolution_status=ResolutionStatus.FAILED.value,
                        failure_reason=str(e)[:500],
                        canonical_url=url_to_resolve,
                        canonical_source_name=parsed.provider,
                    )
                    session.add(attempt)
                    session.commit()
            metrics.increment("resolution.attempted", tags=["outcome:fetch_error"])
            return {"status": "failed", "reason": "fetch_error", "error": str(e)}

        matching = _filter_matching_job(result.raw_jobs, parsed)
        if not matching:
            with get_sync_session() as session:
                job = session.get(Job, UUID(job_id))
                if job:
                    attempt = JobResolutionAttempt(
                        job_id=job.id,
                        resolution_status=ResolutionStatus.FAILED.value,
                        failure_reason="job_not_found_at_url",
                        canonical_url=url_to_resolve,
                        canonical_source_name=parsed.provider,
                    )
                    session.add(attempt)
                    session.commit()
            metrics.increment("resolution.attempted", tags=["outcome:not_found"])
            return {"status": "failed", "reason": "job_not_found_at_url"}

        raw_with_prov = matching[0]
        canonical = connector.normalize(raw_with_prov.raw_payload)
        if canonical is None:
            with get_sync_session() as session:
                job = session.get(Job, UUID(job_id))
                if job:
                    attempt = JobResolutionAttempt(
                        job_id=job.id,
                        resolution_status=ResolutionStatus.FAILED.value,
                        failure_reason="normalize_failed",
                        canonical_url=url_to_resolve,
                        canonical_source_name=parsed.provider,
                    )
                    session.add(attempt)
                    session.commit()
            return {"status": "failed", "reason": "normalize_failed"}

        with get_sync_session() as session:
            job = session.get(Job, UUID(job_id))
            if not job:
                return {"status": "not_found", "job_id": job_id}

            job.description = canonical.description or job.description
            job.apply_url = canonical.apply_url or job.apply_url
            job.url = canonical.source_url or canonical.apply_url or job.url
            job.raw_title = canonical.title
            job.normalized_title = canonical.normalized_title
            job.raw_company = canonical.company
            job.normalized_company = canonical.normalized_company
            job.company_name_raw = canonical.company
            job.raw_location = canonical.location
            job.normalized_location = canonical.normalized_location
            job.location = canonical.location
            job.posted_at = canonical.posted_at
            job.ats_type = parsed.provider
            job.source_payload_json = canonical.raw_payload

            job.canonical_source_name = parsed.provider
            job.canonical_external_id = canonical.external_id
            job.canonical_url = canonical.source_url or canonical.apply_url
            job.resolution_status = ResolutionStatus.RESOLVED_CANONICAL.value
            job.resolution_confidence = 1.0
            job.source_confidence = 1.0

            # Rewind the job to INGESTED so the standard downstream chain
            # (score -> classify -> ats_match -> gate) performs a real
            # recomputation against the newly enriched canonical fields.
            _reset_for_reprocessing(job)

            provenance = raw_with_prov.provenance
            provenance_meta = {
                "fetch_timestamp": provenance.fetch_timestamp,
                "source_url": provenance.source_url,
                "connector_version": provenance.connector_version,
                "resolved_from_discovery_job_id": str(job.id),
            }
            provider_metadata = _provider_slug_metadata(parsed)
            if provider_metadata:
                provenance_meta["provider_metadata"] = provider_metadata
            session.execute(
                insert(JobSourceRecord)
                .values(
                    job_id=job.id,
                    source_name=parsed.provider,
                    external_id=canonical.external_id,
                    raw_data=canonical.raw_payload,
                    provenance_metadata=provenance_meta,
                )
                .on_conflict_do_nothing(index_elements=["source_name", "external_id"])
            )

            attempt = JobResolutionAttempt(
                job_id=job.id,
                resolution_status=ResolutionStatus.RESOLVED_CANONICAL.value,
                confidence=1.0,
                canonical_url=job.canonical_url,
                canonical_source_name=parsed.provider,
            )
            session.add(attempt)
            session.commit()
            inserted_job_ids = [str(job.id)]
            canonical_ext_id = canonical.external_id

        metrics.increment("resolution.resolved", tags=[f"source:{parsed.provider}"])
        logger.info(
            "resolve_discovery_job job_id=%s resolved to %s",
            job_id,
            parsed.provider,
        )
        (
            score_jobs.s(inserted_job_ids)
            | classify_jobs.s()
            | ats_match_resume.s()
            | evaluate_generation_gate.s()
        ).delay()
        return {
            "status": "resolved",
            "job_id": job_id,
            "canonical_source": parsed.provider,
            "canonical_external_id": canonical_ext_id,
        }
