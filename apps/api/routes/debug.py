"""Debug endpoints: task failures, observability (EPIC 10)."""

from fastapi import APIRouter, HTTPException, Query

from apps.api.settings import Settings
from core.observability.failures import get_recent_failures

router = APIRouter(prefix="/api/debug", tags=["debug"])
settings = Settings()


@router.get("/failures")
async def list_failures(limit: int = Query(50, ge=1, le=100)):
    """Return recent task failures for diagnosability. Requires DEBUG_ENDPOINTS_ENABLED=true."""
    if not settings.debug_endpoints_enabled:
        raise HTTPException(status_code=404, detail="Not Found")
    return {"items": get_recent_failures(settings.redis_url, limit=limit)}
