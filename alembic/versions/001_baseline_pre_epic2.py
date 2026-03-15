"""Baseline schema (pre-EPIC2 canonical model).

Revision ID: 001_baseline
Revises: 
Create Date: 2025-03-15

Baseline represents the schema before EPIC 2 canonical additions.
For fresh installs: run upgrade to create tables.
For existing unversioned DBs: do NOT run; use `alembic stamp 001_baseline` instead.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create baseline schema for fresh installs."""
    op.create_table(
        "companies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("apollo_id", sa.Text(), nullable=True),
        sa.Column("stage", sa.Text(), nullable=True),
        sa.Column("headcount", sa.Integer(), nullable=True),
        sa.Column("last_enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_companies_name", "companies", ["name"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_job_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("company_id", UUID(as_uuid=True), nullable=True),
        sa.Column("company_name_raw", sa.Text(), nullable=False, server_default=""),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("remote_flag", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("url", sa.Text(), nullable=False, server_default=""),
        sa.Column("apply_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ats_type", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("status", sa.Text(), server_default="NEW", nullable=False),
        sa.Column("score_total", sa.Float(), nullable=False),
        sa.Column("score_breakdown_json", JSONB(), nullable=True),
        sa.Column("ats_match_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ats_match_breakdown_json", JSONB(), nullable=True),
        sa.Column("source_payload_json", JSONB(), nullable=True),
        sa.Column("dedup_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
    )
    op.create_index("ix_jobs_company_id", "jobs", ["company_id"], unique=False)
    op.create_index("ix_jobs_source", "jobs", ["source"], unique=False)
    op.create_index("ix_jobs_status_scraped_at", "jobs", ["status", "scraped_at"], unique=False)
    op.create_unique_constraint("uq_jobs_dedup_hash", "jobs", ["dedup_hash"])

    op.create_table(
        "scrape_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("params_json", JSONB(), nullable=True),
        sa.Column("stats_json", JSONB(), nullable=True),
        sa.Column("items_json", JSONB(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "applications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("fields_json", JSONB(), nullable=True),
        sa.Column("external_app_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
    )
    op.create_index("ix_applications_job_id_started_at", "applications", ["job_id", "started_at"], unique=False)

    op.create_table(
        "artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("application_id", UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("meta_json", JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
    )

    op.create_table(
        "interventions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("last_url", sa.Text(), nullable=True),
        sa.Column("screenshot_artifact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("html_artifact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.ForeignKeyConstraint(["screenshot_artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["html_artifact_id"], ["artifacts.id"]),
    )
    op.create_index("ix_interventions_status_created_at", "interventions", ["status", "created_at"], unique=False)


def downgrade() -> None:
    """Remove baseline schema."""
    op.drop_table("interventions")
    op.drop_table("artifacts")
    op.drop_table("applications")
    op.drop_table("scrape_runs")
    op.drop_table("jobs")
    op.drop_table("companies")
