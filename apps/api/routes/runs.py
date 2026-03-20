from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db
from core.db.models import ScrapeRun

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _run_to_dict(run: ScrapeRun) -> dict:
    items = run.items_json if isinstance(run.items_json, list) else []
    inserted = sum(1 for item in items if item.get("outcome") == "inserted")
    duplicates = sum(1 for item in items if item.get("outcome") == "duplicate")
    return {
        "id": str(run.id),
        "source": run.source,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "status": run.status,
        "params_json": run.params_json,
        "stats_json": run.stats_json,
        "item_counts": {
            "all": len(items),
            "inserted": inserted,
            "duplicates": duplicates,
        },
        "error_text": run.error_text,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.get("")
async def list_runs(
    db: AsyncSession = Depends(get_db),
    source: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
):
    stmt = select(ScrapeRun)
    count_stmt = select(func.count()).select_from(ScrapeRun)

    if source:
        stmt = stmt.where(ScrapeRun.source == source)
        count_stmt = count_stmt.where(ScrapeRun.source == source)
    if status:
        stmt = stmt.where(ScrapeRun.status == status)
        count_stmt = count_stmt.where(ScrapeRun.status == status)

    stmt = stmt.order_by(ScrapeRun.started_at.desc()).offset((page - 1) * per_page).limit(per_page)
    runs = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar() or 0

    return {"items": [_run_to_dict(r) for r in runs], "total": total, "page": page, "per_page": per_page}


@router.get("/{run_id}")
async def get_run(run_id: UUID, db: AsyncSession = Depends(get_db)):
    run = (await db.execute(select(ScrapeRun).where(ScrapeRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_to_dict(run)


@router.get("/{run_id}/items")
async def get_run_items(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    outcome: str | None = Query(None, pattern="^(inserted|duplicate)$"),
    q: str | None = Query(None, description="Search title/company/source"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
):
    run = (await db.execute(select(ScrapeRun).where(ScrapeRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    all_items = run.items_json if isinstance(run.items_json, list) else []
    filtered: list[dict] = []
    q_lower = q.lower() if q else None
    for item in all_items:
        if not isinstance(item, dict):
            continue
        if outcome and item.get("outcome") != outcome:
            continue
        if q_lower:
            haystack = " ".join(
                [
                    str(item.get("title", "")),
                    str(item.get("company_name", "") or item.get("company", "")),
                    str(item.get("source", "")),
                ]
            ).lower()
            if q_lower not in haystack:
                continue
        filtered.append(item)

    filtered.sort(key=lambda i: int(i.get("index", 0)))
    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = filtered[start:end]
    inserted = sum(1 for item in all_items if isinstance(item, dict) and item.get("outcome") == "inserted")
    duplicates = sum(
        1 for item in all_items if isinstance(item, dict) and item.get("outcome") == "duplicate"
    )
    return {
        "items": page_items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "counts": {
            "all": len(all_items),
            "inserted": inserted,
            "duplicates": duplicates,
        },
    }
