# JobBot

JobBot is a local-first job discovery and decision-support tool.

## Implemented scope

**Ingestion:**
- **Canonical ATS:** Greenhouse, Lever, Ashby
- **Discovery:** JobSpy scrape, AGG-1, SERP1 (`AGG-1` and `SERP1` remain feature-flagged)
- **Adapter-backed discovery launchers:**  
  public boards: StartupJobs NYC, Built In NYC, Welcome to the Jungle  
  portfolio boards: Tech:NYC, Primary Venture Partners, Greycroft, USV  
  auth boards: LinkedIn Jobs, Wellfound, YC (`auth_board` sources remain gated by source flags and `BB_BROWSER_ENABLED`)
- **URL ingest:** supported ATS job URLs (Greenhouse, Lever, Ashby)
- **Manual intake:** manual operator-entered jobs

**Processing:** store, score, classify, ATS analysis; generation gate (auto-generate for eligible jobs when enabled)

**Output:** job-specific resume artifacts; ready-to-apply queue; manual apply via job URL

**Non-goals:** auto-apply, browser automation; final application step is always manual.

## Documentation

- Agent entry point: [AGENTS.md](/Users/marcoparedes/dev/jobbot/AGENTS.md)
- Runtime topology and subsystem map: [ARCHITECTURE.md](/Users/marcoparedes/dev/jobbot/ARCHITECTURE.md)
- Product intent and operating boundaries: [docs/PRODUCT_SENSE.md](/Users/marcoparedes/dev/jobbot/docs/PRODUCT_SENSE.md)
- System design baseline: [docs/DESIGN.md](/Users/marcoparedes/dev/jobbot/docs/DESIGN.md)
- Reliability invariants and verification limits: [docs/RELIABILITY.md](/Users/marcoparedes/dev/jobbot/docs/RELIABILITY.md)
- Product spec index: [docs/product-specs/index.md](/Users/marcoparedes/dev/jobbot/docs/product-specs/index.md)
- Plan index and tracked follow-ups: [docs/PLANS.md](/Users/marcoparedes/dev/jobbot/docs/PLANS.md)

Use the harness-style docs tree under [`docs/`](/Users/marcoparedes/dev/jobbot/docs) as the
repo-local system of record. Historical PR/audit notes were removed in favor of fewer living docs.

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
| **Source adapters: capability read-model** | `GET /api/jobs/run-source-adapter` | Discovery | Lists launchable adapter-backed sources plus operator-facing family, backend, and gating metadata. |
| **Source adapters: launch** | `POST /api/jobs/run-source-adapter` | Discovery | Launches adapter-backed discovery runs for public boards, portfolio boards, and gated auth boards through the existing operator run model. |
| **URL ingest** | `POST /api/jobs/ingest-url` | Canonical | Paste supported Greenhouse/Lever/Ashby job URL. Feature-flagged (`URL_INGEST_ENABLED`). |

All paths run score → classify → ATS analysis. Resume generation: manual via `POST /api/jobs/{id}/generate-resume`, or automatic when `ENABLE_AUTO_RESUME_GENERATION=true` and the job passes the generation gate.

## Known Issues / Verification Reality

- The repo has focused regression coverage for several high-risk invariants, but that is not the same as full end-to-end provider verification.
- Real provider credentials, ready-to-apply throughput, and PDF generation still need local/manual verification when those areas are touched.
- Use [docs/RELIABILITY.md](/Users/marcoparedes/dev/jobbot/docs/RELIABILITY.md) and the listed focused suites as the baseline closeout checklist for backend changes.

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

### Example: Source-adapter launch

```bash
# List operator-visible adapter capabilities
curl http://127.0.0.1:8000/api/jobs/run-source-adapter

# Launch a portfolio-board adapter run
curl -X POST http://127.0.0.1:8000/api/jobs/run-source-adapter \
  -H "Content-Type: application/json" \
  -d '{"source_name":"technyc","max_results":25}'
```

The response includes operator-facing metadata such as `source_label`, `source_family`, and
`backend`. Auth-board sources are only launchable when both their source flag and
`BB_BROWSER_ENABLED=true` are set. Registered unsupported public-board adapters such as TrueUp,
Underdog.io, and VentureLoop appear as unavailable in capability metadata rather than being treated
as fully live.

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
| `GET /api/jobs/run-source-adapter` | List adapter-backed source capabilities and launch gating |
| `POST /api/jobs/run-source-adapter` | Launch adapter-backed source run |
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
