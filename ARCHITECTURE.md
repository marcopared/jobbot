# JobBot Architecture

This document is the architecture entry point for JobBot. It describes the implemented system, not
an aspirational future state.

## 1. System Shape

JobBot has one operator-facing loop:

1. Ingest jobs from canonical ATS, discovery lanes, direct ATS URLs, or manual intake.
2. Normalize and deduplicate into a single `jobs` table.
3. Run deterministic score, persona classification, and ATS extraction.
4. Evaluate the generation gate.
5. Generate a grounded resume artifact for eligible jobs.
6. Surface artifact-ready jobs in the ready-to-apply queue.
7. Stop at manual apply via the external job URL.

## 2. Runtime Topology

### API

- Framework: FastAPI
- Entry point: [apps/api/main.py](/Users/marcoparedes/dev/jobbot/apps/api/main.py)
- Major routers:
  - [apps/api/routes/jobs.py](/Users/marcoparedes/dev/jobbot/apps/api/routes/jobs.py)
  - [apps/api/routes/runs.py](/Users/marcoparedes/dev/jobbot/apps/api/routes/runs.py)
  - [apps/api/routes/artifacts.py](/Users/marcoparedes/dev/jobbot/apps/api/routes/artifacts.py)
  - [apps/api/routes/debug.py](/Users/marcoparedes/dev/jobbot/apps/api/routes/debug.py)
  - [apps/api/routes/ws.py](/Users/marcoparedes/dev/jobbot/apps/api/routes/ws.py)

### Worker

- Framework: Celery with Redis broker/result backend
- Entry point: [apps/worker/celery_app.py](/Users/marcoparedes/dev/jobbot/apps/worker/celery_app.py)
- Current queues:
  - `scrape`
  - `ingestion`
  - `default`
- Task families:
  - scrape: [apps/worker/tasks/scrape.py](/Users/marcoparedes/dev/jobbot/apps/worker/tasks/scrape.py)
  - ingest: [apps/worker/tasks/ingest.py](/Users/marcoparedes/dev/jobbot/apps/worker/tasks/ingest.py)
  - discovery: [apps/worker/tasks/discovery.py](/Users/marcoparedes/dev/jobbot/apps/worker/tasks/discovery.py)
  - resolution: [apps/worker/tasks/resolution.py](/Users/marcoparedes/dev/jobbot/apps/worker/tasks/resolution.py)
  - analysis chain: `score -> classify -> ats_match -> generation_gate`
  - resume generation: [apps/worker/tasks/resume.py](/Users/marcoparedes/dev/jobbot/apps/worker/tasks/resume.py)

### UI

- Framework: React + Vite + Tailwind
- Entry point: [ui/src/App.tsx](/Users/marcoparedes/dev/jobbot/ui/src/App.tsx)
- Default route: `/ready`
- Primary pages:
  - ready to apply
  - all jobs
  - runs
  - run detail
  - job detail
  - manual job intake

### Persistence

- PostgreSQL via SQLAlchemy
- Redis for Celery + debug log/failure visibility
- Local filesystem or GCS for artifacts

## 3. Subsystem Map

### API layer

Responsibility:
- validate request contracts
- create `ScrapeRun` or `GenerationRun` records before queueing
- expose read models for jobs, runs, artifacts, and debug data

Rules:
- routes should not implement scoring, classification, ATS extraction, or generation logic
- routes may enqueue tasks and translate persistence state into response models

### Worker task layer

Responsibility:
- perform fetch, persistence, enrichment, and pipeline progression
- maintain `ScrapeRun` and `GenerationRun` durability
- publish log/failure signals for debugging

Rules:
- tasks own orchestration
- tasks call into `core/` for domain logic
- chain shape is part of the contract and must remain observable

### Core domain layer

Responsibility:
- connectors
- dedup and normalization
- scoring
- persona classification
- ATS extraction
- generation gate
- grounded resume generation
- storage backends
- observability helpers

Rules:
- domain logic should be deterministic unless a provider API is inherently remote
- generated resumes are grounded in structured inventory data

### Data/model layer

- canonical models live in [core/db/models.py](/Users/marcoparedes/dev/jobbot/core/db/models.py)
- migrations live in [alembic/versions](/Users/marcoparedes/dev/jobbot/alembic/versions)
- schema summary lives in [docs/generated/db-schema.md](/Users/marcoparedes/dev/jobbot/docs/generated/db-schema.md)

## 4. Source Role Model

JobBot uses a fixed source-role model:

- Canonical ATS:
  - Greenhouse
  - Lever
  - Ashby
- Discovery:
  - JobSpy
  - AGG-1 (Adzuna)
  - SERP1 (DataForSEO Google Jobs)
  - startupjobs.nyc
  - Built In NYC
  - Welcome to the Jungle

Registered but currently gated/unsupported public-board adapters:

- TrueUp
- Underdog.io
- VentureLoop
- Direct URL ingest:
  - supported Greenhouse/Lever/Ashby URLs

Rules:
- discovery is coverage, not truth
- canonical ATS has the highest trust for content and apply flow
- SERP1 remains lower-confidence and feature-flagged
- manual apply remains the final human step regardless of source

## 5. Current Pipeline Contract

Implemented `pipeline_status` values:

- `INGESTED`
- `SCORED`
- `REJECTED`
- `CLASSIFIED`
- `ATS_ANALYZED`
- `RESUME_READY`
- `FAILED`

Actual write points:

- ingest/scrape/discovery/manual intake create `INGESTED`
- [apps/worker/tasks/score.py](/Users/marcoparedes/dev/jobbot/apps/worker/tasks/score.py) writes `SCORED` or `REJECTED`
- [apps/worker/tasks/classify.py](/Users/marcoparedes/dev/jobbot/apps/worker/tasks/classify.py) writes `CLASSIFIED`
- [apps/worker/tasks/ats_match.py](/Users/marcoparedes/dev/jobbot/apps/worker/tasks/ats_match.py) writes `ATS_ANALYZED`
- [core/resumes/grounded_generator.py](/Users/marcoparedes/dev/jobbot/core/resumes/grounded_generator.py) writes `RESUME_READY`

## 6. Generation Model

Two generation entry points exist:

- Manual:
  - `POST /api/jobs/{id}/generate-resume`
  - requires `ATS_ANALYZED` or `RESUME_READY`
  - persists `GenerationRun(triggered_by="manual")` before queueing
- Automatic:
  - `evaluate_generation_gate`
  - requires `ENABLE_AUTO_RESUME_GENERATION=true`
  - uses stricter rules for discovery than canonical ATS

Grounding model:

- inventory file: [data/experience_inventory.yaml](/Users/marcoparedes/dev/jobbot/data/experience_inventory.yaml)
- selection logic: [core/resumes/selection.py](/Users/marcoparedes/dev/jobbot/core/resumes/selection.py)
- rendering:
  - HTML template
  - Playwright PDF render
  - artifact storage backend

## 7. Resolution Model

Discovery-to-canonical resolution is an in-place enrichment path:

- route: `POST /api/jobs/{id}/resolve`
- worker: [apps/worker/tasks/resolution.py](/Users/marcoparedes/dev/jobbot/apps/worker/tasks/resolution.py)
- attempts table: `job_resolution_attempts`
- canonical provenance table: `job_sources`

Resolution does not create a new job row. It enriches the existing discovery row, rewinds it to
`INGESTED`, and reruns the downstream chain.

## 8. Dependency Rules

1. `ui/` talks to the REST API only.
2. `apps/api/` may depend on `core/` and enqueue worker tasks.
3. `apps/worker/` may depend on `core/` and persistence, but not on UI code.
4. `core/` should remain framework-light and reusable across API and worker paths.
5. Documentation should describe current runtime behavior, not stale phase plans.

## 9. Files To Read For Specific Work

| Work area | Primary files |
| --- | --- |
| Job routes and contracts | [apps/api/routes/jobs.py](/Users/marcoparedes/dev/jobbot/apps/api/routes/jobs.py), [apps/api/schemas.py](/Users/marcoparedes/dev/jobbot/apps/api/schemas.py) |
| Worker orchestration | [apps/worker/celery_app.py](/Users/marcoparedes/dev/jobbot/apps/worker/celery_app.py), [apps/worker/tasks](/Users/marcoparedes/dev/jobbot/apps/worker/tasks) |
| Providers/connectors | [core/connectors](/Users/marcoparedes/dev/jobbot/core/connectors) |
| Scoring/classification/ATS | [core/scoring](/Users/marcoparedes/dev/jobbot/core/scoring), [core/classification](/Users/marcoparedes/dev/jobbot/core/classification), [core/ats](/Users/marcoparedes/dev/jobbot/core/ats) |
| Resume generation | [core/resumes](/Users/marcoparedes/dev/jobbot/core/resumes), [data/experience_inventory.yaml](/Users/marcoparedes/dev/jobbot/data/experience_inventory.yaml) |
| Tests and invariants | [tests/README.md](/Users/marcoparedes/dev/jobbot/tests/README.md), [docs/RELIABILITY.md](/Users/marcoparedes/dev/jobbot/docs/RELIABILITY.md) |
