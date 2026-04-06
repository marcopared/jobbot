"""Pydantic schemas for v1 REST API (EPIC 8)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# --- Job list item ---


class JobListItem(BaseModel):
    """Job list item for GET /api/jobs."""

    id: str
    title: str
    company: str
    location: str | None
    score: float = Field(description="Total relevance score")
    persona: str | None = None
    pipeline_status: str
    user_status: str
    artifact_availability: bool = False
    source: str | None = None


class JobListResponse(BaseModel):
    """Paginated job list response."""

    items: list[JobListItem]
    total: int
    page: int
    per_page: int


# --- Job detail ---


class ScoreBreakdown(BaseModel):
    """Score breakdown for detail view."""

    title_relevance: float | None = None
    seniority_fit: float | None = None
    domain_alignment: float | None = None
    tech_stack: float | None = None
    location_remote: float | None = None
    weights: dict[str, float] | None = None
    raw: dict[str, Any] | None = None


class ATSGaps(BaseModel):
    """ATS keyword gaps and compatibility."""

    missing_keywords: list[str] = Field(default_factory=list)
    found_keywords: list[str] | None = None
    ats_compatibility_score: float | None = None
    raw: dict[str, Any] | None = None


class PersonaInfo(BaseModel):
    """Persona classification and rationale."""

    matched_persona: str | None = None
    persona_confidence: float | None = None
    persona_rationale: str | None = None


class GenerationRunSummary(BaseModel):
    """Latest generation-run summary for Job Detail progress visibility."""

    id: str
    status: str
    triggered_by: str | None = None
    created_at: str | None = None
    finished_at: str | None = None
    failure_reason: str | None = None
    artifact_id: str | None = None


class ArtifactMetadata(BaseModel):
    """Artifact metadata for detail view."""

    id: str
    kind: str
    filename: str
    persona_name: str | None = None
    generation_status: str | None = None
    created_at: str | None = None
    download_url: str
    preview_url: str


class EvidenceCompletenessSummary(BaseModel):
    """Compact evidence completeness summary for resume-generation artifacts."""

    summary: str
    source_kind: str | None = None
    total_sources: int = 0
    present_sources: int = 0
    required_sources: int = 0
    required_present: int = 0
    optional_sources: int = 0
    optional_present: int = 0
    missing_optional_sources: list[str] = Field(default_factory=list)


class JobDetailResponse(BaseModel):
    """Full job detail for GET /api/jobs/{id}."""

    id: str
    title: str
    company: str
    location: str | None
    description: str | None
    url: str | None = Field(description="Job listing URL")
    apply_url: str | None = Field(description="External application URL - user applies manually")
    source: str | None = None

    score: float = 0.0
    artifact_availability: bool = False
    score_breakdown: ScoreBreakdown | None = None
    ats_gaps: ATSGaps | None = None
    persona: PersonaInfo | None = None
    latest_generation_run: GenerationRunSummary | None = None
    artifacts: list["ArtifactItem"] = Field(default_factory=list)

    pipeline_status: str
    user_status: str
    created_at: str | None = None
    updated_at: str | None = None

    # Optional display fields
    salary_min: int | None = None
    salary_max: int | None = None
    posted_at: str | None = None
    remote_flag: bool = False

    # Present only when debug=true AND DEBUG_ENDPOINTS_ENABLED=true on GET /api/jobs/{id}
    debug_data: dict | None = None


# --- Status update ---


class UpdateStatusRequest(BaseModel):
    """Request body for PUT /api/jobs/{id}/status."""

    user_status: str = Field(..., description="One of: SAVED, APPLIED, ARCHIVED (NEW is not client-settable)")


class UpdateStatusResponse(BaseModel):
    """Response for PUT /api/jobs/{id}/status."""

    id: str
    user_status: str


# --- Generate resume ---


class GenerateResumeResponse(BaseModel):
    """Response for POST /api/jobs/{id}/generate-resume."""

    job_id: str
    status: str = Field(
        default="queued",
        description="Queue acceptance status for the manual resume generation request.",
    )
    task_id: str | None = Field(
        default=None,
        description="Celery task identifier for the queued resume generation worker.",
    )
    generation_run_id: str = Field(
        description="Persisted GenerationRun id created before queueing the worker.",
    )


class QueuedRunResponse(BaseModel):
    """Common response for run-launching endpoints."""

    run_id: str
    status: str
    task_id: str | None = None


class SourceAdapterCapability(BaseModel):
    """Operator-visible metadata for adapter-backed ingestion-v2 sources."""

    source_name: str
    source_label: str
    source_family: Literal["public_board", "portfolio_board", "auth_board"]
    family_label: str
    source_kind: str
    source_role: str
    backend: str
    backend_label: str
    requires_auth: bool = False
    feature_flag_key: str | None = None
    enabled: bool = True
    launch_enabled: bool = True
    launch_reason: str | None = None


class SourceAdapterCapabilitiesResponse(BaseModel):
    """Response for listing adapter-backed run capabilities."""

    items: list[SourceAdapterCapability]


class SourceAdapterRunBody(BaseModel):
    """Request body for POST /api/jobs/run-source-adapter."""

    source_name: str = Field(description="Registered ingestion-v2 adapter source name.")
    max_results: int | None = Field(
        default=25,
        ge=1,
        le=100,
        description="Upper bound for jobs to acquire in this operator-triggered run.",
    )


class SourceAdapterRunResponse(QueuedRunResponse):
    """Response for POST /api/jobs/run-source-adapter."""

    source_name: str
    source_label: str
    source_family: Literal["public_board", "portfolio_board", "auth_board"]
    backend: str


class ResolveJobResponse(BaseModel):
    """Response for POST /api/jobs/{id}/resolve."""

    job_id: str
    status: str  # queued | no_op | already_resolved
    task_id: str | None = None
    reason: str | None = None


# --- Artifacts ---


# --- Manual ingest ---


class ManualIngestBody(BaseModel):
    """Request body for POST /api/jobs/manual-ingest."""

    title: str
    company: str
    location: str
    apply_url: str
    description: str
    source_url: str | None = None
    posted_at: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    workplace_type: str | None = None
    employment_type: str | None = None


class ManualIngestResponse(BaseModel):
    """Response for POST /api/jobs/manual-ingest."""

    run_id: str
    job_id: str | None = None
    status: str  # "SUCCESS" | "DUPLICATE" | "FAILED"
    task_id: str | None = None


class ArtifactItem(BaseModel):
    """Artifact item for GET /api/jobs/{id}/artifacts."""

    id: str
    kind: str
    filename: str
    format: str | None = None
    persona_name: str | None = None
    generation_status: str | None = None
    created_at: str | None = None
    artifact_role: str | None = None
    is_primary: bool = False
    payload_version: str | None = None
    inputs_hash: str | None = None
    fit_status: str | None = None
    evidence_completeness: EvidenceCompletenessSummary | None = None
    download_url: str
    preview_url: str


class ArtifactsResponse(BaseModel):
    """Response for GET /api/jobs/{id}/artifacts."""

    items: list[ArtifactItem]
