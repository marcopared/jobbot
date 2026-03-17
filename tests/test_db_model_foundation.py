"""PR 2: DB model foundation tests (source role, resolution, generation eligibility).

Tests:
- Migration 004 schema: new job columns and tables exist
- Model integrity: Job, GenerationRun, JobResolutionAttempt, SourceConfig CRUD
- Backfill safety: existing jobs remain readable; new columns default correctly

Requires: Postgres with migrations applied (alembic upgrade head).
Run: pytest tests/test_db_model_foundation.py
"""

import uuid

from sqlalchemy import create_engine, text

from apps.api.settings import Settings
from core.dedup import compute_dedup_hash_from_raw, normalize_company, normalize_title
from core.db.models import (
    Company,
    GenerationEligibility,
    GenerationRun,
    Job,
    JobResolutionAttempt,
    ResolutionStatus,
    SourceConfig,
    SourceRole,
)
from core.db.session import get_sync_session


def test_migration_004_schema() -> None:
    """Migration 004: jobs has new columns; generation_runs, job_resolution_attempts, source_configs exist."""
    eng = create_engine(Settings().database_url_sync)
    with eng.connect() as conn:
        r = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='jobs' ORDER BY ordinal_position"
            )
        )
        cols = {row[0] for row in r}
        for c in (
            "source_role",
            "canonical_source_name",
            "generation_eligibility",
            "artifact_ready_at",
            "resolution_status",
            "stale_flag",
        ):
            assert c in cols, f"jobs missing column {c}"

        for tbl in ("generation_runs", "job_resolution_attempts", "source_configs"):
            r2 = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables WHERE table_name=:t"
                ),
                {"t": tbl},
            )
            assert r2.fetchone(), f"table {tbl} missing"


def test_job_new_columns_persist() -> None:
    """Job model: new canonical/generation/resolution columns persist."""
    unique = str(uuid.uuid4())[:8]
    company_name = f"TestCo_{unique}"
    dedup_hash = compute_dedup_hash_from_raw(
        company=company_name,
        title="Engineer",
        location="Remote",
        apply_url=f"https://example.com/job/{unique}",
    )
    with get_sync_session() as session:
        company = Company(name=company_name)
        session.add(company)
        session.flush()

        job = Job(
            source="greenhouse",
            title="Engineer",
            raw_title="Engineer",
            normalized_title="engineer",
            company_id=company.id,
            company_name_raw=company_name,
            raw_company=company_name,
            normalized_company=normalize_company(company_name),
            dedup_hash=dedup_hash,
            source_role=SourceRole.CANONICAL.value,
            source_confidence=0.95,
            canonical_source_name="greenhouse",
            canonical_external_id="123",
            canonical_url=f"https://boards.greenhouse.io/job/{unique}",
            workplace_type="remote",
            employment_type="full_time",
            department="Engineering",
            requisition_id="req-1",
            salary_currency="USD",
            salary_interval="year",
            location_structured_json={"country": "US", "remote": True},
            content_quality_score=0.9,
            generation_eligibility=GenerationEligibility.ELIGIBLE.value,
            generation_reason="threshold_met",
            resolution_status=ResolutionStatus.RESOLVED_CANONICAL.value,
            resolution_confidence=0.98,
        )
        session.add(job)
        session.flush()
        job_id = job.id
        session.commit()

    with get_sync_session() as session:
        loaded = session.get(Job, job_id)
        assert loaded is not None
        assert loaded.source_role == SourceRole.CANONICAL.value
        assert loaded.source_confidence == 0.95
        assert loaded.canonical_source_name == "greenhouse"
        assert loaded.generation_eligibility == GenerationEligibility.ELIGIBLE.value
        assert loaded.resolution_status == ResolutionStatus.RESOLVED_CANONICAL.value
        assert loaded.stale_flag is False


def test_generation_run_crud() -> None:
    """GenerationRun: create and read."""
    unique = str(uuid.uuid4())[:8]
    dedup_hash = compute_dedup_hash_from_raw(
        company=f"Co_{unique}",
        title="Dev",
        location="NYC",
        apply_url=f"https://ex.com/{unique}",
    )
    with get_sync_session() as session:
        company = Company(name=f"Co_{unique}")
        session.add(company)
        session.flush()
        job = Job(
            source="lever",
            title="Dev",
            raw_title="Dev",
            normalized_title="dev",
            company_id=company.id,
            company_name_raw=company.name,
            raw_company=company.name,
            normalized_company=company.name,
            dedup_hash=dedup_hash,
        )
        session.add(job)
        session.flush()

        run = GenerationRun(
            job_id=job.id,
            status="success",
            inputs_hash="abc123",
            triggered_by="auto",
        )
        session.add(run)
        session.flush()
        run_id = run.id
        session.commit()

    with get_sync_session() as session:
        loaded = session.get(GenerationRun, run_id)
        assert loaded is not None
        assert loaded.status == "success"
        assert loaded.triggered_by == "auto"


def test_job_resolution_attempt_crud() -> None:
    """JobResolutionAttempt: create and read."""
    unique = str(uuid.uuid4())[:8]
    dedup_hash = compute_dedup_hash_from_raw(
        company=f"C_{unique}",
        title="Eng",
        location="Remote",
        apply_url=f"https://x.com/{unique}",
    )
    with get_sync_session() as session:
        company = Company(name=f"C_{unique}")
        session.add(company)
        session.flush()
        job = Job(
            source="agg1",
            title="Eng",
            raw_title="Eng",
            normalized_title="eng",
            company_id=company.id,
            company_name_raw=company.name,
            raw_company=company.name,
            normalized_company=company.name,
            dedup_hash=dedup_hash,
            source_role=SourceRole.DISCOVERY.value,
        )
        session.add(job)
        session.flush()

        attempt = JobResolutionAttempt(
            job_id=job.id,
            resolution_status=ResolutionStatus.RESOLVED_CANONICAL.value,
            confidence=0.85,
            canonical_url=f"https://greenhouse.io/job/{unique}",
            canonical_source_name="greenhouse",
        )
        session.add(attempt)
        session.flush()
        attempt_id = attempt.id
        session.commit()

    with get_sync_session() as session:
        loaded = session.get(JobResolutionAttempt, attempt_id)
        assert loaded is not None
        assert loaded.resolution_status == ResolutionStatus.RESOLVED_CANONICAL.value
        assert loaded.canonical_source_name == "greenhouse"


def test_source_config_crud() -> None:
    """SourceConfig: create and read (feature flags)."""
    unique = str(uuid.uuid4())[:8]
    with get_sync_session() as session:
        cfg = SourceConfig(
            source_name=f"test_source_{unique}",
            config_key=f"enabled_{unique}",
            config_value_json={"value": True},
        )
        session.add(cfg)
        session.flush()
        cfg_id = cfg.id
        session.commit()

    with get_sync_session() as session:
        loaded = session.get(SourceConfig, cfg_id)
        assert loaded is not None
        assert loaded.source_name == f"test_source_{unique}"
        assert loaded.config_key == f"enabled_{unique}"
        assert loaded.config_value_json == {"value": True}
