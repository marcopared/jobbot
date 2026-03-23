# Known Issues / Reliability Gaps

**Date:** 2026-03-23  
**Purpose:** Current-branch reliability notes. This file is the short-form truth source for
known gaps that should block overconfident documentation or closeout claims.

## What is true today

- The repository has focused regression coverage for several high-risk invariants:
  - batch scoring
  - run-item schema / contract normalization
  - discovery resolution reprocessing
  - skipped-run lifecycle persistence
  - manual generation run tracking
- The committed architecture is still the simpler current model:
  - queues: `default`, `scrape`, `ingestion`
  - pipeline states: `INGESTED`, `SCORED`, `REJECTED`, `CLASSIFIED`, `ATS_ANALYZED`, `RESUME_READY`
- Manual resume generation and auto generation both persist `GenerationRun` state.
- Feature-flag-disabled scrape/ingest/discovery paths now persist terminal `ScrapeRun` state.

## Reliability gaps that still matter

- Historical closeout docs in this repo were written as point-in-time verification snapshots.
  They are useful context, but they are not sufficient evidence that the current branch is
  "stable", "green", or ready for unrestricted feature work.
- Full provider-backed verification is still partly manual:
  real AGG-1/SERP1 credentials, ready-to-apply throughput, and end-to-end artifact generation
  are not proven by unit tests alone.
- The target queue model and expanded pipeline state machine remain aspirational. Do not
  document them as implemented.
- The focused regression suites cover specific correctness bugs; they do not prove complete
  system reliability.
- Full local verification still depends on local services and setup:
  Postgres for DB-backed tests, Redis for Celery enqueue paths, and Playwright for real PDF generation.

## Mandatory invariants for future changes

- Every persisted `ScrapeRun` or `GenerationRun` created before queueing work must reach a durable
  terminal state on success, skip, or failure.
- Discovery, canonical ATS, and URL ingest roles must remain distinct.
- Discovery sources must never be documented or treated as canonical truth by default.
- Run-item payloads must stay backward-compatible with the UI contract.
- Reprocessing after discovery-to-canonical resolution must remain intact.

## Minimum focused verification before closeout

Run these suites when touching pipeline, run tracking, or contracts:

```bash
bash scripts/run_regression_invariants.sh
```
