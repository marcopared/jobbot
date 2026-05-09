# JobBot

JobBot is a local-first job description triage and existing-resume recommendation tool.

## Current MVP scope

**Goal:** reduce the time spent visiting job sites and deciding which resume to use.

JobBot currently:

1. gets job descriptions;
2. normalizes and deduplicates them locally;
3. scores/classifies/analyzes each job description;
4. matches each job to an existing resume catalog, especially years of experience;
5. recommends the best existing resume;
6. shows the direct job/apply link;
7. stops so the user can apply manually on the external job site.

JobBot currently does **not** generate custom resumes and does **not** auto-apply.

## Active inputs

- Existing resume catalog: [`data/resumes.yaml`](data/resumes.yaml)
- Optional existing resume files referenced by that catalog, e.g. `resumes/backend.pdf`
- Job descriptions from:
  - manual intake
  - supported ATS URL ingest
  - Greenhouse/Lever/Ashby connector ingest
  - simple discovery lanes when enabled

## Active processing

```text
INGESTED -> SCORED or REJECTED -> CLASSIFIED -> ATS_ANALYZED -> RESUME_READY
```

In this MVP, `RESUME_READY` means an existing-resume recommendation is ready for user review.

## Documentation

Active docs:

- Agent/repo entry point: [AGENTS.md](AGENTS.md)
- Runtime architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- System design: [docs/DESIGN.md](docs/DESIGN.md)
- Product intent: [docs/PRODUCT_SENSE.md](docs/PRODUCT_SENSE.md)
- Frontend/operator surface: [docs/FRONTEND.md](docs/FRONTEND.md)
- Design doc index: [docs/design-docs/index.md](docs/design-docs/index.md)
- Core beliefs: [docs/design-docs/core-beliefs.md](docs/design-docs/core-beliefs.md)
- Schema summary: [docs/generated/db-schema.md](docs/generated/db-schema.md)

Archived docs live under [docs/archive/2026-05-07-architecture-cleanup](docs/archive/2026-05-07-architecture-cleanup). Archived docs are historical reference only.

## Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Node.js 18+

## Initial setup

```bash
cp .env.example .env
pip install -r requirements.txt
cd ui && npm install && cd ..
alembic upgrade head
```

Playwright may still be present in dependencies because the old custom-resume generation path is archived, but it is not required for the active MVP flow.

## Run locally

### One command

```bash
bash scripts/dev.sh
```

This starts Postgres + Redis, runs migrations, and launches FastAPI, Celery, and Vite.

- API: `http://127.0.0.1:8000`
- UI: `http://127.0.0.1:5173`

### Manual terminals

```bash
docker compose up -d
alembic upgrade head
PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000
PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape,ingestion
cd ui && npm run dev -- --host 127.0.0.1 --port 5173
```

## Useful endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Health check |
| `POST /api/jobs/manual-ingest` | Add a job description manually |
| `POST /api/jobs/ingest-url` | Ingest a supported Greenhouse/Lever/Ashby job URL |
| `POST /api/jobs/run-ingestion` | Run canonical ATS ingestion |
| `POST /api/jobs/run-scrape` | Run JobSpy scrape |
| `POST /api/jobs/run-discovery` | Run feature-flagged discovery |
| `GET /api/jobs` | List jobs |
| `GET /api/jobs/ready-to-apply` | List jobs with existing-resume recommendations ready |
| `GET /api/jobs/{id}` | Job detail, direct URL, ATS info, and resume suggestion |
| `PUT /api/jobs/{id}/status` | Mark saved/applied/archived |
| `GET /api/runs` | List ingestion/scrape/discovery runs |
| `GET /api/runs/{id}` | Run detail |

## Resume catalog example

```yaml
resumes:
  - id: backend
    label: Backend Resume
    path: resumes/backend.pdf
    persona: BACKEND
    years_experience: 8
    skills: [Python, Go, PostgreSQL, Redis, FastAPI]
```

## Non-goals

- auto-apply
- browser automation of job applications
- custom resume generation
- generated PDF artifacts
- production cloud storage requirements
- broad authenticated browser ingestion
