"""Debug endpoints: task failures, observability (EPIC 10)."""

from fastapi import APIRouter, Query

from apps.api.settings import Settings
from core.observability.failures import get_recent_failures

router = APIRouter(prefix="/api/debug", tags=["debug"])
settings = Settings()


@router.get("/failures")
async def list_failures(limit: int = Query(50, ge=1, le=100)):
    """Return recent task failures for diagnosability."""
    return {"items": get_recent_failures(settings.redis_url, limit=limit)}
