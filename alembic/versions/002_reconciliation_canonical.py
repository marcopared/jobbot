"""Reconciliation: add canonical columns, job_sources, job_analyses, backfill.

Revision ID: 002_reconciliation
Revises: 001_baseline
Create Date: 2025-03-15

Adds pipeline_status, user_status, raw/normalized fields; creates job_sources
and job_analyses; backfills with explicit CASE mapping (no direct status copy).
For DBs stamped at baseline, uses conditional DDL (IF NOT EXISTS).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002_reconciliation"
down_revision: Union[str, Sequence[str], None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add canonical schema and backfill."""
    # --- jobs: add canonical columns (conditional for already-patched DBs) ---
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS raw_company TEXT DEFAULT ''")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS raw_title TEXT DEFAULT ''")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS raw_location TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS normalized_company TEXT DEFAULT ''")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS normalized_title TEXT DEFAULT ''")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS normalized_location TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS pipeline_status TEXT DEFAULT 'INGESTED'")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_status TEXT DEFAULT 'NEW'")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_payload_json JSONB")

    # --- indexes on jobs ---
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_pipeline_status ON jobs (pipeline_status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_user_status ON jobs (user_status)")

    # --- raw/normalized backfill (plain copy, coarse transitional) ---
    op.execute("""
        UPDATE jobs
        SET raw_company = COALESCE(company_name_raw, ''),
            normalized_company = COALESCE(company_name_raw, ''),
            raw_title = COALESCE(title, ''),
            normalized_title = COALESCE(title, ''),
            raw_location = location,
            normalized_location = location
        WHERE (raw_company = '' OR raw_title = '')
          AND company_name_raw IS NOT NULL AND title IS NOT NULL
    """)

    # --- user_status backfill (explicit CASE, never direct copy) ---
    op.execute("""
        UPDATE jobs SET user_status = CASE
            WHEN status = 'APPLIED' THEN 'APPLIED'
            WHEN status IN ('REJECTED', 'ARCHIVED', 'INTERVENTION_REQUIRED', 'APPLY_FAILED', 'SKIPPED') THEN 'ARCHIVED'
            WHEN status IN ('APPROVED', 'SAVED') THEN 'SAVED'
            ELSE 'NEW'
        END
    """)

    # --- pipeline_status backfill (explicit safe mappings, else INGESTED) ---
    op.execute("""
        UPDATE jobs SET pipeline_status = CASE
            WHEN status = 'SCORED' THEN 'SCORED'
            WHEN status = 'REJECTED' THEN 'REJECTED'
            ELSE 'INGESTED'
        END
    """)

    # --- job_sources (IF NOT EXISTS for DBs that have it from create_all) ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS job_sources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL REFERENCES jobs(id),
            source_name TEXT NOT NULL,
            external_id TEXT NOT NULL,
            raw_data JSONB,
            provenance_metadata JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(source_name, external_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_job_sources_job_id ON job_sources (job_id)")

    # --- job_analyses (one row per job, UNIQUE job_id) ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS job_analyses (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL UNIQUE REFERENCES jobs(id),
            total_score FLOAT NOT NULL DEFAULT 0,
            seniority_score FLOAT,
            tech_stack_score FLOAT,
            location_score FLOAT,
            persona_specific_scores JSONB,
            matched_persona TEXT,
            persona_confidence FLOAT,
            persona_rationale TEXT,
            missing_keywords JSONB,
            found_keywords JSONB,
            ats_compatibility_score FLOAT,
            run_id TEXT,
            model_version TEXT,
            prompt_version TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    # Ensure unique constraint exists for existing tables (e.g. from create_all)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_job_analyses_job_id')
               AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'job_analyses')
            THEN
                ALTER TABLE job_analyses ADD CONSTRAINT uq_job_analyses_job_id UNIQUE (job_id);
            END IF;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # --- artifacts: add canonical metadata columns ---
    op.execute("ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS persona_name TEXT")
    op.execute("ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS file_url TEXT")
    op.execute("ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS format TEXT")
    op.execute("ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS version TEXT")
    op.execute("ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS prompt_version TEXT")
    op.execute("ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS template_version TEXT")
    op.execute("ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS inventory_version_hash TEXT")
    op.execute("ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS generation_status TEXT")

    # --- scrape_runs: items_json (may already exist) ---
    op.execute("ALTER TABLE scrape_runs ADD COLUMN IF NOT EXISTS items_json JSONB")


def downgrade() -> None:
    """Remove canonical additions."""
    op.execute("ALTER TABLE scrape_runs DROP COLUMN IF EXISTS items_json")
    op.execute("ALTER TABLE artifacts DROP COLUMN IF EXISTS persona_name")
    op.execute("ALTER TABLE artifacts DROP COLUMN IF EXISTS file_url")
    op.execute("ALTER TABLE artifacts DROP COLUMN IF EXISTS format")
    op.execute("ALTER TABLE artifacts DROP COLUMN IF EXISTS version")
    op.execute("ALTER TABLE artifacts DROP COLUMN IF EXISTS prompt_version")
    op.execute("ALTER TABLE artifacts DROP COLUMN IF EXISTS template_version")
    op.execute("ALTER TABLE artifacts DROP COLUMN IF EXISTS inventory_version_hash")
    op.execute("ALTER TABLE artifacts DROP COLUMN IF EXISTS generation_status")
    op.execute("DROP TABLE IF EXISTS job_analyses")
    op.execute("DROP TABLE IF EXISTS job_sources")
    op.execute("DROP INDEX IF EXISTS ix_jobs_pipeline_status")
    op.execute("DROP INDEX IF EXISTS ix_jobs_user_status")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS raw_company")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS raw_title")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS raw_location")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS normalized_company")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS normalized_title")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS normalized_location")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS pipeline_status")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS user_status")
