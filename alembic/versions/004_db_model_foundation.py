"""DB model foundation: canonical ATS, discovery, resolution, generation (PR 2).

Revision ID: 004_db_foundation
Revises: 003_ats_categories
Create Date: 2025-03-15

Adds:
- jobs: source_role, source_confidence, canonical_*, workplace_type, employment_type,
  department, team, requisition_id, salary_currency, salary_interval,
  location_structured_json, content_quality_score, generation_eligibility,
  generation_reason, auto_generated_at, artifact_ready_at, resolution_status,
  resolution_confidence, stale_flag
- generation_runs
- job_resolution_attempts
- source_configs

Uses ADD COLUMN IF NOT EXISTS for safe idempotent application.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "004_db_foundation"
down_revision: Union[str, Sequence[str], None] = "003_ats_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- jobs: canonical ATS, discovery, URL ingest ---
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_role TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_confidence FLOAT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS canonical_source_name TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS canonical_external_id TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS canonical_url TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS workplace_type TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS employment_type TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS department TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS team TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS requisition_id TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_currency TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS salary_interval TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS location_structured_json JSONB")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS content_quality_score FLOAT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS generation_eligibility TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS generation_reason TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS auto_generated_at TIMESTAMPTZ")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS artifact_ready_at TIMESTAMPTZ")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS resolution_status TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS resolution_confidence FLOAT")
    op.execute(
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS stale_flag BOOLEAN NOT NULL DEFAULT false"
    )

    # --- jobs: indexes for ready-to-apply and filtering ---
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_source_role ON jobs (source_role)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_generation_eligibility ON jobs (generation_eligibility)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_artifact_ready_at ON jobs (artifact_ready_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_resolution_status ON jobs (resolution_status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_stale_flag ON jobs (stale_flag)")

    # --- generation_runs ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS generation_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL REFERENCES jobs(id),
            status TEXT NOT NULL DEFAULT 'queued',
            inputs_hash TEXT,
            failure_reason TEXT,
            artifact_id UUID REFERENCES artifacts(id),
            triggered_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_generation_runs_job_id ON generation_runs (job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_generation_runs_status ON generation_runs (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_generation_runs_created_at ON generation_runs (created_at)")

    # --- job_resolution_attempts ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS job_resolution_attempts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL REFERENCES jobs(id),
            resolution_status TEXT NOT NULL,
            confidence FLOAT,
            failure_reason TEXT,
            canonical_url TEXT,
            canonical_source_name TEXT,
            attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_job_resolution_attempts_job_id ON job_resolution_attempts (job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_job_resolution_attempts_attempted_at ON job_resolution_attempts (attempted_at)")

    # --- source_configs ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS source_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_name TEXT NOT NULL,
            config_key TEXT NOT NULL,
            config_value_json JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(source_name, config_key)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS source_configs")
    op.execute("DROP TABLE IF EXISTS job_resolution_attempts")
    op.execute("DROP TABLE IF EXISTS generation_runs")
    op.execute("DROP INDEX IF EXISTS ix_jobs_stale_flag")
    op.execute("DROP INDEX IF EXISTS ix_jobs_resolution_status")
    op.execute("DROP INDEX IF EXISTS ix_jobs_artifact_ready_at")
    op.execute("DROP INDEX IF EXISTS ix_jobs_generation_eligibility")
    op.execute("DROP INDEX IF EXISTS ix_jobs_source_role")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS stale_flag")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS resolution_confidence")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS resolution_status")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS artifact_ready_at")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS auto_generated_at")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS generation_reason")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS generation_eligibility")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS content_quality_score")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS location_structured_json")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS salary_interval")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS salary_currency")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS requisition_id")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS team")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS department")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS employment_type")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS workplace_type")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS canonical_url")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS canonical_external_id")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS canonical_source_name")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS source_confidence")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS source_role")
