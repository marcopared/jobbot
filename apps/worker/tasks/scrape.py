from datetime import datetime, timezone
import json
import logging

import redis
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert

from apps.api.settings import Settings
from core.db.models import (
    Company,
    Job,
    ScrapeRun,
    ScrapeRunStatus,
)
from core.db.session import get_sync_session
from core.scraping.base import (
    compute_dedup_hash,
    detect_ats_type,
)
from core.scraping.jobspy_scraper import JobSpyScraper
from core.scraping.base import ScrapeParams

from apps.worker.celery_app import celery_app
from apps.worker.tasks.score import score_jobs
from apps.worker.tasks.ats_match import ats_match_resume

settings = Settings()
logger = logging.getLogger(__name__)


def _publish_log(level: str, message: str, run_id: str | None = None) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "task": "scrape_jobspy",
        "message": message,
    }
    if run_id is not None:
        payload["run_id"] = run_id
    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.publish("jobbot:logs", json.dumps(payload))
        client.close()
    except Exception:
        # Logging stream is best-effort only.
        logger.debug("Failed to publish scrape log payload to Redis", exc_info=True)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def scrape_jobspy(
    self,
    run_id: str,
    query: str | None = None,
    location: str | None = None,
    hours_old: int | None = None,
    results_wanted: int | None = None,
):
    """Scrape JobSpy sources, store jobs in DB, update scrape_run record."""
    from uuid import UUID

    params = ScrapeParams(
        query=query or settings.default_search_query,
        location=location or settings.default_location,
        hours_old=hours_old if hours_old is not None else settings.scrape_hours_old,
        results_wanted=results_wanted
        if results_wanted is not None
        else settings.scrape_results_wanted,
    )
    if not settings.jobspy_enabled:
        logger.info("Skipping scrape run_id=%s because jobspy is disabled", run_id)
        return {"status": "skipped", "reason": "JOBSPY_ENABLED=false"}
    scraper = JobSpyScraper()
    logger.info(
        "Starting scrape run_id=%s query=%s location=%s hours_old=%s results_wanted=%s",
        run_id,
        params.query,
        params.location,
        params.hours_old,
        params.results_wanted,
    )
    _publish_log(
        "INFO",
        f"Scrape started query='{params.query}' location='{params.location}'",
        run_id=run_id,
    )
    try:
        result = scraper.scrape(params)
    except Exception as e:
        logger.exception("Unhandled scraper exception for run_id=%s", run_id)
        _publish_log("ERROR", f"Scrape crashed: {e}", run_id=run_id)
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
        logger.error("Scrape finished with error run_id=%s error=%s", run_id, result.error)
        _publish_log("ERROR", f"Scrape failed: {result.error}", run_id=run_id)
        with get_sync_session() as session:
            run = session.get(ScrapeRun, UUID(run_id))
            if run:
                run.status = ScrapeRunStatus.FAILED.value
                run.finished_at = datetime.now(timezone.utc)
                run.error_text = result.error
                run.stats_json = {
                    "fetched": result.stats.get("fetched", 0),
                    "inserted": 0,
                    "duplicates": 0,
                    "errors": result.stats.get("errors", 1),
                }
                run.items_json = []
                session.commit()
        return {"run_id": str(run_id), "status": "FAILED", "error": result.error}
    inserted = 0
    duplicates = 0
    run_items: list[dict] = []
    with get_sync_session() as session:
        session.execute(
            text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_payload_json JSONB")
        )
        session.execute(
            text("ALTER TABLE scrape_runs ADD COLUMN IF NOT EXISTS items_json JSONB")
        )
        for index, nj in enumerate(result.jobs, start=1):
            url_for_dedup = nj.apply_url or nj.url
            dedup_hash = compute_dedup_hash(nj.title, nj.company_name, url_for_dedup)
            ats_type = detect_ats_type(url_for_dedup)
            company_id = None
            company = (
                session.execute(select(Company).where(Company.name == nj.company_name))
                .scalars()
                .first()
            )
            if company:
                company_id = company.id
            else:
                company = Company(name=nj.company_name)
                session.add(company)
                session.flush()
                company_id = company.id
            stmt = (
                insert(Job)
                .values(
                source=nj.source.value,
                source_job_id=nj.source_job_id,
                title=nj.title,
                company_id=company_id,
                company_name_raw=nj.company_name,
                location=nj.location,
                remote_flag=nj.remote_flag,
                url=nj.url,
                apply_url=nj.apply_url,
                description=nj.description,
                salary_min=nj.salary_min,
                salary_max=nj.salary_max,
                posted_at=nj.posted_at,
                ats_type=ats_type.value,
                status="NEW",
                score_total=0.0,
                source_payload_json=nj.raw_payload,
                dedup_hash=dedup_hash,
            )
                .on_conflict_do_nothing(index_elements=["dedup_hash"])
                .returning(Job.id)
            )
            inserted_job_id = session.execute(stmt).scalar_one_or_none()
            if inserted_job_id is not None:
                inserted += 1
                run_items.append(
                    {
                        "index": index,
                        "outcome": "inserted",
                        "job_id": str(inserted_job_id),
                        "dedup_hash": dedup_hash,
                        "source": nj.source.value,
                        "source_job_id": nj.source_job_id,
                        "title": nj.title,
                        "company_name": nj.company_name,
                        "location": nj.location,
                        "url": nj.url,
                        "apply_url": nj.apply_url,
                        "ats_type": ats_type.value,
                        "raw_payload_json": nj.raw_payload,
                    }
                )
            else:
                duplicates += 1
                existing_job = (
                    session.execute(
                        select(Job.id, Job.source_payload_json, Job.apply_url).where(
                            Job.dedup_hash == dedup_hash
                        )
                    )
                    .first()
                )
                existing_job_id = str(existing_job[0]) if existing_job is not None else None
                had_payload = bool(existing_job and existing_job[1])
                had_apply_url = bool(existing_job and existing_job[2])
                backfilled_payload = False
                backfilled_apply_url = False
                if existing_job is not None and not had_payload and nj.raw_payload:
                    session.execute(
                        update(Job)
                        .where(Job.id == existing_job[0])
                        .values(source_payload_json=nj.raw_payload)
                    )
                    backfilled_payload = True
                if existing_job is not None and not had_apply_url and nj.apply_url:
                    session.execute(
                        update(Job)
                        .where(Job.id == existing_job[0])
                        .values(apply_url=nj.apply_url)
                    )
                    backfilled_apply_url = True
                run_items.append(
                    {
                        "index": index,
                        "outcome": "duplicate",
                        "job_id": existing_job_id,
                        "dedup_hash": dedup_hash,
                        "source": nj.source.value,
                        "source_job_id": nj.source_job_id,
                        "title": nj.title,
                        "company_name": nj.company_name,
                        "location": nj.location,
                        "url": nj.url,
                        "apply_url": nj.apply_url,
                        "ats_type": ats_type.value,
                        "backfilled_payload": backfilled_payload,
                        "backfilled_apply_url": backfilled_apply_url,
                        "raw_payload_json": nj.raw_payload,
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
    logger.info(
        "Scrape completed run_id=%s fetched=%s inserted=%s duplicates=%s errors=%s",
        run_id,
        result.stats.get("fetched", 0),
        inserted,
        duplicates,
        result.stats.get("errors", 0),
    )
    _publish_log(
        "INFO",
        f"Scrape finished fetched={result.stats.get('fetched', 0)} inserted={inserted} duplicates={duplicates}",
        run_id=run_id,
    )
    (score_jobs.s() | ats_match_resume.si()).delay()
    logger.debug("Queued post-scrape chain score_jobs -> ats_match_resume for run_id=%s", run_id)
    return {
        "run_id": str(run_id),
        "status": "SUCCESS",
        "stats": {"fetched": result.stats.get("fetched", 0), "inserted": inserted, "duplicates": duplicates},
    }
