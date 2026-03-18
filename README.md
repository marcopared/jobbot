# JobBot

JobBot is a local-first job discovery and decision-support tool.

Alpha discovery implementation wave note: the current system still reflects the implemented scope below. Tonight's target implementation wave maps `AGG-1` to Adzuna and `SERP1` to DataForSEO Google Jobs once those code PRs land.

## Implemented scope

**Ingestion:**
- **Canonical ATS:** Greenhouse, Lever, Ashby
- **Discovery:** JobSpy (scrape), AGG-1, SERP1 (latter two feature-flagged)
- **URL ingest:** supported ATS job URLs (Greenhouse, Lever, Ashby)

**Processing:** store, score, classify, ATS analysis; generation gate (auto-generate for eligible jobs when enabled)

**Output:** job-specific resume artifacts; ready-to-apply queue; manual apply via job URL

**Non-goals:** auto-apply, browser automation; final application step is always manual.

## Planned next alpha wave

Planned implementation order for the next code PRs: `AGG-1` Adzuna hardening, `SERP1` DataForSEO Google Jobs implementation, discovery end-to-end verification, then optional UI polish. For this wave, `AGG-1` maps to Adzuna and `SERP1` maps to DataForSEO Google Jobs. This is planned work only; the implemented scope above remains the current truth until those PRs land.

## Documentation

- Product behavior and boundaries: `docs/SPEC.md`
- System components and data flow: `docs/ARCHITECTURE.md`
- Active backlog and roadmap: `docs/TODO.md`
- PR boundaries and implementation order: `docs/IMPLEMENTATION_PLAN.md`
- Coding-agent operating instructions: `docs/CODING_AGENT_GUIDE.md`

See `docs/README.md` for the authoritative docs index and current-system summary.

## Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Node.js 18+

## Initial Setup

```bash
cp .env.example .env
pip install -r requirements.txt
playwright install chromium
cd ui && npm install && cd ..
```

**Required before first run:**
- `playwright install chromium` — PDF resume generation uses Playwright; omit and resumes will fail.
- `alembic upgrade head` — Schema is managed by Alembic; run migrations before starting the API.

## Run Locally

### Option A: one command

```bash
bash scripts/dev.sh
```

This starts Postgres + Redis (Docker), runs migrations, then launches FastAPI, Celery worker, and Vite UI.

- API: `http://127.0.0.1:8000`
- UI: `http://127.0.0.1:5173`

### Option B: manual terminals

```bash
docker compose up -d
# Wait for Postgres, then:
alembic upgrade head
PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000
PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape,ingestion
cd ui && npm run dev -- --host 127.0.0.1 --port 5173
```

## Ingestion paths

| Path | Endpoint | Role | Use case |
|------|----------|------|----------|
| **JobSpy scrape** | `POST /api/jobs/run-scrape` | Discovery | Scrapes job boards via JobSpy. Uses `.env` defaults or optional body params. |
| **Canonical ATS** | `POST /api/jobs/run-ingestion` | Canonical | Greenhouse, Lever, Ashby. Requires connector-specific params (e.g. `board_token` for greenhouse, `client_name` for lever). |
| **Broad discovery** | `POST /api/jobs/run-discovery` | Discovery | AGG-1 or SERP1. Feature-flagged (`ENABLE_AGG1_DISCOVERY`, `ENABLE_SERP1_DISCOVERY`). |
| **URL ingest** | `POST /api/jobs/ingest-url` | Canonical | Paste supported Greenhouse/Lever/Ashby job URL. Feature-flagged (`URL_INGEST_ENABLED`). |

All paths run score → classify → ATS analysis. Resume generation: manual via `POST /api/jobs/{id}/generate-resume`, or automatic when `ENABLE_AUTO_RESUME_GENERATION=true` and the job passes the generation gate.

### Example: JobSpy scrape

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/run-scrape
# Optional body: {"query":"backend engineer","location":"Remote","hours_old":48,"results_wanted":50}
```

### Example: Canonical ATS ingestion

```bash
# Greenhouse
curl -X POST http://127.0.0.1:8000/api/jobs/run-ingestion \
  -H "Content-Type: application/json" \
  -d '{"connector":"greenhouse","board_token":"acme","company_name":"Acme Corp"}'

# Lever (requires client_name)
curl -X POST http://127.0.0.1:8000/api/jobs/run-ingestion \
  -H "Content-Type: application/json" \
  -d '{"connector":"lever","company_name":"Acme","client_name":"acme"}'

# Ashby (requires job_board_name)
curl -X POST http://127.0.0.1:8000/api/jobs/run-ingestion \
  -H "Content-Type: application/json" \
  -d '{"connector":"ashby","company_name":"Acme","job_board_name":"acme"}'
```

### Seed data (quick start)

With API + worker running:

```bash
bash scripts/seed.sh
```

Runs `POST /api/jobs/run-scrape` and waits for completion.

## Useful endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Health check |
| `GET /api/jobs` | List jobs (supports user_status, pipeline_status, persona filters) |
| `GET /api/jobs/ready-to-apply` | Jobs with artifact ready for manual apply (default operational view) |
| `GET /api/jobs/{id}` | Job detail with scores, persona, ATS gaps |
| `PUT /api/jobs/{id}/status` | Update user workflow status (SAVED, APPLIED, ARCHIVED) |
| `POST /api/jobs/{id}/resolve` | Trigger discovery-to-canonical resolution (discovery jobs only) |
| `POST /api/jobs/{id}/generate-resume` | Trigger tailored resume generation (manual override) |
| `GET /api/jobs/{id}/artifacts` | List artifacts for a job |
| `GET /api/runs` | List scrape/ingest/discovery runs |
| `GET /api/runs/{id}` | Run detail |
| `GET /api/debug/failures` | Recent task failures (debug-only; requires `DEBUG_ENDPOINTS_ENABLED=true`) |
| `WS /ws/logs` | WebSocket log stream (debug-only; requires `DEBUG_ENDPOINTS_ENABLED=true`) |

Debug endpoints are disabled by default; enable only for local/dev use.

## Storage

- `storage/artifacts/` — generated resumes and snapshots (local mode)
- `storage/profiles/` — Playwright profiles (if used)

Artifact and profile directories are created on API startup.

### Artifact Storage Backends

| Provider | Use case |
|----------|----------|
| **local** (default) | Development. Stores PDFs under `ARTIFACT_DIR`. |
| **gcs** | Production. Stores PDFs in Google Cloud Storage. Objects are private; preview/download routes generate signed URLs on demand. |

**GCS configuration:**

1. Set `ARTIFACT_STORAGE_PROVIDER=gcs`, `GCS_ARTIFACT_BUCKET=your-bucket`, and optionally `GCS_PROJECT_ID`, `GCS_PREFIX`, `GCS_SIGNED_URL_TTL_SECONDS`.
2. Authenticate via **Application Default Credentials**:
   - **Local dev:** Set `GOOGLE_APPLICATION_CREDENTIALS` to the path of a service account JSON key file.
   - **Deployed:** Use an attached service account with `storage.objects.create` and `storage.objects.get` permissions.

**Signed URL credential caveat:** Preview/download routes generate signed URLs for GCS-backed artifacts. Signed URL generation requires a **service account with a private key** (e.g. `GOOGLE_APPLICATION_CREDENTIALS` pointing to a JSON key file). User credentials from `gcloud auth application-default login` do not include a private key and cannot sign URLs. Ensure your service account has `storage.objects.create` and `storage.objects.get` IAM roles.
