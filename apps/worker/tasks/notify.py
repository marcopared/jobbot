import logging

from apps.worker.celery_app import celery_app
from core.notify import get_notifier

logger = logging.getLogger(__name__)


@celery_app.task
def send_notification(title: str, message: str, url: str | None = None):
    """Send push notification via configured provider."""
    notifier = get_notifier()
    ok = notifier.send(title=title, message=message, url=url)
    if not ok:
        logger.warning("Notification failed: title=%s", title)
    return {"sent": ok}
