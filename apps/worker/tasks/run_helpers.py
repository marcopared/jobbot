"""Shared helpers for ScrapeRun lifecycle management."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from core.db.models import ScrapeRun, ScrapeRunStatus
from core.db.session import get_sync_session

logger = logging.getLogger(__name__)


def mark_run_skipped(run_id: str, reason: str) -> None:
    """Mark a ScrapeRun as SKIPPED with the given reason.

    Called when a task exits early due to a disabled feature flag or source.
    """
    with get_sync_session() as session:
        run = session.get(ScrapeRun, UUID(run_id))
        if run:
            run.status = ScrapeRunStatus.SKIPPED.value
            run.finished_at = datetime.now(timezone.utc)
            run.error_text = reason
            run.stats_json = {"fetched": 0, "inserted": 0, "duplicates": 0, "errors": 0}
            run.items_json = []
            session.commit()
        else:
            logger.warning("mark_run_skipped: ScrapeRun %s not found", run_id)
