from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db
from core.db.models import Application, Job

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _application_to_dict(app: Application) -> dict:
    return {
        "id": str(app.id),
        "job_id": str(app.job_id),
        "started_at": app.started_at.isoformat() if app.started_at else None,
        "finished_at": app.finished_at.isoformat() if app.finished_at else None,
        "status": app.status,
        "method": app.method,
        "error_text": app.error_text,
        "fields_json": app.fields_json,
        "external_app_id": app.external_app_id,
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }


@router.get("")
async def list_applications(
    db: AsyncSession = Depends(get_db),
    job_id: Optional[UUID] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
):
    stmt = select(Application)
    count_stmt = select(func.count()).select_from(Application)

    if job_id:
        stmt = stmt.where(Application.job_id == job_id)
        count_stmt = count_stmt.where(Application.job_id == job_id)
    if status:
        stmt = stmt.where(Application.status == status)
        count_stmt = count_stmt.where(Application.status == status)

    stmt = stmt.order_by(Application.started_at.desc()).offset((page - 1) * per_page).limit(
        per_page
    )
    result = await db.execute(stmt)
    applications = result.scalars().all()

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    return {
        "items": [_application_to_dict(a) for a in applications],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{application_id}")
async def get_application(application_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Application, Job.title, Job.company_name_raw)
        .join(Job, Application.job_id == Job.id)
        .where(Application.id == application_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    application, job_title, company_name_raw = row
    payload = _application_to_dict(application)
    payload["job"] = {
        "id": str(application.job_id),
        "title": job_title,
        "company_name_raw": company_name_raw,
    }
    return payload
