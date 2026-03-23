# Test Suite Guide

This directory contains both broad feature tests and focused regression suites for known
correctness hazards.

## Mandatory regression suites

When touching pipeline, contracts, or worker lifecycle code, rerun these suites:

- `tests/test_score_batch.py`
  - invariant: every scored job in a batch gets its own `JobAnalysis`
- `tests/test_run_items_contract.py`
  - invariant: run-item responses stay compatible with the UI contract
- `tests/test_run_item_schema_regressions.py`
  - invariant: stored `items_json` payloads are already canonical across writers
- `tests/test_resolution.py -k resolved_job_past_ingested_gets_reprocessed`
  - invariant: discovery resolution re-runs downstream processing
- `tests/test_skipped_runs.py`
  - invariant: disabled-feature runs do not stay `RUNNING`
- `tests/test_api_jobs.py -k manual_generate_resume`
  - invariant: manual resume generation creates and returns a persisted `GenerationRun`
- `tests/test_generation_run_tracking.py`
  - invariant: manual and auto generation update `GenerationRun` on success and failure

You can run the whole focused set with:

```bash
bash scripts/run_regression_invariants.sh
```

## Verification reality

- Many of these tests require local Postgres with migrations applied.
- Some route tests also expect Redis/Celery broker availability for enqueue paths.
- Focused suites catch specific regressions; they are not proof that the full product is reliable end to end.
