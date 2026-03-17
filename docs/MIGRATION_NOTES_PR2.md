# Migration Notes: PR 2 — DB Model Foundation

## Summary

Migration `004_db_foundation` adds schema support for:
- Canonical ATS expansion (Greenhouse, Lever, Ashby)
- Discovery vs canonical distinction
- URL ingest support
- Generation eligibility tracking
- Provenance / resolution tracking

## Files Touched

| File | Change |
|------|--------|
| `core/db/models.py` | Enums, Job columns, GenerationRun, JobResolutionAttempt, SourceConfig |
| `alembic/versions/004_db_model_foundation.py` | Migration |
| `tests/test_db_model_foundation.py` | Model integrity tests |

## Migration Behavior

- **Idempotent**: Uses `ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`.
- **Backfill**: No data backfill. New columns are nullable (except `stale_flag`). Existing jobs remain valid; new columns default to `NULL` or `false`.
- **Downgrade**: Removes all added columns and tables; order ensures no FK violations.

## New Job Columns

| Column | Type | Purpose |
|--------|------|---------|
| `source_role` | TEXT | `canonical`, `discovery`, `url_ingest` |
| `source_confidence` | FLOAT | 0–1 confidence in source |
| `canonical_source_name` | TEXT | ATS name when resolved (greenhouse, lever, ashby) |
| `canonical_external_id` | TEXT | Provider ID |
| `canonical_url` | TEXT | Canonical job posting URL |
| `workplace_type` | TEXT | remote, onsite, hybrid |
| `employment_type` | TEXT | full_time, part_time, contract, etc. |
| `department` | TEXT | Department label |
| `team` | TEXT | Team label |
| `requisition_id` | TEXT | Requisition / job ID |
| `salary_currency` | TEXT | ISO currency |
| `salary_interval` | TEXT | hour, day, week, month, year |
| `location_structured_json` | JSONB | Structured location |
| `content_quality_score` | FLOAT | 0–1 |
| `generation_eligibility` | TEXT | eligible, ineligible, pending |
| `generation_reason` | TEXT | Reason code / text |
| `auto_generated_at` | TIMESTAMPTZ | When artifact was auto-generated |
| `artifact_ready_at` | TIMESTAMPTZ | When artifact became ready |
| `resolution_status` | TEXT | pending, resolved_canonical, etc. |
| `resolution_confidence` | FLOAT | 0–1 |
| `stale_flag` | BOOLEAN | Default false |

## New Tables

### generation_runs
Tracks generation attempts (auto and manual). Columns: `job_id`, `status`, `inputs_hash`, `failure_reason`, `artifact_id`, `triggered_by`, timestamps.

### job_resolution_attempts
Tracks discovery→canonical resolution attempts. Columns: `job_id`, `resolution_status`, `confidence`, `failure_reason`, `canonical_url`, `canonical_source_name`, `attempted_at`.

### source_configs
Feature flags and source config. Columns: `source_name`, `config_key`, `config_value_json`. UNIQUE(source_name, config_key).

## Enums (Python; stored as TEXT in DB)

- `SourceRole`: CANONICAL, DISCOVERY, URL_INGEST
- `ResolutionStatus`: PENDING, RESOLVED_CANONICAL, RESOLVED_DISCOVERY_ONLY, FAILED, SKIPPED, NOT_APPLICABLE
- `GenerationEligibility`: ELIGIBLE, INELIGIBLE, PENDING
- `WorkplaceType`: REMOTE, ONSITE, HYBRID, OTHER
- `EmploymentType`: FULL_TIME, PART_TIME, CONTRACT, INTERNSHIP, OTHER
- `SalaryInterval`: HOUR, DAY, WEEK, MONTH, YEAR
- `GenerationRunStatus`: QUEUED, RUNNING, SUCCESS, FAILED, SKIPPED

## Downstream Assumptions for Later Agents

### PR 3 (ATS expansion)
- Connectors must set `source_role` = `canonical` for Greenhouse, Lever, Ashby.
- URL ingest route must set `source_role` = `url_ingest` and populate `canonical_url`, `canonical_source_name`, `canonical_external_id` when known.
- Use `JobSourceRecord` (job_sources) for provenance; `source_role` and `source_confidence` live on Job.

### PR 4 (Discovery)
- Discovery connectors must set `source_role` = `discovery`.
- AGG-1 / SERP jobs start with `resolution_status` = `pending` or `not_applicable`.
- Resolution worker updates `resolution_status`, `resolution_confidence`, `canonical_*` and inserts `JobResolutionAttempt` rows.

### PR 5 (Automation)
- Generation gate writes `generation_eligibility`, `generation_reason`.
- On successful auto-generation: set `auto_generated_at`, `artifact_ready_at`, insert `GenerationRun` row.
- Ready-to-apply query: `artifact_ready_at IS NOT NULL AND apply_url IS NOT NULL AND stale_flag = false`.

### General
- Legacy `Job.source` and `Job.source_job_id` remain for compatibility; prefer `source_role` + `canonical_source_name` / `canonical_external_id` for new logic.
- `source_configs` can store feature flags: e.g. `source_name='lever'`, `config_key='enabled'`, `config_value_json={'value': true}`.
