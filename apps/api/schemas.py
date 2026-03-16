"""Pydantic schemas for v1 REST API (EPIC 8)."""

from datetime import datetime
from typing import Any

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
    score_breakdown: ScoreBreakdown | None = None
    ats_gaps: ATSGaps | None = None
    persona: PersonaInfo | None = None
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
    status: str = "queued"
    task_id: str | None = None


# --- Artifacts ---


class ArtifactItem(BaseModel):
    """Artifact item for GET /api/jobs/{id}/artifacts."""

    id: str
    kind: str
    filename: str
    persona_name: str | None = None
    generation_status: str | None = None
    created_at: str | None = None
    download_url: str
    preview_url: str


class ArtifactsResponse(BaseModel):
    """Response for GET /api/jobs/{id}/artifacts."""

    items: list[ArtifactItem]
