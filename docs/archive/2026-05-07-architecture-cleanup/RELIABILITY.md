# RELIABILITY.md — Invariants And Verification

## Current Reality

JobBot has good focused regression coverage for its highest-risk contracts. It does not have a
complete always-green proof of live-provider reliability.

Use this document as the closeout baseline for backend changes.

## Implemented Runtime Model

### Current queues

- `default`
- `scrape`
- `ingestion`

### Current pipeline states

- `INGESTED`
- `SCORED`
- `REJECTED`
- `CLASSIFIED`
- `ATS_ANALYZED`
- `RESUME_READY`
- `FAILED` is present in the model enum, but the normal tested progression still centers on the
  states above

Do not document the larger aspirational state machine as if it were implemented.

## Mandatory Invariants

1. Every persisted `ScrapeRun` created before queueing work must reach a durable terminal state.
2. Every persisted `GenerationRun` created before queueing work must reach a durable terminal state.
3. Manual generation must:
   create `GenerationRun(triggered_by="manual")`, commit it, pass the same
   `generation_run_id` to the worker, and return that id to the caller.
4. Run-item payloads in `items_json` must remain backward-compatible with the UI contract.
5. Discovery resolution must reprocess the enriched job through the downstream chain.
6. Discovery, canonical ATS, and URL-ingest roles must remain distinct.
7. Resume generation must not record artifact success when one-page fit is missed unless
   `RESUME_GENERATION_ALLOW_MULTI_PAGE_FALLBACK=true`.
8. Successful resume generation must persist the primary PDF plus `resume_payload` and
   `resume_diagnostics` sidecars with a shared `resume_v2` metadata envelope.

## Focused Regression Suites

Run these when touching pipeline, contracts, run tracking, or worker lifecycle code:

```bash
bash scripts/run_regression_invariants.sh
```

That script covers:

- `tests/test_score_batch.py`
- `tests/test_run_items_contract.py`
- `tests/test_run_item_schema_regressions.py`
- `tests/test_resolution.py -k resolved_job_past_ingested_gets_reprocessed`
- `tests/test_skipped_runs.py`
- `tests/test_api_jobs.py -k manual_generate_resume`
- `tests/test_generation_run_tracking.py`
- `tests/test_grounded_generator.py`
- `tests/test_resume_evidence_builder.py`

## Additional High-Signal Suites

- connector/provider behavior:
  [tests/test_connectors_agg1.py](../tests/test_connectors_agg1.py),
  [tests/test_connectors_serp.py](../tests/test_connectors_serp.py)
- source-adapter launch matrix and run durability:
  [tests/test_api_jobs.py](../tests/test_api_jobs.py),
  [tests/test_source_run_public_boards.py](../tests/test_source_run_public_boards.py),
  [tests/test_source_run_portfolio_boards.py](../tests/test_source_run_portfolio_boards.py),
  [tests/test_source_run_auth_boards.py](../tests/test_source_run_auth_boards.py)
- ready-to-apply contract:
  [tests/test_automation_ready_to_apply.py](../tests/test_automation_ready_to_apply.py)
- end-to-end chain coverage:
  [tests/test_pipeline_chain.py](../tests/test_pipeline_chain.py)

## What Still Requires Manual Verification

1. Live provider credentials for Adzuna and DataForSEO.
2. Real ready-to-apply throughput on a live local stack.
3. Playwright-backed PDF generation in the current environment.
4. GCS signed URL behavior when the storage backend changes.
5. End-to-end generation behavior against real local resume inputs under `data/resume_inputs/`.

## Failure Visibility

- recent task failures are recorded in Redis:
  [core/observability/failures.py](../core/observability/failures.py)
- debug endpoints are off by default:
  [apps/api/routes/debug.py](../apps/api/routes/debug.py)
- WebSocket log streaming is also gated behind debug settings:
  [apps/api/routes/ws.py](../apps/api/routes/ws.py)

## Reliability Guidance For Agents

1. Prefer changing code and docs together when touching contracts.
2. Do not use deleted historical audit docs as proof of current-branch readiness.
3. Keep the docs aligned to the implemented runtime model, not to planned queue/state expansions.
4. Keep future-facing ingestion backend notes clearly separated from implemented runtime claims.
