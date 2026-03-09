# JobBot

Automated job discovery and application engine.

## Documentation

- Product/system contract: `docs/SPEC.md`
- Runtime/data-flow reference: `docs/ARCHITECTURE.md`
- Operator next steps and manual checks: `docs/TODO.md`

## Simplify

Simplify support is optional and disabled by default (`SIMPLIFY_ENABLED=false`).
When enabled, JobBot loads an unpacked extension from `extensions/simplify` into
Playwright's bundled Chromium using a persistent Simplify profile so stored
Simplify account state survives across runs.

Current MVP apply behavior is Simplify-first: it assumes the operator already
has a Simplify session, resume, and profile data saved in that persistent
profile. JobBot-local resume replacement inside Simplify is deferred.

## Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Node.js 18+
- Playwright browsers (`playwright install chromium`)

## Initial Setup

```bash
cp .env.example .env
pip install -r requirements.txt
cd ui && npm install && cd ..
playwright install chromium
```

If you plan to use Simplify flows, copy/export the unpacked extension into
`extensions/simplify` and point `SIMPLIFY_EXTENSION_PATH` there. The extension
folder must contain `manifest.json`. `SIMPLIFY_EXTENSION_PATH` and
`SIMPLIFY_PROFILE_DIR` only matter when `SIMPLIFY_ENABLED=true`.

## Run Locally

### Option A: one command (recommended)

```bash
bash scripts/dev.sh
```

This starts:

- Docker services (Postgres + Redis)
- FastAPI at `http://127.0.0.1:8000`
- Celery worker
- Vite UI at `http://127.0.0.1:5173`

### Option B: manual terminals

```bash
docker compose up -d
PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000
PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape,apply
cd ui && npm run dev -- --host 127.0.0.1 --port 5173
```

## Seed Data

With API + worker running:

```bash
bash scripts/seed.sh
```

This triggers `/api/jobs/run-scrape` and waits for the run to complete.

## Useful Endpoints

- Health: `GET /api/health`
- Jobs: `GET /api/jobs`
- Applications: `GET /api/applications`
- Interventions: `GET /api/interventions?status=OPEN`
- Runs: `GET /api/runs`
- WebSocket logs: `WS /ws/logs`

## Storage

- `storage/artifacts/` — screenshots, HTML snapshots, resumes
- `storage/profiles/` — persistent Chromium profiles, including the persistent Simplify profile

Both directories are auto-created on API startup.
