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
- Entry point: [apps/api/main.py](apps/api/main.py)
- Major routers:
  - [apps/api/routes/jobs.py](apps/api/routes/jobs.py)
  - [apps/api/routes/runs.py](apps/api/routes/runs.py)
  - [apps/api/routes/artifacts.py](apps/api/routes/artifacts.py)
  - [apps/api/routes/debug.py](apps/api/routes/debug.py)
  - [apps/api/routes/ws.py](apps/api/routes/ws.py)

### Worker

- Framework: Celery with Redis broker/result backend
- Entry point: [apps/worker/celery_app.py](apps/worker/celery_app.py)
- Current queues:
  - `scrape`
  - `ingestion`
  - `default`
- Task families:
  - scrape: [apps/worker/tasks/scrape.py](apps/worker/tasks/scrape.py)
  - ingest: [apps/worker/tasks/ingest.py](apps/worker/tasks/ingest.py)
  - discovery: [apps/worker/tasks/discovery.py](apps/worker/tasks/discovery.py)
  - resolution: [apps/worker/tasks/resolution.py](apps/worker/tasks/resolution.py)
  - generation gate: [apps/worker/tasks/generation.py](apps/worker/tasks/generation.py)
  - analysis chain: `score -> classify -> ats_match -> generation_gate`
  - resume generation: [apps/worker/tasks/resume.py](apps/worker/tasks/resume.py)

### UI

- Framework: React + Vite + Tailwind
- Entry point: [ui/src/App.tsx](ui/src/App.tsx)
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

- canonical models live in [core/db/models.py](core/db/models.py)
- migrations live in [alembic/versions](alembic/versions)
- schema summary lives in [docs/generated/db-schema.md](docs/generated/db-schema.md)

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
  - Tech:NYC Jobs
  - Primary Venture Partners Jobs Board
  - Greycroft Jobs Board
  - Union Square Ventures Jobs Board
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
- [apps/worker/tasks/score.py](apps/worker/tasks/score.py) writes `SCORED` or `REJECTED`
- [apps/worker/tasks/classify.py](apps/worker/tasks/classify.py) writes `CLASSIFIED`
- [apps/worker/tasks/ats_match.py](apps/worker/tasks/ats_match.py) writes `ATS_ANALYZED`
- [core/resumes/grounded_generator.py](core/resumes/grounded_generator.py) writes `RESUME_READY`

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

- inventory file: [data/experience_inventory.yaml](data/experience_inventory.yaml)
- optional local-first supplemental inputs directory: `data/resume_inputs`
- exact optional sources:
  - `current_resume`
  - `current_role`
  - `achievements`
  - `project_writeups` from `data/resume_inputs/projects/` or a single `projects.*` file
- selection logic: [core/resumes/selection.py](core/resumes/selection.py)
- evidence assembly:
  [core/resumes/evidence_builder.py](core/resumes/evidence_builder.py)
- rendering:
  - centralized Letter + 0.5in default page geometry
  - deterministic fit planning with bounded compaction
  - Playwright PDF render plus rendered page-count validation
  - artifact storage backend
- exact evidence source-kind values:
  - `inventory-only`
  - `inventory-plus-local-files`

Persisted artifact bundle on successful generation:

- primary PDF artifact with role `resume_pdf_primary`
- payload sidecar with role `resume_payload`
- diagnostics sidecar with role `resume_diagnostics`
- shared `resume_v2` metadata envelope with `payload_schema_version`, `inputs_hash`,
  `fit_outcome`, `fit_diagnostics`, and `evidence_completeness`
- fit outcomes:
  - `fit_success_one_page`
  - `fit_success_multi_page_fallback`
  - `fit_failed_overflow`

## 7. Resolution Model

Discovery-to-canonical resolution is an in-place enrichment path:

- route: `POST /api/jobs/{id}/resolve`
- worker: [apps/worker/tasks/resolution.py](apps/worker/tasks/resolution.py)
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
| Job routes and contracts | [apps/api/routes/jobs.py](apps/api/routes/jobs.py), [apps/api/schemas.py](apps/api/schemas.py) |
| Worker orchestration | [apps/worker/celery_app.py](apps/worker/celery_app.py), [apps/worker/tasks](apps/worker/tasks) |
| Providers/connectors | [core/connectors](core/connectors) |
| Scoring/classification/ATS | [core/scoring](core/scoring), [core/classification](core/classification), [core/ats](core/ats) |
| Resume generation | [core/resumes](core/resumes), [data/experience_inventory.yaml](data/experience_inventory.yaml) |
| Resume-generation v2 note | [docs/design-docs/resume-generation-v2.md](docs/design-docs/resume-generation-v2.md) |
| Tests and invariants | [tests/README.md](tests/README.md), [docs/RELIABILITY.md](docs/RELIABILITY.md) |
