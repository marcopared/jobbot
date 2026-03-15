import uuid
from enum import Enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db.base import Base


# --- Canonical vs legacy ownership ---
# Canonical source of truth: pipeline_status, user_status, raw/normalized title/company/location.
# Legacy Job.status is a compatibility mirror only. Use core.job_status.legacy_status_from_canonical()
# to derive it. Do not use status to drive new behavior.


# --- Enums (SPEC §7.1) ---


class PipelineStatus(str, Enum):
    INGESTED = "INGESTED"
    DEDUPED = "DEDUPED"
    SCORED = "SCORED"
    REJECTED = "REJECTED"
    CLASSIFIED = "CLASSIFIED"
    ATS_ANALYZED = "ATS_ANALYZED"
    RESUME_READY = "RESUME_READY"
    FAILED = "FAILED"

class UserStatus(str, Enum):
    NEW = "NEW"
    SAVED = "SAVED"
    APPLIED = "APPLIED"
    ARCHIVED = "ARCHIVED"

class JobStatus(str, Enum):
    # Legacy statuses kept for DB compatibility if needed
    NEW = "NEW"
    SCORED = "SCORED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SAVED = "SAVED"
    APPLIED = "APPLIED"
    ARCHIVED = "ARCHIVED"
    APPLY_QUEUED = "APPLY_QUEUED"
    APPLY_FAILED = "APPLY_FAILED"
    INTERVENTION_REQUIRED = "INTERVENTION_REQUIRED"


class ApplicationStatus(str, Enum):
    STARTED = "STARTED"
    SUBMITTED = "SUBMITTED"
    FAILED = "FAILED"
    INTERVENTION_REQUIRED = "INTERVENTION_REQUIRED"
    SKIPPED = "SKIPPED"


class InterventionStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    ABORTED = "ABORTED"


class ScrapeRunStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ATSType(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKDAY = "workday"
    YC = "yc"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class ArtifactKind(str, Enum):
    SCREENSHOT = "screenshot"
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
    LOG = "log"
    OTHER = "other"


class JobSource(str, Enum):
    JOBSPY = "jobspy"
    GREENHOUSE = "greenhouse"
    WELLFOUND = "wellfound"
    BUILTINNYC = "builtinnyc"
    YC = "yc"
    MANUAL = "manual"
    OTHER = "other"


class InterventionReason(str, Enum):
    CAPTCHA = "captcha"
    MFA = "mfa"
    UNEXPECTED_FIELD = "unexpected_field"
    BLOCKED = "blocked"
    LOGIN_REQUIRED = "login_required"
    OTHER = "other"


class ApplyMethod(str, Enum):
    PLAYWRIGHT = "playwright"
    MANUAL = "manual"


# --- Models (SPEC §7.2) ---


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    apollo_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    headcount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_enriched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="company")

    __table_args__ = (Index("ix_companies_name", "name"),)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    raw_company: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_company: Mapped[str] = mapped_column(Text, nullable=False, default="")
    normalized_title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    normalized_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Legacy fields kept for compatibility during migration
    source: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    source_job_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True
    )
    company_name_raw: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remote_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    apply_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    salary_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ats_type: Mapped[str] = mapped_column(Text, default="unknown", nullable=False)
    status: Mapped[str] = mapped_column(Text, default="NEW", nullable=False)
    pipeline_status: Mapped[str] = mapped_column(Text, default="INGESTED", nullable=False)
    user_status: Mapped[str] = mapped_column(Text, default="NEW", nullable=False)
    score_total: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    score_breakdown_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ats_match_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ats_match_breakdown_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    source_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    dedup_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    company: Mapped[Optional["Company"]] = relationship(
        "Company", back_populates="jobs"
    )
    applications: Mapped[list["Application"]] = relationship(
        "Application", back_populates="job"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact", back_populates="job"
    )
    interventions: Mapped[list["Intervention"]] = relationship(
        "Intervention", back_populates="job"
    )
    sources: Mapped[list["JobSourceRecord"]] = relationship(
        "JobSourceRecord", back_populates="job"
    )
    analyses: Mapped[list["JobAnalysis"]] = relationship(
        "JobAnalysis", back_populates="job"
    )

    __table_args__ = (
        Index("ix_jobs_status_scraped_at", "status", "scraped_at"),
        Index("ix_jobs_pipeline_status", "pipeline_status"),
        Index("ix_jobs_user_status", "user_status"),
        Index("ix_jobs_company_id", "company_id"),
        Index("ix_jobs_source", "source"),
    )

class JobSourceRecord(Base):
    __tablename__ = "job_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False
    )
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    provenance_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["Job"] = relationship("Job", back_populates="sources")

    __table_args__ = (
        Index("ix_job_sources_job_id", "job_id"),
        Index("ix_job_sources_source_ext_id", "source_name", "external_id", unique=True),
    )

class JobAnalysis(Base):
    __tablename__ = "job_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False
    )
    total_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    seniority_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tech_stack_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    persona_specific_scores: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    matched_persona: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    persona_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    persona_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    missing_keywords: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    found_keywords: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    ats_categories: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ats_compatibility_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    run_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["Job"] = relationship("Job", back_populates="analyses")

    __table_args__ = (
        Index("ix_job_analyses_job_id", "job_id"),
        Index("uq_job_analyses_job_id", "job_id", unique=True),
    )


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, default="RUNNING", nullable=False)
    params_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    stats_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    items_json: Mapped[Optional[list[dict]]] = mapped_column(JSONB, nullable=True)
    error_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# Legacy: applications/interventions are internal tables for apply flow, not part of canonical job pipeline.
class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, default="STARTED", nullable=False)
    method: Mapped[str] = mapped_column(Text, default="playwright", nullable=False)
    error_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fields_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    external_app_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["Job"] = relationship("Job", back_populates="applications")
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact", back_populates="application"
    )
    interventions: Mapped[list["Intervention"]] = relationship(
        "Intervention", back_populates="application"
    )

    __table_args__ = (Index("ix_applications_job_id_started_at", "job_id", "started_at"),)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True
    )
    application_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # New canonical fields
    persona_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    format: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    template_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inventory_version_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generation_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    meta_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="artifacts")
    application: Mapped[Optional["Application"]] = relationship(
        "Application", back_populates="artifacts"
    )


# Legacy: internal table for apply-flow interventions; retained for compatibility only.
class Intervention(Base):
    __tablename__ = "interventions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False
    )
    application_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, default="OPEN", nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    last_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    screenshot_artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=True
    )
    html_artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    job: Mapped["Job"] = relationship("Job", back_populates="interventions")
    application: Mapped[Optional["Application"]] = relationship(
        "Application", back_populates="interventions"
    )

    __table_args__ = (Index("ix_interventions_status_created_at", "status", "created_at"),)
