import logging

from apps.browser.runner import apply_job as browser_apply_job
from apps.worker.celery_app import celery_app
from core.db.session import get_sync_session

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=120)
def apply_job(self, job_id: str):
    """Prepare resume, launch Playwright, attempt application."""
    with get_sync_session() as session:
        result = browser_apply_job(session=session, job_id=job_id)
        logger.info("apply_job result for job_id=%s: %s", job_id, result)
        return result
