# JobBot Specification (Current Scope)

This spec defines what JobBot supports today. It is the source of truth for active
features and runtime behavior.

## 1) Product Scope

Implemented:

1. Scrape job listings (JobSpy-first).
2. Store and deduplicate jobs in Postgres.
3. Score and rank jobs.
4. Run ATS keyword extraction and ATS match scoring against a base resume.
5. Generate resume artifacts/tailored resume outputs for operator use.
6. Support manual operator review flows (approve/reject/intervention handling).

Not implemented:

- Auto-apply / automatic browser submission.

## 2) Explicit Boundaries

- No extension-dependent runtime.
- No auto-submit of applications.
- No queue/retry apply UX.
- No claim that application automation is currently functional.

Legacy apply-oriented DB enums/status fields may remain for compatibility, but they
are not an active product capability.

## 3) Core Runtime

### Backend

- FastAPI app in `apps/api`.
- SQLAlchemy models in `core/db`.
- Startup auto-creates storage directories and schema tables.

### Workers

- Celery app in `apps/worker/celery_app.py`.
- Active work: scrape, score, ATS matching, resume prep, notifications.

### UI

- React/Vite frontend in `ui`.
- Operator workflows: review jobs, inspect scoring/ATS signals, manage interventions.

## 4) Environment Variables

```bash
# Core
APP_ENV=dev
LOG_LEVEL=DEBUG
API_HOST=0.0.0.0
API_PORT=8000
UI_BASE_URL=http://localhost:5173

# Data
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/jobbot
DATABASE_URL_SYNC=postgresql+psycopg2://postgres:postgres@localhost:5432/jobbot
REDIS_URL=redis://localhost:6379/0

# Storage
ARTIFACT_DIR=./storage/artifacts
PROFILE_DIR=./storage/profiles

# Scrape defaults
DEFAULT_SEARCH_QUERY=backend engineer fintech
DEFAULT_LOCATION=New York, NY
SCRAPE_HOURS_OLD=48
SCRAPE_RESULTS_WANTED=50

# Scraper flags
JOBSPY_ENABLED=true
WELLFOUND_ENABLED=false
BUILTINNYC_ENABLED=false
YC_ENABLED=false

# Optional integrations
APOLLO_API_KEY=
SCRAPEOPS_API_KEY=

# Notifications
PUSH_PROVIDER=pushover
PUSHOVER_TOKEN=
PUSHOVER_USER=
NTFY_TOPIC_URL=

# Resume / ATS
BASE_RESUME_PATH=./storage/base_resume.pdf
MASTER_SKILLS_PATH=./storage/master_skills.json
RESUME_TAILOR_ENABLED=true

# Playwright runtime defaults
PLAYWRIGHT_HEADFUL=true
PLAYWRIGHT_SLOW_MO_MS=0
PLAYWRIGHT_PROFILE_NAME=default
PLAYWRIGHT_TIMEOUT_MS=30000
```

## 5) API Contract

### Health

- `GET /api/health` -> `{ "status": "ok" }`

### Jobs

- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/run-scrape`
- `POST /api/jobs/bulk-approve`
- `POST /api/jobs/bulk-reject`
- `POST /api/jobs/{job_id}/approve`
- `POST /api/jobs/{job_id}/reject`

### Interventions

- `GET /api/interventions`
- `GET /api/interventions/{id}`
- `POST /api/interventions/{id}/resolve`
- `POST /api/interventions/{id}/abort`

### Applications

- `GET /api/applications`
- `GET /api/applications/{id}`

### Artifacts

- `GET /api/artifacts/{id}/download`
- `GET /api/artifacts/{id}/preview`

### Runs

- `GET /api/runs`
- `GET /api/runs/{id}`
- `GET /api/runs/{id}/items`

## 6) UI Contract

### Jobs Page

- List/filter/sort jobs.
- Bulk approve/reject.
- No auto-apply button.

### Job Detail Page

- View job description/source payload.
- View score + ATS match breakdown.
- Approve/reject.
- No auto-apply action.

### Interventions Page

- List interventions by status.
- Resolve and abort interventions.
- No apply-retry action.

### Runs / Applications

- Inspect historical execution outputs and application records.

## 7) Acceptance Criteria

1. No active code path depends on extension-specific env vars or extension assets.
2. Auto-apply endpoints are not exposed in the active API surface.
3. UI does not expose queue/retry apply controls.
4. Scrape -> score -> ATS -> resume workflows remain operational.
5. README, architecture doc, spec, and TODO all describe the same reduced scope.

## 8) Future Direction (Non-Implemented)

After scraping, scoring, ATS analysis, and resume customization are stable, optional
auto-apply can be researched as a separate future workstream.
