import logging

from celery import Celery

from apps.api.settings import Settings
from core.logging_config import configure_logging

settings = Settings()
configure_logging(app_env=settings.app_env, level=settings.log_level)
logger = logging.getLogger(__name__)
logger.debug("Configuring Celery app with app_env=%s log_level=%s", settings.app_env, settings.log_level)

celery_app = Celery("jobbot")
celery_app.config_from_object(
    {
        "broker_url": settings.redis_url,
        "result_backend": settings.redis_url,
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "worker_hijack_root_logger": False,
        "task_routes": {
            "apps.worker.tasks.scrape.*": {"queue": "scrape"},
            "apps.worker.tasks.ingest.*": {"queue": "ingestion"},
            "apps.worker.tasks.score.*": {"queue": "default"},
            "apps.worker.tasks.ats_match.*": {"queue": "default"},
            "apps.worker.tasks.notify.*": {"queue": "default"},
        },
    }
)
celery_app.autodiscover_tasks(["apps.worker"])

from celery.signals import task_failure


def _on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
    """Record task failure for dead-letter visibility (EPIC 10)."""
    from core.observability.failures import record_task_failure

    retry_count = 0
    req = getattr(sender, "request", None)
    if req is not None:
        retry_count = getattr(req, "retries", 0) or 0
    record_task_failure(
        task_name=sender.name,
        args=args or (),
        kwargs=kwargs or {},
        error=str(exception),
        retries=retry_count,
        redis_url=settings.redis_url,
    )


task_failure.connect(_on_task_failure)
