# Simplify Dummy Page Manual Test

This is a short, manual smoke test for Simplify autofill against the local dummy application page.

Scope note: this MVP validates Simplify autofill using resume/profile data already stored in the Simplify account. Local resume replacement/upload from Jobbot is a later feature.

## Required Environment Variables

Set these before running the scripts:

- `SIMPLIFY_ENABLED=true`
- `SIMPLIFY_EXTENSION_PATH=/path/to/unpacked/simplify-extension`
- `SIMPLIFY_PROFILE_DIR=/path/to/chromium-profile-dir`

## 1) Bootstrap Simplify Session

Run once (or whenever you need to refresh login state):

- From `jobbot/` directory:
  - `python scripts/bootstrap_simplify.py`
- From repo root (equivalent):
  - `python jobbot/scripts/bootstrap_simplify.py`

This launches Chromium with the persistent profile so Simplify stays logged in.

## 2) Run Dummy Form Smoke Test (file:// mode)

From repo root:

- `python scripts/test_simplify_dummy.py`

The browser opens `tests/fixtures/dummy_apply_form.html` via `file://`.

## Optional: localhost Mode (http://)

Terminal A (serve fixture page):

- `python scripts/serve_dummy_apply.py`

Terminal B (run smoke test against local server):

- `python scripts/test_simplify_dummy.py --url "http://127.0.0.1:8899/dummy_apply_form.html"`

## Manual Verification Checklist

Confirm the following during the run:

- Simplify extension loads (script prints extension ID).
- Persistent profile is still logged in.
- Dummy page opens correctly.
- Simplify recognizes the page and offers autofill behavior.
- Form fields are autofilled (fully or partially is acceptable for smoke test).
- Resume field behavior is observable, but local file upload automation is not part of this MVP check.
- After pressing Enter in terminal, artifacts are created in:
  - `storage/artifacts/simplify_dummy_test/dummy_apply_page.png`
  - `storage/artifacts/simplify_dummy_test/dummy_apply_page.html`
  - `storage/artifacts/simplify_dummy_test/field_fill_summary.json`
