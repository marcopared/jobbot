# EPIC 2: Canonical Data Model Hardening — Final Implementation Plan

## Current state

- **Schema**: Canonical columns and tables exist in [core/db/models.py](core/db/models.py) (Job with `pipeline_status`/`user_status`/raw/normalized, `JobSourceRecord`, `JobAnalysis`, Artifact metadata). All mutations are done at runtime: [apps/api/main.py](apps/api/main.py) runs `Base.metadata.create_all` plus many `ALTER TABLE ... IF NOT EXISTS` and a backfill `UPDATE` in `lifespan()`; [apps/worker/tasks/scrape.py](apps/worker/tasks/scrape.py) runs two `ALTER TABLE` calls.
- **Workers**: [apps/worker/tasks/score.py](apps/worker/tasks/score.py) sets `user_status = ARCHIVED` when score is below threshold (wrong: that is a user action). Score and ATS write only to `Job` columns; nothing writes to `job_analyses` or `job_sources`.
- **Alembic**: [alembic/env.py](alembic/env.py) is wired to `Base.metadata` and `Settings().database_url_sync`. No migrations exist yet.

---

## 1. Alembic migrations: two-step strategy

Use **two Alembic revisions**: baseline + reconciliation. Do not use a single revision. Do not rely on idempotent "add if missing" as the primary strategy. For existing unversioned DBs with schema drift from `create_all()` plus startup `ALTER TABLE`: `alembic stamp <baseline_rev>` then `alembic upgrade head`.

**1.1 Ensure migration environment**

- Ensure `alembic/versions` exists. In [alembic/env.py](alembic/env.py), in `run_migrations_online()`, build the engine from `settings.database_url_sync` so the app and migrations use the same URL.

**1.2 Baseline revision**

- Create a baseline Alembic revision representing the schema Alembic will consider as the starting point for fresh installs. This revision establishes the migration history root. For existing unversioned DBs, do **not** run it; instead `alembic stamp <baseline_rev>` to mark the DB as at baseline.

**1.3 Reconciliation revision**

- **jobs**: Add canonical columns: `raw_company`, `raw_title`, `raw_location`, `normalized_company`, `normalized_title`, `normalized_location`, `pipeline_status`, `user_status`, `source_payload_json`. Add indexes `ix_jobs_pipeline_status`, `ix_jobs_user_status`; ensure `dedup_hash` unique constraint. The reconciliation migration uses conditional DDL (e.g. `existing_ok=True`) where needed for DBs stamped at baseline that already have some columns.
- **Normalized/raw backfill**: Use **plain copy** (no SQL normalization). Set `raw_company = company_name_raw`, `normalized_company = company_name_raw`, `raw_title = title`, `normalized_title = title`, `raw_location = location`, `normalized_location = location`. Canonical normalization happens on future writes via ingestion/app logic. This is a coarse transitional backfill for speed.
- **user_status backfill**: Do **not** copy legacy `status` directly. Use an explicit `CASE` expression or mapping table:
  - `APPLIED` → `APPLIED`
  - archive/dismiss-like states (`REJECTED`, `ARCHIVED`, `INTERVENTION_REQUIRED`, `APPLY_FAILED`, `SKIPPED`) → `ARCHIVED`
  - approve/save-like states (`APPROVED`, `SAVED`) → `SAVED`
  - everything else (including `NEW`, `SCORED`, `APPLY_QUEUED`, unknown) → `NEW`
- **pipeline_status backfill**: Use explicit safe mappings only; otherwise default to `INGESTED`. Map e.g. `SCORED`, `REJECTED`, `ATS_ANALYZED` where you have a clear 1:1; for unknown or mixed states, default to `INGESTED`.
- **job_sources**: Create table with `job_id`, `source_name`, `external_id`, `raw_data`, `provenance_metadata`, `created_at`; unique on `(source_name, external_id)`; index on `job_id`.
- **job_analyses**: Create table with score/ATS fields; **add `UNIQUE(job_id)`** so v1 has exactly one current analysis row per job. Index on `job_id` (or rely on unique). Score and ATS tasks will upsert this single row.
- **artifacts**: Add `persona_name`, `file_url`, `format`, `version`, `prompt_version`, `template_version`, `inventory_version_hash`, `generation_status`.
- **scrape_runs**: Add `items_json` JSONB.

Do not drop or alter `applications` / `interventions`.

---

## 2. Remove all schema mutation from API and worker startup

- **[apps/api/main.py](apps/api/main.py)**: Remove **all** `ALTER TABLE`, the backfill `UPDATE`, and **`Base.metadata.create_all`** entirely. Keep only directory creation for `artifact_dir` and `profile_dir`. Require `alembic upgrade head` before startup. Document in README that deploy must run migrations first.
- **[apps/worker/tasks/scrape.py](apps/worker/tasks/scrape.py)**: Remove the two `session.execute(text("ALTER TABLE ... IF NOT EXISTS ..."))` calls for `jobs.source_payload_json` and `scrape_runs.items_json`.

---

## 3. Canonical-vs-legacy ownership

- **Document in [core/db/models.py](core/db/models.py)**: Canonical source of truth is `pipeline_status`, `user_status`, and raw/normalized title/company/location. Legacy `Job.status` is a compatibility mirror only.
- **Centralize legacy status mirror**: Add a single helper (e.g. in `core/db/` or `core/job_status.py`) that, given `pipeline_status` and `user_status`, returns the value to set for `Job.status`. All writers (API routes, score task, ATS task, scrape task) use this helper — no hand-rolled mirror logic in multiple places.
- **Legacy status mirror precedence** (exact order, implement once):
  1. If `pipeline_status = REJECTED` → `REJECTED`
  2. Else if `user_status = APPLIED` → `APPLIED`
  3. Else if `user_status = ARCHIVED` → `ARCHIVED`
  4. Else if `pipeline_status = SCORED` → `SCORED`
  5. Else → `NEW`
- **Legacy tables**: Add a comment above `Application` and `Intervention`: legacy/internal tables, not part of the canonical job pipeline; retained for compatibility only.
- **UI/API visibility**: The architecture defines `NEW` as a user workflow state for jobs ready for review, typically after the pipeline has advanced. `user_status = NEW` alone does not imply review-ready. The UI/API must key visibility off `pipeline_status` (e.g. hide `REJECTED` by default), not just `user_status`. List/detail APIs should filter by `pipeline_status` where appropriate.

---

## 4. Worker state transitions (pipeline vs user)

- **[apps/worker/tasks/score.py](apps/worker/tasks/score.py)**:
  - When `total < settings.scoring_threshold`: set only `pipeline_status = REJECTED`. Do **not** set `user_status` — leave it unchanged. Use the centralized mirror helper for `job.status`.
  - When `total >= threshold`: set `pipeline_status = SCORED`, leave `user_status` as `NEW`, use mirror helper for `job.status`.
  - Continue writing `score_total` and `score_breakdown_json` on `Job` (transitional); also upsert `job_analyses` row.

---

## 5. Canonical analysis storage (job_analyses)

- **One row per job**: Add `UNIQUE(job_id)` to `job_analyses` in model and migrations. Use upsert semantics (INSERT ... ON CONFLICT (job_id) DO UPDATE).
- **Score task**: Upsert `job_analyses` with `total_score` and breakdown (e.g. in `persona_specific_scores`). Keep writing to `Job` for transitional compatibility.
- **ATS task**: Upsert same `job_analyses` row with `ats_compatibility_score`, `found_keywords`, `missing_keywords`. Keep writing to `Job` for compatibility.
- Add comment: canonical score/ATS data lives in `job_analyses`; `Job` fields are transitional mirrors.

---

## 6. Scrape task: full provenance in job_sources

- **Rule**: Always insert a provenance row for every new `(source_name, external_id)` pair, even when the canonical job already exists due to dedup. Skip only when that exact `(source_name, external_id)` pair already exists (unique constraint enforces this).
- **Implementation**:
  - On new job insert: insert `JobSourceRecord` with `job_id`, `source_name`, `external_id`, `raw_data`.
  - On duplicate (existing job): still insert `JobSourceRecord` for the existing `job_id` if `(source_name, external_id)` is new. Use INSERT ... ON CONFLICT (source_name, external_id) DO NOTHING or equivalent.
  - Optionally backfill `source_payload_json` on existing job if still empty (current logic is fine).

---

## 7. Indexes and constraints

- **jobs**: Unique on `dedup_hash`; indexes on `pipeline_status`, `user_status`.
- **job_sources**: Unique on `(source_name, external_id)`; index on `job_id`.
- **job_analyses**: **Unique on `job_id`**; index on `job_id` (or rely on unique).

---

## 8. Backfill expectations

- **Raw/normalized**: Coarse backfill only; document that canonical normalization happens on future writes unless SQL normalization is used.
- **user_status**: Explicit mapping only — never direct copy from legacy `status`.
- **pipeline_status**: Explicit safe mappings; default to `INGESTED` for unknown.
- No ongoing backfill in app code.

---

## 9. Testing and execution order

- For existing unversioned DBs: `alembic stamp <baseline_rev>` then `alembic upgrade head`.
- For fresh installs: `alembic upgrade head`.
- Start API and worker; run scrape, score, ATS; verify jobs have `pipeline_status` set, low-score jobs do **not** have `user_status = ARCHIVED`, `job_sources` and `job_analyses` get rows.
- Run backend tests; fix any that assume startup DDL or old score behavior.

---

## Summary of deliverables

| Area | Action |
|------|--------|
| **Migrations** | Two-step: baseline + reconciliation. Explicit backfill mapping for user_status and pipeline_status. UNIQUE(job_id) on job_analyses. env.py uses Settings URL. |
| **Startup** | Remove all ALTER/UPDATE from main.py. **Remove create_all completely.** Require `alembic upgrade head` before start. Remove ALTER from scrape task. |
| **Ownership** | Document canonical vs legacy; single legacy-status mirror helper; annotate Application/Intervention as legacy. |
| **Score task** | Never set user_status when rejecting; use mirror helper; write to job_analyses. |
| **ATS task** | Upsert job_analyses; use mirror helper if it writes legacy status. |
| **Scrape task** | Insert JobSourceRecord for every new (source_name, external_id) pair, including when job exists by dedup; remove in-task ALTER. |
| **Legacy tables** | Keep; do not delete; comment as legacy/internal. |

**Remaining transitional debt**: API/UI read score/ATS from `Job`; legacy `Job.status` written via mirror helper; full reader migration to `job_analyses` is a follow-up.
