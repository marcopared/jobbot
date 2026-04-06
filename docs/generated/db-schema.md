# Database Schema Summary

Generated-style summary of the current database model, based on
[core/db/models.py](../../core/db/models.py) and the Alembic migrations
present on 2026-03-24.

## Primary Tables

### `companies`

Purpose:
- normalized company records referenced by jobs

Key fields:
- `id`
- `name`
- `domain`
- `linkedin_url`
- `apollo_id`

### `jobs`

Purpose:
- canonical storage for all ingested jobs regardless of source

Key fields:
- source identity:
  `source`, `source_job_id`, `source_role`, `source_confidence`
- canonical identity:
  `canonical_source_name`, `canonical_external_id`, `canonical_url`
- normalized identity:
  `normalized_company`, `normalized_title`, `normalized_location`, `dedup_hash`
- pipeline:
  `pipeline_status`, `user_status`, `score_total`
- generation:
  `generation_eligibility`, `generation_reason`, `artifact_ready_at`, `auto_generated_at`
- resolution:
  `resolution_status`, `resolution_confidence`

Relationships:
- `artifacts`
- `analyses`
- `sources`
- `generation_runs`
- `resolution_attempts`

### `job_sources`

Purpose:
- provenance records per provider/source for a job

Key fields:
- `job_id`
- `source_name`
- `external_id`
- `raw_data`
- `provenance_metadata`

Unique index:
- `(source_name, external_id)`

### `job_analyses`

Purpose:
- persisted score/classification/ATS analysis state

Key fields:
- `job_id`
- `total_score`
- `matched_persona`
- `persona_confidence`
- `missing_keywords`
- `found_keywords`
- `ats_categories`
- `ats_compatibility_score`

Unique index:
- `job_id`

### `generation_runs`

Purpose:
- durable lifecycle for manual and auto resume generation

Key fields:
- `job_id`
- `status`
- `triggered_by`
- `failure_reason`
- `artifact_id`
- `finished_at`

### `job_resolution_attempts`

Purpose:
- audit trail for discovery-to-canonical resolution attempts

Key fields:
- `job_id`
- `resolution_status`
- `confidence`
- `failure_reason`
- `canonical_url`
- `canonical_source_name`
- `attempted_at`

### `source_configs`

Purpose:
- source-scoped configuration table

Key fields:
- `source_name`
- `config_key`
- `config_value_json`

Unique index:
- `(source_name, config_key)`

### `scrape_runs`

Purpose:
- durable run tracking for scrape, ingest, discovery, URL ingest, and manual intake launches

Key fields:
- `source`
- `status`
- `params_json`
- `stats_json`
- `items_json`
- `error_text`
- `started_at`
- `finished_at`

## Artifact Tables

### `artifacts`

Purpose:
- generated PDFs and other file artifacts

Key fields:
- `job_id`
- `kind`
- `filename`
- `path`
- `persona_name`
- `generation_status`
- `file_url`

## Legacy Tables Still Present

### `applications`

Legacy apply-flow table retained for compatibility. Not part of the current product loop.

### `interventions`

Legacy intervention table retained for compatibility. Not part of the current product loop.

## Notes

1. `jobs.dedup_hash` is the main duplicate suppression key.
2. `job_analyses` is the canonical persisted analysis table even though some mirrored fields still
   exist on `jobs`.
3. `ScrapeRun.items_json` has a canonical normalization layer in
   [core/run_items.py](../../core/run_items.py).
