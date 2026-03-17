# Follow-up: Discovery Lane (PR 4)

## Scope delivered

- `POST /api/jobs/run-discovery` — triggers AGG-1 or SERP1 connector
- AGG-1 connector (Adzuna API as reference implementation)
- Optional SERP1 connector stub (feature-flagged)
- Discovery-source normalization to canonical schema
- Minimal provenance wiring: `source_role=discovery`, `resolution_status=pending`, `source_confidence`
- Feature flags: `ENABLE_AGG1_DISCOVERY`, `ENABLE_SERP1_DISCOVERY`

## Dependencies for canonical-resolution work

1. **Discovery-to-canonical resolution** — `POST /api/jobs/{id}/resolve` implemented. When a discovery job's apply URL matches Greenhouse/Lever/Ashby, the system fetches and merges canonical data. Resolution attempts are recorded in `job_resolution_attempts`.

2. **Generation gate** — Implemented (PR 5). Discovery records use stricter threshold; canonical at moderate threshold; SERP-only unresolved not eligible by default.

3. **Source confidence** — Current heuristic: base 0.5 + description length + apply_url + location. Can be refined in PR 5 when generation eligibility is wired.

## Dependencies for automation work

- Discovery jobs chain to `score_jobs -> classify_jobs -> ats_match_resume` (implemented)
- Generation gate gates `generate_grounded_resume_task` for discovery records (implemented)
- Ready-to-apply feed should filter by `source_confidence` / `resolution_status` when implemented (PR 5/6)

## Adzuna (AGG-1) configuration

Set in `.env`:

```
ENABLE_AGG1_DISCOVERY=true
ADZUNA_APP_ID=<from developer.adzuna.com>
ADZUNA_APP_KEY=<from developer.adzuna.com>
ADZUNA_COUNTRY=us
```

If `ENABLE_AGG1_DISCOVERY=true` but credentials are missing, the task will return an error in the run's `error_text`.

## SERP1 (explicit stub)

SERP1 is an **intentional stub** that returns empty results. Behavior:

- **When disabled** (`ENABLE_SERP1_DISCOVERY=false`, default): run-discovery with `connector=serp1` returns 403.
- **When enabled**: run-discovery enqueues the task; `fetch_raw_jobs` returns `FetchResult(raw_jobs=[], stats={"fetched":0,"errors":0}, error=None)`. The pipeline completes successfully with 0 inserted. Never raises; fails safely.

No external API calls. No credentials required. Enables route/task wiring and feature-flag discipline.

**Future implementation (optional):** Add a SERP API (e.g. SerpAPI, Serper) with query-driven job search. Mark records as lower-confidence; never treat as canonical.
