from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.deps import get_db
from apps.api.schemas import (
    ArtifactItem,
    ArtifactsResponse,
    ATSGaps,
    GenerateResumeResponse,
    JobDetailResponse,
    JobListItem,
    JobListResponse,
    PersonaInfo,
    ScoreBreakdown,
    UpdateStatusRequest,
    UpdateStatusResponse,
)
from apps.api.settings import Settings
from apps.worker.tasks.scrape import scrape_jobspy
from apps.worker.tasks.ingest import ingest_greenhouse
from apps.worker.tasks.resume import generate_grounded_resume_task
from core.db.models import Artifact, Job, JobAnalysis, PipelineStatus, ScrapeRun, ScrapeRunStatus, UserStatus
from core.job_status import legacy_status_from_canonical

settings = Settings()

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _job_to_list_item(j: Job) -> JobListItem:
    """Build list item from Job (expects analyses and artifacts loaded)."""
    persona = None
    if j.analyses:
        persona = j.analyses[0].matched_persona
    artifact_availability = any(
        a.generation_status == "success" or (a.file_url or a.path)
        for a in (j.artifacts or [])
    )
    return JobListItem(
        id=str(j.id),
        title=j.normalized_title or j.title or "",
        company=j.normalized_company or j.company_name_raw or "",
        location=j.normalized_location or j.location,
        score=j.score_total or 0.0,
        persona=persona,
        pipeline_status=j.pipeline_status or "INGESTED",
        user_status=j.user_status or "NEW",
        artifact_availability=artifact_availability,
        source=j.source or None,
    )


def _build_score_breakdown(j: Job) -> ScoreBreakdown | None:
    b = j.score_breakdown_json or {}
    if not b:
        return None
    return ScoreBreakdown(
        title_relevance=b.get("title_relevance"),
        seniority_fit=b.get("seniority_fit"),
        domain_alignment=b.get("domain_alignment"),
        tech_stack=b.get("tech_stack"),
        location_remote=b.get("location_remote"),
        weights=b.get("weights"),
        raw=b if isinstance(b, dict) else None,
    )


def _build_ats_gaps(j: Job, analysis: JobAnalysis | None) -> ATSGaps | None:
    if analysis:
        return ATSGaps(
            missing_keywords=analysis.missing_keywords or [],
            found_keywords=analysis.found_keywords,
            ats_compatibility_score=analysis.ats_compatibility_score,
            raw=analysis.ats_categories if isinstance(analysis.ats_categories, dict) else None,
        )
    b = j.ats_match_breakdown_json or {}
    if not b and not (j.ats_match_score or j.ats_match_score == 0):
        return None
    return ATSGaps(
        missing_keywords=[],
        found_keywords=None,
        ats_compatibility_score=float(j.ats_match_score) if j.ats_match_score is not None else None,
        raw=b if isinstance(b, dict) else None,
    )


def _job_to_detail_response(j: Job, artifacts: list[Artifact]) -> JobDetailResponse:
    """Build detail response from Job (expects analyses loaded)."""
    analysis = j.analyses[0] if j.analyses else None
    persona = None
    if analysis:
        persona = PersonaInfo(
            matched_persona=analysis.matched_persona,
            persona_confidence=analysis.persona_confidence,
            persona_rationale=analysis.persona_rationale,
        )
    artifact_items = [
        ArtifactItem(
            id=str(a.id),
            kind=a.kind or "pdf",
            filename=a.filename or "resume.pdf",
            persona_name=a.persona_name,
            generation_status=a.generation_status,
            created_at=a.created_at.isoformat() if a.created_at else None,
            download_url=f"/api/artifacts/{a.id}/download",
            preview_url=f"/api/artifacts/{a.id}/preview",
        )
        for a in artifacts
    ]
    return JobDetailResponse(
        id=str(j.id),
        title=j.normalized_title or j.title or "",
        company=j.normalized_company or j.company_name_raw or "",
        location=j.normalized_location or j.location,
        description=j.description,
        url=j.url,
        apply_url=j.apply_url,
        source=j.source,
        score=j.score_total or 0.0,
        score_breakdown=_build_score_breakdown(j),
        ats_gaps=_build_ats_gaps(j, analysis),
        persona=persona,
        artifacts=artifact_items,
        pipeline_status=j.pipeline_status or "INGESTED",
        user_status=j.user_status or "NEW",
        created_at=j.created_at.isoformat() if j.created_at else None,
        updated_at=j.updated_at.isoformat() if j.updated_at else None,
        salary_min=j.salary_min,
        salary_max=j.salary_max,
        posted_at=j.posted_at.isoformat() if j.posted_at else None,
        remote_flag=j.remote_flag or False,
    )


class RunScrapeBody(BaseModel):
    query: Optional[str] = None
    location: Optional[str] = None
    hours_old: Optional[int] = None
    results_wanted: Optional[int] = None


class RunIngestionBody(BaseModel):
    connector: str  # "greenhouse" for v1
    board_token: str
    company_name: str


class BulkJobIds(BaseModel):
    job_ids: list[str]


@router.post("/run-ingestion")
async def run_ingestion(
    body: RunIngestionBody,
    db: AsyncSession = Depends(get_db),
):
    """Trigger connector-based ingestion (e.g. Greenhouse). Enqueues Celery task."""
    if body.connector != "greenhouse":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported connector: {body.connector}. Use 'greenhouse'.",
        )
    scrape_run = ScrapeRun(
        source="greenhouse",
        status=ScrapeRunStatus.RUNNING.value,
        params_json={
            "board_token": body.board_token,
            "company_name": body.company_name,
        },
    )
    db.add(scrape_run)
    await db.commit()
    await db.refresh(scrape_run)
    run_id = str(scrape_run.id)
    task = ingest_greenhouse.delay(
        run_id=run_id,
        board_token=body.board_token,
        company_name=body.company_name,
    )
    return {"run_id": run_id, "status": "RUNNING", "task_id": str(task.id)}


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


@router.post("/bulk-status")
async def bulk_status(body: BulkJobIds, status: str = Query(...), db: AsyncSession = Depends(get_db)):
    valid_statuses = {s.value for s in UserStatus}
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid user_status: {status}")
        
    updated = 0
    for jid in body.job_ids:
        result = await db.execute(select(Job).where(Job.id == jid))
        job = result.scalar_one_or_none()
        if not job:
            continue
        job.user_status = status
        job.status = legacy_status_from_canonical(job.pipeline_status, job.user_status)
        updated += 1
    await db.commit()
    return {"updated": updated}


@router.get("", response_model=JobListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    user_status: Optional[str] = Query(None, description="Filter by user_status"),
    status: Optional[str] = Query(None, description="Alias for user_status (backward compat)"),
    pipeline_status: Optional[str] = None,
    source: Optional[str] = None,
    persona: Optional[str] = Query(None, description="Filter by matched persona"),
    q: Optional[str] = Query(None, description="Search title/company"),
    min_score: Optional[float] = None,
    include_rejected: bool = Query(False, description="Include REJECTED jobs for debugging"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    sort_by: str = Query("score_total", description="Sort column (score_total, scraped_at, title)"),
    sort_dir: str = Query("desc"),
):
    """List jobs with pagination. Supports v1 manual-review workflow."""
    status_filter = user_status or status
    stmt = select(Job).options(
        selectinload(Job.analyses),
        selectinload(Job.artifacts),
    )
    count_stmt = select(func.count()).select_from(Job)
    if status_filter:
        stmt = stmt.where(Job.user_status == status_filter)
        count_stmt = count_stmt.where(Job.user_status == status_filter)
    if pipeline_status:
        stmt = stmt.where(Job.pipeline_status == pipeline_status)
        count_stmt = count_stmt.where(Job.pipeline_status == pipeline_status)
    elif not include_rejected:
        stmt = stmt.where(Job.pipeline_status != PipelineStatus.REJECTED.value)
        count_stmt = count_stmt.where(Job.pipeline_status != PipelineStatus.REJECTED.value)
    if source:
        stmt = stmt.where(Job.source == source)
        count_stmt = count_stmt.where(Job.source == source)
    if persona:
        stmt = stmt.join(JobAnalysis, Job.id == JobAnalysis.job_id).where(
            JobAnalysis.matched_persona == persona
        )
        count_stmt = count_stmt.join(
            JobAnalysis, Job.id == JobAnalysis.job_id
        ).where(JobAnalysis.matched_persona == persona)
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
    jobs = result.unique().scalars().all()
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    items = [_job_to_list_item(j) for j in jobs]
    return JobListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{job_id}")
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    debug: bool = Query(False, description="Include internal debug data (e.g. source_payload_json)"),
):
    """Retrieve full job details, analysis, scores, and artifact metadata."""
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.analyses), selectinload(Job.artifacts))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    artifacts = sorted(
        job.artifacts or [],
        key=lambda a: a.created_at.timestamp() if a.created_at else 0.0,
        reverse=True,
    )
    return _job_to_detail_response(job, artifacts)


@router.put("/{job_id}/status", response_model=UpdateStatusResponse)
async def update_job_status(
    job_id: UUID, body: UpdateStatusRequest, db: AsyncSession = Depends(get_db)
):
    """Update user workflow status (SAVED, APPLIED, ARCHIVED)."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    valid_statuses = {s.value for s in UserStatus}
    if body.user_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid user_status: {body.user_status}")
    job.user_status = body.user_status
    job.status = legacy_status_from_canonical(job.pipeline_status, job.user_status)
    await db.commit()
    await db.refresh(job)
    return UpdateStatusResponse(id=str(job.id), user_status=job.user_status)


@router.post("/{job_id}/generate-resume", response_model=GenerateResumeResponse)
async def trigger_generate_resume(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Trigger or regenerate tailored resume for a job. Enqueues Celery task."""
    result = await db.execute(
        select(Job).where(Job.id == job_id).options(selectinload(Job.analyses))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    task = generate_grounded_resume_task.delay(str(job_id))
    return GenerateResumeResponse(job_id=str(job_id), status="queued", task_id=str(task.id))


@router.get("/{job_id}/artifacts", response_model=ArtifactsResponse)
async def list_job_artifacts(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """List artifacts (resumes) for a job. Returns 404 if job does not exist."""
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    if not job_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Job not found")
    result = await db.execute(
        select(Artifact).where(Artifact.job_id == job_id).order_by(Artifact.created_at.desc())
    )
    artifacts = result.scalars().all()
    items = [
        ArtifactItem(
            id=str(a.id),
            kind=a.kind or "pdf",
            filename=a.filename or "resume.pdf",
            persona_name=a.persona_name,
            generation_status=a.generation_status,
            created_at=a.created_at.isoformat() if a.created_at else None,
            download_url=f"/api/artifacts/{a.id}/download",
            preview_url=f"/api/artifacts/{a.id}/preview",
        )
        for a in artifacts
    ]
    return ArtifactsResponse(items=items)