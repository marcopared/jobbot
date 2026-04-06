from datetime import datetime, timezone
from typing import Literal, Optional
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
    ManualIngestBody,
    ManualIngestResponse,
    PersonaInfo,
    ResolveJobResponse,
    ScoreBreakdown,
    SourceAdapterCapabilitiesResponse,
    SourceAdapterCapability,
    SourceAdapterRunBody,
    SourceAdapterRunResponse,
    UpdateStatusRequest,
    UpdateStatusResponse,
)
from apps.api.settings import Settings
from apps.worker.tasks.discovery import (
    run_auth_board_source,
    run_discovery,
    run_public_board_source,
)
from apps.worker.tasks.generation_runs import build_generation_run
from apps.worker.tasks.ingest import (
    ingest_ashby,
    ingest_greenhouse,
    ingest_lever,
    ingest_url,
    manual_ingest_pipeline,
)
from apps.worker.tasks.resolution import resolve_discovery_job
from apps.worker.tasks.resume import generate_grounded_resume_task
from apps.worker.tasks.scrape import scrape_jobspy
from core.connectors.url_provider import parse_supported_url
from core.dedup import compute_dedup_hash, normalize_company, normalize_location, normalize_title
from core.db.models import (
    Artifact,
    Job,
    JobAnalysis,
    PipelineStatus,
    ResolutionStatus,
    ScrapeRun,
    ScrapeRunStatus,
    SourceRole,
    UserStatus,
)
from core.ingestion.registry import build_default_source_registry
from core.ingestion.source_policies import SOURCE_POLICIES, get_source_policy
from core.ingestion.sources.public_boards.common import UnsupportedPublicBoardSourceAdapter
from core.ingestion.types import BackendPreference, SourceKind
from core.job_status import legacy_status_from_canonical
from core.run_items import make_run_item

settings = Settings()
source_registry = build_default_source_registry()

# User workflow: NEW is the initial state; clients may only set SAVED, APPLIED, ARCHIVED.
WRITABLE_USER_STATUSES = frozenset(
    {UserStatus.SAVED.value, UserStatus.APPLIED.value, UserStatus.ARCHIVED.value}
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

SOURCE_LABELS: dict[str, str] = {
    "builtin_nyc": "Built In NYC",
    "greycroft": "Greycroft",
    "linkedin_jobs": "LinkedIn Jobs",
    "primary_vc": "Primary Venture Partners",
    "startupjobs_nyc": "StartupJobs NYC",
    "technyc": "Tech:NYC",
    "trueup": "TrueUp",
    "underdog": "Underdog",
    "usv": "USV",
    "ventureloop": "VentureLoop",
    "wellfound": "Wellfound",
    "welcome_to_the_jungle": "Welcome to the Jungle",
    "yc": "Work at a Startup (YC)",
}

PORTFOLIO_BOARD_SOURCES = {
    "technyc",
    "primary_vc",
    "greycroft",
    "usv",
}

BACKEND_LABELS = {
    BackendPreference.SCRAPLING.value: "Scrapling",
    BackendPreference.BB_BROWSER.value: "bb-browser",
}

SOURCE_FAMILY_LABELS = {
    "public_board": "Public boards",
    "portfolio_board": "Portfolio boards",
    "auth_board": "Authenticated boards",
}


def _source_label(source_name: str) -> str:
    return SOURCE_LABELS.get(source_name, source_name.replace("_", " ").title())


def _source_family_for_policy(source_name: str, source_kind: str) -> str:
    if source_kind == SourceKind.BROWSER_AUTH.value:
        return "auth_board"
    if source_name in PORTFOLIO_BOARD_SOURCES:
        return "portfolio_board"
    return "public_board"


def _setting_name_for_feature_flag(flag_key: str | None) -> str | None:
    if not flag_key:
        return None
    return flag_key.lower()


def _adapter_launch_reason(source_name: str) -> str | None:
    policy = get_source_policy(source_name)
    setting_name = _setting_name_for_feature_flag(policy.feature_flag_key)
    if setting_name and not getattr(settings, setting_name, True):
        return f"{policy.feature_flag_key}=false"
    if (
        policy.backend_preference == BackendPreference.BB_BROWSER.value
        and not settings.bb_browser_enabled
    ):
        return "BB_BROWSER_ENABLED=false"

    adapter = source_registry.create(source_name)
    if isinstance(adapter, UnsupportedPublicBoardSourceAdapter):
        return getattr(adapter, "_reason", None) or "Source adapter is registered but currently unsupported."
    return None


def _build_source_adapter_capability(source_name: str) -> SourceAdapterCapability:
    policy = get_source_policy(source_name)
    source_family = _source_family_for_policy(source_name, policy.source_kind)
    launch_reason = _adapter_launch_reason(source_name)
    setting_name = _setting_name_for_feature_flag(policy.feature_flag_key)
    enabled = True if setting_name is None else bool(getattr(settings, setting_name, True))
    return SourceAdapterCapability(
        source_name=source_name,
        source_label=_source_label(source_name),
        source_family=source_family,
        family_label=SOURCE_FAMILY_LABELS[source_family],
        source_kind=policy.source_kind,
        source_role=policy.source_role_default,
        backend=policy.backend_preference,
        backend_label=BACKEND_LABELS.get(policy.backend_preference, policy.backend_preference),
        requires_auth=policy.requires_auth,
        feature_flag_key=policy.feature_flag_key,
        enabled=enabled,
        launch_enabled=launch_reason is None,
        launch_reason=launch_reason,
    )


def _list_source_adapter_capabilities() -> list[SourceAdapterCapability]:
    items: list[SourceAdapterCapability] = []
    family_order = {"public_board": 0, "portfolio_board": 1, "auth_board": 2}
    for source_name, policy in SOURCE_POLICIES.items():
        if policy.backend_preference not in {
            BackendPreference.SCRAPLING.value,
            BackendPreference.BB_BROWSER.value,
        }:
            continue
        items.append(_build_source_adapter_capability(source_name))
    return sorted(
        items,
        key=lambda item: (
            family_order.get(item.source_family, 99),
            item.source_label.lower(),
        ),
    )


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
        title=j.title or j.normalized_title or "",
        company=j.company_name_raw or j.normalized_company or "",
        location=j.location or j.normalized_location,
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
            raw=analysis.ats_categories
            if isinstance(analysis.ats_categories, dict)
            else None,
        )
    b = j.ats_match_breakdown_json or {}
    if not b and not (j.ats_match_score or j.ats_match_score == 0):
        return None
    return ATSGaps(
        missing_keywords=[],
        found_keywords=None,
        ats_compatibility_score=float(j.ats_match_score)
        if j.ats_match_score is not None
        else None,
        raw=b if isinstance(b, dict) else None,
    )


def _job_to_detail_response(
    j: Job, artifacts: list[Artifact], debug: bool = False
) -> JobDetailResponse:
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
    debug_data = None
    if debug:
        debug_data = {
            "source_payload_json": j.source_payload_json,
            "dedup_hash": j.dedup_hash,
        }
    return JobDetailResponse(
        id=str(j.id),
        title=j.title or j.normalized_title or "",
        company=j.company_name_raw or j.normalized_company or "",
        location=j.location or j.normalized_location,
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
        debug_data=debug_data,
    )


class RunScrapeBody(BaseModel):
    query: Optional[str] = None
    location: Optional[str] = None
    hours_old: Optional[int] = None
    results_wanted: Optional[int] = None


class RunIngestionBody(BaseModel):
    """Generalized canonical ingestion. Fields vary by connector."""

    connector: Literal["greenhouse", "lever", "ashby"]
    company_name: str
    # Greenhouse
    board_token: Optional[str] = None
    # Lever
    client_name: Optional[str] = None
    # Ashby
    job_board_name: Optional[str] = None


class IngestUrlBody(BaseModel):
    url: str


class RunDiscoveryBody(BaseModel):
    """Discovery run. Connector agg1 (primary) or serp1 (optional, feature-flagged)."""

    connector: Literal["agg1", "serp1"]
    query: Optional[str] = None
    location: Optional[str] = None
    results_per_page: Optional[int] = None
    distance: Optional[int] = None
    max_days_old: Optional[int] = None
    sort_by: Optional[str] = "date"
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    full_time: Optional[bool] = None
    part_time: Optional[bool] = None
    contract: Optional[bool] = None
    permanent: Optional[bool] = None
    category: Optional[str] = None
    max_pages: Optional[int] = None
    max_results: Optional[int] = None


class BulkJobIds(BaseModel):
    job_ids: list[str]


@router.get(
    "/run-source-adapter",
    response_model=SourceAdapterCapabilitiesResponse,
)
async def list_source_adapter_capabilities():
    """List operator-visible adapter-backed source capabilities for ingestion-v2."""
    return SourceAdapterCapabilitiesResponse(items=_list_source_adapter_capabilities())


@router.post(
    "/run-source-adapter",
    response_model=SourceAdapterRunResponse,
)
async def run_source_adapter(
    body: SourceAdapterRunBody,
    db: AsyncSession = Depends(get_db),
):
    """Trigger an ingestion-v2 source-adapter run via the existing public/auth workers."""
    try:
        capability = _build_source_adapter_capability(body.source_name)
    except KeyError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source adapter: {body.source_name}.",
        ) from exc

    if not capability.launch_enabled:
        raise HTTPException(
            status_code=403,
            detail=capability.launch_reason or f"{body.source_name} is not launchable.",
        )

    scrape_run = ScrapeRun(
        source=body.source_name,
        status=ScrapeRunStatus.RUNNING.value,
        params_json={
            "launch_mode": "source_adapter",
            "source_name": body.source_name,
            "source_family": capability.source_family,
            "backend": capability.backend,
            "max_results": body.max_results,
        },
    )
    db.add(scrape_run)
    await db.commit()
    await db.refresh(scrape_run)

    task_kwargs = {
        "run_id": str(scrape_run.id),
        "source_name": body.source_name,
        "max_results": body.max_results or 25,
    }
    task_fn = (
        run_auth_board_source.delay
        if capability.source_family == "auth_board"
        else run_public_board_source.delay
    )
    task = task_fn(**task_kwargs)
    return SourceAdapterRunResponse(
        run_id=str(scrape_run.id),
        status=ScrapeRunStatus.RUNNING.value,
        task_id=str(task.id),
        source_name=body.source_name,
        source_label=capability.source_label,
        source_family=capability.source_family,
        backend=capability.backend,
    )


@router.post("/run-ingestion")
async def run_ingestion(
    body: RunIngestionBody,
    db: AsyncSession = Depends(get_db),
):
    """Trigger connector-based ingestion (Greenhouse, Lever, Ashby). Enqueues Celery task."""
    if body.connector == "greenhouse":
        if not body.board_token:
            raise HTTPException(
                status_code=400,
                detail="board_token required for greenhouse connector.",
            )
        params = {"board_token": body.board_token, "company_name": body.company_name}
        task_fn = ingest_greenhouse.delay
        task_kwargs = {
            "run_id": None,
            "board_token": body.board_token,
            "company_name": body.company_name,
        }
    elif body.connector == "lever":
        if not body.client_name:
            raise HTTPException(
                status_code=400,
                detail="client_name required for lever connector.",
            )
        params = {"client_name": body.client_name, "company_name": body.company_name}
        task_fn = ingest_lever.delay
        task_kwargs = {
            "run_id": None,
            "client_name": body.client_name,
            "company_name": body.company_name,
        }
    elif body.connector == "ashby":
        if not body.job_board_name:
            raise HTTPException(
                status_code=400,
                detail="job_board_name required for ashby connector.",
            )
        params = {
            "job_board_name": body.job_board_name,
            "company_name": body.company_name,
        }
        task_fn = ingest_ashby.delay
        task_kwargs = {
            "run_id": None,
            "job_board_name": body.job_board_name,
            "company_name": body.company_name,
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported connector: {body.connector}. Supported: greenhouse, lever, ashby.",
        )

    scrape_run = ScrapeRun(
        source=body.connector,
        status=ScrapeRunStatus.RUNNING.value,
        params_json=params,
    )
    db.add(scrape_run)
    await db.commit()
    await db.refresh(scrape_run)
    run_id = str(scrape_run.id)
    task_kwargs["run_id"] = run_id
    task = task_fn(**task_kwargs)
    return {"run_id": run_id, "status": "RUNNING", "task_id": str(task.id)}


@router.post("/run-discovery")
async def run_discovery_route(
    body: RunDiscoveryBody,
    db: AsyncSession = Depends(get_db),
):
    """Trigger broad discovery via AGG-1 or SERP1. Enqueues Celery task."""
    connector = body.connector
    if connector == "agg1":
        if not settings.enable_agg1_discovery:
            raise HTTPException(
                status_code=403,
                detail="AGG-1 discovery is disabled (ENABLE_AGG1_DISCOVERY=false).",
            )
    elif connector == "serp1":
        if not settings.enable_serp1_discovery:
            raise HTTPException(
                status_code=403,
                detail="SERP1 discovery is disabled (ENABLE_SERP1_DISCOVERY=false).",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported discovery connector: {connector}. Supported: agg1, serp1.",
        )
    params = {
        "connector": connector,
        "query": body.query,
        "location": body.location,
        "results_per_page": body.results_per_page or 20,
        "distance": body.distance,
        "max_days_old": body.max_days_old,
        "sort_by": body.sort_by or "date",
        "salary_min": body.salary_min,
        "salary_max": body.salary_max,
        "full_time": body.full_time,
        "part_time": body.part_time,
        "contract": body.contract,
        "permanent": body.permanent,
        "category": body.category,
        "max_pages": body.max_pages,
        "max_results": body.max_results,
    }
    scrape_run = ScrapeRun(
        source=connector,
        status=ScrapeRunStatus.RUNNING.value,
        params_json=params,
    )
    db.add(scrape_run)
    await db.commit()
    await db.refresh(scrape_run)
    run_id = str(scrape_run.id)
    task = run_discovery.delay(
        run_id=run_id,
        connector=connector,
        query=body.query,
        location=body.location,
        results_per_page=body.results_per_page or 20,
        distance=body.distance,
        max_days_old=body.max_days_old,
        sort_by=body.sort_by or "date",
        salary_min=body.salary_min,
        salary_max=body.salary_max,
        full_time=body.full_time,
        part_time=body.part_time,
        contract=body.contract,
        permanent=body.permanent,
        category=body.category,
        max_pages=body.max_pages,
        max_results=body.max_results,
    )
    return {
        "run_id": run_id,
        "status": "RUNNING",
        "task_id": str(task.id),
        "connector": connector,
    }


@router.post("/ingest-url")
async def ingest_url_route(
    body: IngestUrlBody,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a single job from a supported ATS URL (Greenhouse, Lever, Ashby). Enqueues Celery task."""
    if not settings.url_ingest_enabled:
        raise HTTPException(
            status_code=403,
            detail="URL ingest is disabled (URL_INGEST_ENABLED=false).",
        )
    parsed = parse_supported_url(body.url)
    if parsed is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported job URL. Supported providers: greenhouse, lever, ashby.",
        )
    scrape_run = ScrapeRun(
        source="url_ingest",
        status=ScrapeRunStatus.RUNNING.value,
        params_json={"url": body.url, "provider": parsed.provider},
    )
    db.add(scrape_run)
    await db.commit()
    await db.refresh(scrape_run)
    run_id = str(scrape_run.id)
    task = ingest_url.delay(run_id=run_id, url=body.url)
    return {
        "run_id": run_id,
        "status": "RUNNING",
        "task_id": str(task.id),
        "provider": parsed.provider,
    }


@router.post("/manual-ingest", response_model=ManualIngestResponse)
async def manual_ingest(
    body: ManualIngestBody,
    db: AsyncSession = Depends(get_db),
):
    """Persist a manually-entered job and enqueue the downstream pipeline."""
    from sqlalchemy.dialects.postgresql import insert

    norm_title = normalize_title(body.title)
    norm_company = normalize_company(body.company)
    norm_location = normalize_location(body.location)
    dedup_hash = compute_dedup_hash(
        normalized_company=norm_company,
        normalized_title=norm_title,
        normalized_location=norm_location or "",
        apply_url=body.apply_url,
    )

    posted_at = None
    if body.posted_at:
        try:
            posted_at = datetime.fromisoformat(body.posted_at)
        except (ValueError, OverflowError):
            pass

    # Create ScrapeRun for tracking
    scrape_run = ScrapeRun(
        source="manual_intake",
        status=ScrapeRunStatus.RUNNING.value,
        params_json={
            "title": body.title,
            "company": body.company,
            "location": body.location,
            "apply_url": body.apply_url,
        },
    )
    db.add(scrape_run)
    await db.flush()
    run_id = str(scrape_run.id)

    # Insert job with dedup
    stmt = (
        insert(Job)
        .values(
            source="manual_intake",
            source_role=SourceRole.CANONICAL.value,
            source_confidence=1.0,
            title=body.title.strip(),
            raw_title=body.title.strip(),
            normalized_title=norm_title,
            raw_company=body.company.strip(),
            normalized_company=norm_company,
            company_name_raw=body.company.strip(),
            raw_location=body.location.strip(),
            normalized_location=norm_location,
            location=body.location.strip(),
            url=body.source_url or body.apply_url,
            apply_url=body.apply_url.strip(),
            description=body.description.strip(),
            posted_at=posted_at,
            salary_min=body.salary_min,
            salary_max=body.salary_max,
            workplace_type=body.workplace_type,
            employment_type=body.employment_type,
            ats_type="manual",
            status="NEW",
            user_status="NEW",
            pipeline_status="INGESTED",
            score_total=0.0,
            dedup_hash=dedup_hash,
            source_payload_json={
                "intake_source": "manual_intake",
                "run_id": run_id,
            },
        )
        .on_conflict_do_nothing(index_elements=["dedup_hash"])
        .returning(Job.id)
    )
    result = await db.execute(stmt)
    job_id = result.scalar_one_or_none()
    raw_payload = {
        "intake_source": "manual_intake",
        "run_id": run_id,
    }

    if job_id is None:
        # Duplicate
        existing_job_id = (
            await db.execute(select(Job.id).where(Job.dedup_hash == dedup_hash))
        ).scalar_one_or_none()
        scrape_run.status = ScrapeRunStatus.SUCCESS.value
        scrape_run.finished_at = datetime.now(timezone.utc)
        scrape_run.stats_json = {"fetched": 1, "inserted": 0, "duplicates": 1, "errors": 0}
        scrape_run.items_json = [
            make_run_item(
                index=1,
                outcome="duplicate",
                job_id=str(existing_job_id) if existing_job_id is not None else None,
                dedup_hash=dedup_hash,
                source="manual_intake",
                source_job_id=None,
                title=body.title,
                company_name=body.company,
                location=body.location,
                url=body.source_url or body.apply_url,
                apply_url=body.apply_url,
                ats_type="manual_intake",
                raw_payload_json=raw_payload,
            )
        ]
        await db.commit()
        return ManualIngestResponse(
            run_id=run_id,
            job_id=None,
            status="DUPLICATE",
        )

    scrape_run.status = ScrapeRunStatus.SUCCESS.value
    scrape_run.finished_at = datetime.now(timezone.utc)
    scrape_run.stats_json = {"fetched": 1, "inserted": 1, "duplicates": 0, "errors": 0}
    scrape_run.items_json = [
        make_run_item(
            index=1,
            outcome="inserted",
            job_id=str(job_id),
            dedup_hash=dedup_hash,
            source="manual_intake",
            source_job_id=None,
            title=body.title,
            company_name=body.company,
            location=body.location,
            url=body.source_url or body.apply_url,
            apply_url=body.apply_url,
            ats_type="manual_intake",
            raw_payload_json=raw_payload,
        )
    ]
    await db.commit()

    # Enqueue downstream pipeline
    task = manual_ingest_pipeline.delay([str(job_id)])

    return ManualIngestResponse(
        run_id=run_id,
        job_id=str(job_id),
        status="SUCCESS",
        task_id=str(task.id),
    )


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


@router.get("/ready-to-apply", response_model=JobListResponse)
async def list_ready_to_apply(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    sort_by: str = Query(
        "artifact_ready_at",
        description="Sort column (artifact_ready_at, score_total, scraped_at)",
    ),
    sort_dir: str = Query("desc"),
):
    """
    Jobs with artifact ready for manual application (ARCH §11.2).
    Filters: pipeline_status=RESUME_READY, artifact_ready_at IS NOT NULL, user_status=NEW.
    """
    stmt = (
        select(Job)
        .where(Job.pipeline_status == PipelineStatus.RESUME_READY.value)
        .where(Job.artifact_ready_at.isnot(None))
        .where(Job.user_status == UserStatus.NEW.value)
        .options(selectinload(Job.analyses), selectinload(Job.artifacts))
    )
    count_stmt = (
        select(func.count())
        .select_from(Job)
        .where(Job.pipeline_status == PipelineStatus.RESUME_READY.value)
        .where(Job.artifact_ready_at.isnot(None))
        .where(Job.user_status == UserStatus.NEW.value)
    )
    sort_col = getattr(Job, sort_by, Job.artifact_ready_at)
    if sort_dir == "asc":
        stmt = stmt.order_by(sort_col.asc().nullslast())
    else:
        stmt = stmt.order_by(sort_col.desc().nullslast())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    jobs = result.unique().scalars().all()
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    items = [_job_to_list_item(j) for j in jobs]
    return JobListResponse(items=items, total=total, page=page, per_page=per_page)


@router.post("/bulk-status")
async def bulk_status(
    body: BulkJobIds, status: str = Query(...), db: AsyncSession = Depends(get_db)
):
    if status not in WRITABLE_USER_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"user_status must be one of {sorted(WRITABLE_USER_STATUSES)}; NEW is not client-settable",
        )

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
    status: Optional[str] = Query(
        None, description="Alias for user_status (backward compat)"
    ),
    pipeline_status: Optional[str] = None,
    source: Optional[str] = None,
    persona: Optional[str] = Query(None, description="Filter by matched persona"),
    q: Optional[str] = Query(None, description="Search title/company"),
    min_score: Optional[float] = None,
    include_rejected: bool = Query(
        False, description="Include REJECTED jobs for debugging"
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    sort_by: str = Query(
        "score_total", description="Sort column (score_total, scraped_at, title)"
    ),
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
        count_stmt = count_stmt.where(
            Job.pipeline_status != PipelineStatus.REJECTED.value
        )
    if source:
        stmt = stmt.where(Job.source == source)
        count_stmt = count_stmt.where(Job.source == source)
    if persona:
        stmt = stmt.join(JobAnalysis, Job.id == JobAnalysis.job_id).where(
            JobAnalysis.matched_persona == persona
        )
        count_stmt = count_stmt.join(JobAnalysis, Job.id == JobAnalysis.job_id).where(
            JobAnalysis.matched_persona == persona
        )
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
    include_rejected: bool = Query(
        False, description="Allow viewing REJECTED jobs (debug)"
    ),
    debug: bool = Query(
        False,
        description="Include internal debug data (source_payload_json, dedup_hash); requires DEBUG_ENDPOINTS_ENABLED=true",
    ),
):
    """Retrieve full job details, analysis, scores, and artifact metadata.
    When debug=true, internal debug_data is included only if DEBUG_ENDPOINTS_ENABLED is set."""
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.analyses), selectinload(Job.artifacts))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not include_rejected and job.pipeline_status == PipelineStatus.REJECTED.value:
        raise HTTPException(status_code=404, detail="Job not found")
    artifacts = sorted(
        job.artifacts or [],
        key=lambda a: a.created_at.timestamp() if a.created_at else 0.0,
        reverse=True,
    )
    # Gate debug_data behind debug_endpoints_enabled (same as /api/debug/*)
    effective_debug = debug and settings.debug_endpoints_enabled
    return _job_to_detail_response(job, artifacts, debug=effective_debug)


@router.post("/{job_id}/resolve", response_model=ResolveJobResponse)
async def resolve_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Force canonical enrichment for a discovery job (ARCH §11.2).
    When the job's apply_url maps to Greenhouse, Lever, or Ashby, fetches
    canonical data and enriches in place. Enqueues Celery task.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.source_role != SourceRole.DISCOVERY.value:
        raise HTTPException(
            status_code=400,
            detail="Job is not a discovery record. Resolution applies only to source_role=discovery.",
        )
    if job.resolution_status == ResolutionStatus.RESOLVED_CANONICAL.value:
        return ResolveJobResponse(
            job_id=str(job_id),
            status="already_resolved",
            task_id=None,
            reason="Job already resolved to canonical.",
        )
    url_to_resolve = (job.apply_url or job.url or "").strip()
    if not url_to_resolve:
        raise HTTPException(
            status_code=400,
            detail="Job has no apply_url or url to resolve.",
        )
    task = resolve_discovery_job.delay(str(job_id))
    return ResolveJobResponse(
        job_id=str(job_id),
        status="queued",
        task_id=str(task.id),
    )


@router.put("/{job_id}/status", response_model=UpdateStatusResponse)
async def update_job_status(
    job_id: UUID, body: UpdateStatusRequest, db: AsyncSession = Depends(get_db)
):
    """Update user workflow status (SAVED, APPLIED, ARCHIVED)."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if body.user_status not in WRITABLE_USER_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"user_status must be one of {sorted(WRITABLE_USER_STATUSES)}; NEW is not client-settable",
        )
    job.user_status = body.user_status
    job.status = legacy_status_from_canonical(job.pipeline_status, job.user_status)
    await db.commit()
    await db.refresh(job)
    return UpdateStatusResponse(id=str(job.id), user_status=job.user_status)


# Resume generation requires the full pipeline: score → classify → ats_match.
# Only ATS_ANALYZED and RESUME_READY have complete persona + ATS keyword data.
RESUME_READY_PIPELINE_STATUSES = frozenset(
    {PipelineStatus.ATS_ANALYZED.value, PipelineStatus.RESUME_READY.value}
)


@router.post("/{job_id}/generate-resume", response_model=GenerateResumeResponse)
async def trigger_generate_resume(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Trigger or regenerate tailored resume for a job. Enqueues Celery task."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.pipeline_status not in RESUME_READY_PIPELINE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Resume generation requires score → classify → ATS analysis. "
            "Job pipeline_status must be ATS_ANALYZED or RESUME_READY. "
            f"Current: {job.pipeline_status}.",
        )
    run = build_generation_run(job_id, "manual")
    db.add(run)
    await db.flush()
    generation_run_id = str(run.id)
    await db.commit()
    task = generate_grounded_resume_task.delay(
        str(job_id), generation_run_id=generation_run_id, triggered_by="manual"
    )
    return GenerateResumeResponse(
        job_id=str(job_id),
        status="queued",
        task_id=str(task.id),
        generation_run_id=generation_run_id,
    )


@router.get("/{job_id}/artifacts", response_model=ArtifactsResponse)
async def list_job_artifacts(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """List artifacts (resumes) for a job. Returns 404 if job does not exist."""
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    if not job_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Job not found")
    result = await db.execute(
        select(Artifact)
        .where(Artifact.job_id == job_id)
        .order_by(Artifact.created_at.desc())
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
