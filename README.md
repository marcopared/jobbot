# JobBot

Automated job discovery and application engine.

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
- `storage/profiles/` — persistent Chromium profile

Both directories are auto-created on API startup.
