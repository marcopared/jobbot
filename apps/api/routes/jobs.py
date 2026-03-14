from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db
from apps.worker.tasks.scrape import scrape_jobspy
from core.db.models import Job, JobStatus, ScrapeRun, ScrapeRunStatus

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

APPROVE_FROM = {JobStatus.NEW.value, JobStatus.SCORED.value}
REJECT_FROM = {JobStatus.NEW.value, JobStatus.SCORED.value, JobStatus.APPROVED.value}
def _job_to_dict(j: Job) -> dict:
    return {
        "id": str(j.id),
        "title": j.title,
        "company_name_raw": j.company_name_raw,
        "source": j.source,
        "status": j.status,
        "score_total": j.score_total,
        "ats_match_score": j.ats_match_score,
        "location": j.location,
        "url": j.url,
        "apply_url": j.apply_url,
        "ats_type": j.ats_type,
        "remote_flag": j.remote_flag,
        "scraped_at": j.scraped_at.isoformat() if j.scraped_at else None,
    }


def _job_to_detail(j: Job) -> dict:
    d = _job_to_dict(j)
    d.update(
        {
            "description": j.description,
            "salary_min": j.salary_min,
            "salary_max": j.salary_max,
            "posted_at": j.posted_at.isoformat() if j.posted_at else None,
            "score_breakdown_json": j.score_breakdown_json,
            "ats_match_breakdown_json": j.ats_match_breakdown_json,
            "source_job_id": j.source_job_id,
            "source_payload_json": j.source_payload_json,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "updated_at": j.updated_at.isoformat() if j.updated_at else None,
        }
    )
    return d


class RunScrapeBody(BaseModel):
    query: Optional[str] = None
    location: Optional[str] = None
    hours_old: Optional[int] = None
    results_wanted: Optional[int] = None


class BulkJobIds(BaseModel):
    job_ids: list[str]


@router.post("/run-scrape")
async def run_scrape(
    body: RunScrapeBody | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a JobSpy scrape. Enqueues Celery task."""
    params = body.model_dump(exclude_none=True) if body else {}
    query = params.get("query")
    location = params.get("location")
    hours_old = params.get("hours_old")
    results_wanted = params.get("results_wanted")
    scrape_run = ScrapeRun(
        source="jobspy",
        status=ScrapeRunStatus.RUNNING.value,
        params_json=params or None,
    )
    db.add(scrape_run)
    await db.commit()
    await db.refresh(scrape_run)
    run_id = str(scrape_run.id)
    task = scrape_jobspy.delay(
        run_id=run_id,
        query=query,
        location=location,
        hours_old=hours_old,
        results_wanted=results_wanted,
    )
    return {"run_id": run_id, "status": "RUNNING", "task_id": str(task.id)}


@router.post("/bulk-approve")
async def bulk_approve(body: BulkJobIds, db: AsyncSession = Depends(get_db)):
    updated = 0
    for jid in body.job_ids:
        result = await db.execute(select(Job).where(Job.id == jid))
        job = result.scalar_one_or_none()
        if not job:
            continue
        if job.status in APPROVE_FROM:
            job.status = JobStatus.APPROVED.value
            updated += 1
    await db.commit()
    return {"updated": updated}


@router.post("/bulk-reject")
async def bulk_reject(body: BulkJobIds, db: AsyncSession = Depends(get_db)):
    updated = 0
    for jid in body.job_ids:
        result = await db.execute(select(Job).where(Job.id == jid))
        job = result.scalar_one_or_none()
        if not job:
            continue
        if job.status in REJECT_FROM:
            job.status = JobStatus.REJECTED.value
            updated += 1
    await db.commit()
    return {"updated": updated}


@router.get("")
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = None,
    source: Optional[str] = None,
    q: Optional[str] = Query(None, description="Search title/company"),
    min_score: Optional[float] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    sort_by: str = Query("scraped_at"),
    sort_dir: str = Query("desc"),
):
    """List jobs with pagination."""
    stmt = select(Job)
    count_stmt = select(func.count()).select_from(Job)
    if status:
        stmt = stmt.where(Job.status == status)
        count_stmt = count_stmt.where(Job.status == status)
    if source:
        stmt = stmt.where(Job.source == source)
        count_stmt = count_stmt.where(Job.source == source)
    if q:
        q_lower = f"%{q.lower()}%"
        filter_clause = (func.lower(Job.title).like(q_lower)) | (
            func.lower(Job.company_name_raw).like(q_lower)
        )
        stmt = stmt.where(filter_clause)
        count_stmt = count_stmt.where(filter_clause)
    if min_score is not None:
        stmt = stmt.where(Job.score_total >= min_score)
        count_stmt = count_stmt.where(Job.score_total >= min_score)
    sort_col = getattr(Job, sort_by, Job.scraped_at)
    if sort_dir == "asc":
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    items = [_job_to_dict(j) for j in jobs]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/{job_id}")
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_detail(job)


@router.post("/{job_id}/approve")
async def approve_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == JobStatus.APPROVED.value:
        return {"id": str(job.id), "status": job.status}
    if job.status not in APPROVE_FROM:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {job.status} to APPROVED",
        )
    job.status = JobStatus.APPROVED.value
    await db.commit()
    await db.refresh(job)
    return {"id": str(job.id), "status": job.status}


@router.post("/{job_id}/reject")
async def reject_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == JobStatus.REJECTED.value:
        return {"id": str(job.id), "status": job.status}
    if job.status not in REJECT_FROM:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {job.status} to REJECTED",
        )
    job.status = JobStatus.REJECTED.value
    await db.commit()
    await db.refresh(job)
    return {"id": str(job.id), "status": job.status}