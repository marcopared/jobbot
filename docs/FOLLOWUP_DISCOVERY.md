# Follow-up: Discovery Lane (PR 4)

## Scope delivered

- `POST /api/jobs/run-discovery` — triggers AGG-1 or SERP1 connector
- AGG-1 lane in the repo baseline
- SERP1 lane in the repo baseline
- Discovery-source normalization to canonical schema
- Minimal provenance wiring: `source_role=discovery`, `resolution_status=pending`, `source_confidence`
- Feature flags: `ENABLE_AGG1_DISCOVERY`, `ENABLE_SERP1_DISCOVERY`

## Current repo truth vs alpha implementation target

Current repo truth:

- discovery route/task wiring exists for AGG-1 and SERP1 lanes
- the repo baseline may still contain partial, placeholder, or stubbed provider behavior
- this document must not claim the real Adzuna and DataForSEO implementations have already landed unless the code does

Alpha implementation target for this wave:

- Adzuna is the real `AGG-1` provider for this wave
- DataForSEO Google Jobs is the real `SERP1` provider target for this wave
- the work required now is provider completion and hardening, not replacement with new abstractions or new provider lanes

## Dependencies for canonical-resolution work

1. **Discovery-to-canonical resolution** — `POST /api/jobs/{id}/resolve` implemented. When a discovery job's apply URL matches Greenhouse/Lever/Ashby, the system fetches and merges canonical data. Resolution attempts are recorded in `job_resolution_attempts`.

2. **Generation gate** — Implemented (PR 5). Discovery records use stricter threshold; canonical at moderate threshold; SERP-only unresolved not eligible by default.

3. **Source confidence** — Current heuristic: base 0.5 + description length + apply_url + location. Can be refined in PR 5 when generation eligibility is wired.

## Dependencies for automation work

- Discovery jobs chain to `score_jobs -> classify_jobs -> ats_match_resume` (implemented)
- Generation gate gates `generate_grounded_resume_task` for discovery records (implemented)
- Ready-to-apply feed should filter by `source_confidence` / `resolution_status` when implemented (PR 5/6)

## Provider contract: Adzuna (`AGG-1`)

Adzuna is not a reference-only provider in this wave. It is the actual structured discovery provider for the alpha path and needs production hardening. Treat this work as hardening the existing `AGG-1` alpha lane, not replacing it with a different abstraction or provider.

Implementation expectations:

- use real Adzuna search API retrieval
- fetch multiple pages per run, subject to an explicit run cap
- support useful filters at minimum: keyword/title query, location, age/freshness, salary bounds, and employment-type filters
- normalize discovered jobs into the shared discovery model
- preserve unmapped provider fields in `raw_payload`
- add tests that cover pagination, normalization, and failure handling

## Provider contract: DataForSEO Google Jobs (`SERP1`)

Current repo baseline may still be stubbed, but the target for this wave is a real DataForSEO Google Jobs implementation.

Implementation expectations:

- use DataForSEO Google Jobs endpoints only
- do not use generic organic SERP endpoints for this wave
- authenticate with basic auth
- implement `task_post + bounded polling + task_get/advanced`
- use bounded polling for readiness with explicit attempt and/or wall-clock limits
- normalize Google Jobs results into the shared discovery model
- preserve provider provenance and lower-confidence semantics
- add tests that cover task submission, timeout/failure behavior, and normalization

## Adzuna (AGG-1) configuration

Set in `.env`:

```
ENABLE_AGG1_DISCOVERY=true
ADZUNA_APP_ID=<from developer.adzuna.com>
ADZUNA_APP_KEY=<from developer.adzuna.com>
ADZUNA_COUNTRY=us
```

If `ENABLE_AGG1_DISCOVERY=true` but credentials are missing, the task will return an error in the run's `error_text`.

## SERP1 baseline vs target

Current repo baseline may still behave like an intentional stub that returns empty results. If so, baseline behavior is:

- **When disabled** (`ENABLE_SERP1_DISCOVERY=false`, default): run-discovery with `connector=serp1` returns 403.
- **When enabled**: run-discovery enqueues the task; `fetch_raw_jobs` returns `FetchResult(raw_jobs=[], stats={"fetched":0,"errors":0}, error=None)`. The pipeline completes successfully with 0 inserted. Never raises; fails safely.

That baseline is not the alpha target.

Alpha target behavior:

- use DataForSEO Google Jobs only
- perform `task_post + bounded polling + task_get/advanced`
- normalize results into the existing discovery flow
- keep SERP records lower-confidence than Adzuna and canonical ATS
- never treat SERP results as canonical truth
- do not route this wave through generic organic SERP endpoints

## Non-goals preserved

- no browser automation
- no auto-apply
- no generic arbitrary crawling

## Implementation decisions frozen for alpha

- Adzuna is page-based and bounded per run.
- DataForSEO uses a bounded synchronous wrapper over `task_post` and `task_get`.
- No new migration is required by default for this wave.
- Preserve unmapped provider fields in `raw_payload`.
- No generic crawler work is in scope for this wave.
