# JobBot Architecture

This document describes the currently implemented system. It intentionally reflects
the reduced product scope:

- Job ingestion and scraping
- Persistence and retrieval
- Scoring and ATS analysis
- Resume tailoring/custom resume artifact generation
- Manual operator review workflows

Auto-apply is intentionally out of scope right now.

## 1) High-Level Components

```text
Operator (UI)
  -> FastAPI (`apps/api`)
    -> PostgreSQL (`core/db/models.py`)
    -> Redis (Celery broker/backend)
  -> React UI (`ui/`)

Celery Worker (`apps/worker`)
  - scrape tasks
  - scoring tasks
  - ATS match tasks
  - resume preparation/tailoring tasks
  - notification tasks
```

## 2) Data Flow

1. Operator triggers scrape (`POST /api/jobs/run-scrape`)
2. Worker ingests jobs and writes normalized rows
3. Scoring task computes `score_total` + breakdown
4. ATS task computes resume-job keyword match + breakdown
5. Operator reviews jobs in UI and manually approves/rejects
6. Resume artifact preparation remains available for manual/operator workflows

No production path currently executes automated browser submit/apply.

## 3) Persistence Model

Primary tables:

- `jobs`
- `companies`
- `scrape_runs`
- `applications` (legacy/manual tracking still possible)
- `artifacts`
- `interventions`

Legacy apply-related statuses/enums may still exist in the schema for compatibility.
They are not part of the active product surface.

## 4) Worker Queues

Active queues:

- `scrape`
- `default`

The previous apply queue is not part of active runtime behavior.

## 5) API Surface Boundaries

Current API supports:

- scraping runs
- job listing/filtering/details
- approve/reject transitions
- artifact retrieval
- interventions listing and manual resolve/abort operations
- runs history

## 6) UI Surface Boundaries

Current UI supports:

- jobs list and detail review
- scoring and ATS breakdown visibility
- manual approve/reject actions
- interventions view with manual resolve/abort
- run history and artifact viewing

Queue/retry apply buttons are intentionally removed.

## 7) Storage Layout

```text
storage/
  artifacts/   # generated files (resume outputs, snapshots, logs)
  profiles/    # local profile state used by browser tooling
  logs/        # local run logs
```

## 8) Product Boundary Statement

Implemented now:

- scrape
- store/score/rank
- ATS keyword extraction and matching
- custom resume preparation/tailoring
- manual operator workflow

Not implemented now:

- automated job application submission (auto-apply)
