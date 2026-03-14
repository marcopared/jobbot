from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db
from core.db.models import (
    Intervention,
    InterventionStatus,
    Job,
    JobStatus,
)

router = APIRouter(prefix="/api/interventions", tags=["interventions"])


class ResolveBody(BaseModel):
    notes: Optional[str] = None


def _to_dict(i: Intervention) -> dict:
    return {
        "id": str(i.id),
        "job_id": str(i.job_id),
        "application_id": str(i.application_id) if i.application_id else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
        "status": i.status,
        "reason": i.reason,
        "last_url": i.last_url,
        "screenshot_artifact_id": (
            str(i.screenshot_artifact_id) if i.screenshot_artifact_id else None
        ),
        "html_artifact_id": str(i.html_artifact_id) if i.html_artifact_id else None,
        "notes": i.notes,
    }


@router.get("")
async def list_interventions(
    db: AsyncSession = Depends(get_db),
    status: str = Query(InterventionStatus.OPEN.value),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
):
    stmt = select(Intervention).where(Intervention.status == status)
    count_stmt = select(func.count()).select_from(Intervention).where(Intervention.status == status)
    stmt = stmt.order_by(Intervention.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar() or 0
    return {"items": [_to_dict(i) for i in items], "total": total, "page": page, "per_page": per_page}


@router.get("/{intervention_id}")
async def get_intervention(intervention_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Intervention).where(Intervention.id == intervention_id))
    intervention = result.scalar_one_or_none()
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervention not found")
    return _to_dict(intervention)


@router.post("/{intervention_id}/resolve")
async def resolve_intervention(
    intervention_id: UUID,
    body: ResolveBody | None = None,
    db: AsyncSession = Depends(get_db),
):
    intervention = (
        await db.execute(select(Intervention).where(Intervention.id == intervention_id))
    ).scalar_one_or_none()
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervention not found")
    if intervention.status == InterventionStatus.RESOLVED.value:
        return {"id": str(intervention.id), "status": intervention.status}
    if intervention.status != InterventionStatus.OPEN.value:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {intervention.status} to RESOLVED",
        )

    intervention.status = InterventionStatus.RESOLVED.value
    intervention.resolved_at = datetime.now(UTC)
    if body and body.notes is not None:
        intervention.notes = body.notes
    await db.commit()
    await db.refresh(intervention)
    return {"id": str(intervention.id), "status": intervention.status}


@router.post("/{intervention_id}/abort")
async def abort_intervention(intervention_id: UUID, db: AsyncSession = Depends(get_db)):
    intervention = (
        await db.execute(select(Intervention).where(Intervention.id == intervention_id))
    ).scalar_one_or_none()
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervention not found")
    if intervention.status == InterventionStatus.ABORTED.value:
        return {"id": str(intervention.id), "status": intervention.status}
    if intervention.status != InterventionStatus.OPEN.value:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {intervention.status} to ABORTED",
        )

    job = (await db.execute(select(Job).where(Job.id == intervention.job_id))).scalar_one()
    intervention.status = InterventionStatus.ABORTED.value
    intervention.resolved_at = datetime.now(UTC)
    job.status = JobStatus.APPLY_FAILED.value
    await db.commit()
    await db.refresh(intervention)
    return {"id": str(intervention.id), "status": intervention.status}
