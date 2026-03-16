"""Add ats_categories to job_analyses (EPIC 5).

Revision ID: 003_ats_categories
Revises: 002_reconciliation
Create Date: 2025-03-15

Adds ats_categories JSONB column for grouped ATS keyword categories.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003_ats_categories"
down_revision: Union[str, Sequence[str], None] = "002_reconciliation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE job_analyses ADD COLUMN IF NOT EXISTS ats_categories JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE job_analyses DROP COLUMN IF EXISTS ats_categories")
