# Real ATS Simplify Smoke Test (No Submission)

Use this runbook after the dummy-page check to validate a harmless real ATS flow with Simplify.

## Prerequisites

- `SIMPLIFY_ENABLED=true`
- `SIMPLIFY_EXTENSION_PATH=/path/to/unpacked/simplify-extension`
- `SIMPLIFY_PROFILE_DIR=/path/to/chromium-profile-dir`
- Simplify account is already logged in within the persistent profile.
- Simplify account already has profile data and resume uploaded.

## 1) Launch/Refresh Persistent Simplify Session

Run once before testing:

- From `jobbot/`:
  - `python scripts/bootstrap_simplify.py`
- Or from repo root:
  - `python jobbot/scripts/bootstrap_simplify.py`

Confirm the browser opens with Simplify available, then close when ready.

## 2) Choose a Harmless Real Job Page

Use a real ATS page (Greenhouse, Lever, Ashby, etc.) where you can safely test without submitting:

- Prefer lower-priority or already-closed/older listings for first runs.
- Avoid jobs you care about until the flow is stable.
- Ensure the page has a visible `Apply` entry point and standard application fields.

## 3) Run the Real ATS Smoke Flow

Open the page in the persistent-profile Chromium run and perform only manual smoke verification steps.

## Manual Verification Checklist

- Page loads successfully.
- `Apply` button/link is found and opens the form.
- Simplify extension opens from the page.
- Simplify autofills stored profile fields (name, email, links, etc.).
- Simplify uses resume already uploaded in the Simplify account.
- Stop before final submission (do **not** click final submit).

## Artifacts/Logs to Capture

Capture enough evidence for debugging without submitting:

- Full-page screenshot after autofill attempt.
- HTML snapshot of current form page.
- Field-fill summary/log (filled fields count + sample).
- Current page URL and ATS type (if available in run logs).

Store artifacts under the standard artifact location used by the apply runner.

## Safety Warning

First real ATS smoke tests should be treated as dry runs. Use non-critical postings and always stop before final submission.
