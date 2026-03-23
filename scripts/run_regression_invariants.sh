#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH=. pytest -q tests/test_score_batch.py
PYTHONPATH=. pytest -q tests/test_run_items_contract.py tests/test_run_item_schema_regressions.py
PYTHONPATH=. pytest -q tests/test_resolution.py -k resolved_job_past_ingested_gets_reprocessed
PYTHONPATH=. pytest -q tests/test_skipped_runs.py
PYTHONPATH=. pytest -q tests/test_api_jobs.py -k manual_generate_resume
PYTHONPATH=. pytest -q tests/test_generation_run_tracking.py
