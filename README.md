# JobBot

JobBot is a local-first job discovery and decision-support tool.

Current implemented scope:
- scrape jobs
- store, score, and rank jobs
- run ATS keyword extraction and ATS match scoring
- generate job-specific resume artifacts from your base resume and skills data
- support manual operator review workflows

Auto-apply is intentionally **not** part of the current product scope.

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
cd ui && npm install && cd ..
```

## Run Locally

### Option A: one command

```bash
bash scripts/dev.sh
```

This starts:
- Postgres + Redis (Docker)
- FastAPI at `http://127.0.0.1:8000`
- Celery worker
- Vite UI at `http://127.0.0.1:5173`

### Option B: manual terminals

```bash
docker compose up -d
PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000
PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape
cd ui && npm run dev -- --host 127.0.0.1 --port 5173
```

## Seed Data

With API + worker running:

```bash
bash scripts/seed.sh
```

This triggers `/api/jobs/run-scrape` and waits for completion.

## Useful Endpoints

- Health: `GET /api/health`
- Jobs: `GET /api/jobs`
- Applications: `GET /api/applications`
- Interventions: `GET /api/interventions?status=OPEN`
- Runs: `GET /api/runs`
- WebSocket logs: `WS /ws/logs`

## Storage

- `storage/artifacts/` - generated artifacts (including resume outputs and snapshots)
- `storage/profiles/` - Playwright/Chromium profile data for local browser automation tooling

Both directories are auto-created on API startup.
