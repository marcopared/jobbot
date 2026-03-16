# JobBot

JobBot is a local-first job discovery and decision-support tool.

Current implemented scope:
- scrape jobs (JobSpy) and ingest via connectors (Greenhouse)
- store, score, and rank jobs
- run ATS keyword extraction and ATS match scoring
- generate job-specific resume artifacts from your experience inventory and skills data
- support manual operator review workflows

Auto-apply is intentionally **not** part of the current product scope. Users manually apply via the job URL.

## Documentation

- Product behavior and boundaries: `docs/SPEC.md`
- System components and data flow: `docs/ARCHITECTURE.md`
- Active backlog and roadmap: `docs/TODO.md`

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

## Ingestion Paths

Two ways to bring jobs into the pipeline:

| Path | Endpoint | Use case |
|------|----------|----------|
| **JobSpy scrape** | `POST /api/jobs/run-scrape` | Scrapes job boards (Glassdoor, LinkedIn, etc.) via JobSpy. Uses defaults from `.env` or optional body params. |
| **Greenhouse connector** | `POST /api/jobs/run-ingestion` | Fetches from Greenhouse ATS API. Requires `board_token` and `company_name`. |

Both paths enqueue Celery tasks that run score → classify → ATS analysis. Resume generation is manual: `POST /api/jobs/{id}/generate-resume`.

### Trigger JobSpy scrape

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/run-scrape
# Optional body: {"query":"backend engineer","location":"Remote","hours_old":48,"results_wanted":50}
```

### Trigger Greenhouse ingestion

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/run-ingestion \
  -H "Content-Type: application/json" \
  -d '{"connector":"greenhouse","board_token":"acme","company_name":"Acme Corp"}'
```

### Seed data (quick start)

With API + worker running:

```bash
bash scripts/seed.sh
```

Runs `POST /api/jobs/run-scrape` and waits for completion.

## Useful Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Health check |
| `GET /api/jobs` | List jobs (supports user_status, pipeline_status, persona filters) |
| `GET /api/jobs/{id}` | Job detail with scores, persona, ATS gaps |
| `PUT /api/jobs/{id}/status` | Update user workflow status (SAVED, APPLIED, ARCHIVED) |
| `POST /api/jobs/{id}/generate-resume` | Trigger tailored resume generation |
| `GET /api/jobs/{id}/artifacts` | List artifacts for a job |
| `GET /api/runs` | List scrape/ingest runs |
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
