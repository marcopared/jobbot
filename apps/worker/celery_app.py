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
            "apps.worker.tasks.score.*": {"queue": "default"},
            "apps.worker.tasks.ats_match.*": {"queue": "default"},
            "apps.worker.tasks.notify.*": {"queue": "default"},
        },
    }
)
celery_app.autodiscover_tasks(["apps.worker"])
