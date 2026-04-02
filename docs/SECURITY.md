# SECURITY.md — JobBot Security And Safety Boundaries

## Security Posture

JobBot is a local-first operator tool with bounded external integrations. Its strongest safety
controls are product-boundary controls and small runtime safeguards, not a separate policy engine.

## Hard Safety Boundaries

1. No automated job application submission.
2. No browser automation for application flows.
3. Discovery sources are never canonical truth by default.
4. SERP1 stays feature-flagged and lower-confidence.

These are both product and safety constraints.

## Sensitive Inputs

Secrets and credentials come from environment variables via
[apps/api/settings.py](/Users/marcoparedes/dev/jobbot/apps/api/settings.py):

- database and Redis URLs
- Adzuna credentials
- DataForSEO credentials
- GCS configuration
- notification provider credentials

Do not move secret-bearing runtime values into committed documentation.

## Artifact Access

Artifact storage backends:

- local filesystem
- GCS

For GCS:

- objects stay private
- preview/download routes generate signed URLs on demand
- signing requires service-account credentials with a private key

Relevant files:

- [core/storage/factory.py](/Users/marcoparedes/dev/jobbot/core/storage/factory.py)
- [core/storage/local_store.py](/Users/marcoparedes/dev/jobbot/core/storage/local_store.py)
- [core/storage/gcs_store.py](/Users/marcoparedes/dev/jobbot/core/storage/gcs_store.py)
- [apps/api/routes/artifacts.py](/Users/marcoparedes/dev/jobbot/apps/api/routes/artifacts.py)

## Debug Surface

Debug APIs are disabled by default.

- `GET /api/debug/failures`
- `WS /ws/logs`
- `GET /api/jobs/{id}?debug=true` only includes internal payloads when debug is enabled

That keeps raw payload visibility out of the normal operator path.

## Provider Safety

1. Current implementation uses the named provider surfaces already supported in code.
2. New provider surfaces should be added explicitly through the approved source-adapter and
   acquisition-backend model.
3. Keep provider-specific unmapped fields in `raw_payload` rather than forcing schema churn.
4. Do not broaden discovery providers into generic crawling.

## Authenticated-Browser Ingestion

Authenticated-browser acquisition is an approved ingestion direction, but it must remain a bounded
browser/session capability layer only.

Security rules:

- bb-browser may be used for auth-bound or browser-native source acquisition where normal fetch
  paths are insufficient.
- bb-browser must not own JobBot business logic, trust policy, scoring, classification, or
  persistence rules.
- bb-browser must not be framed as a CAPTCHA, anti-bot, or guaranteed bypass strategy.
- session-derived payloads should still flow through the normal JobBot provenance and `raw_payload`
  handling discipline.
- browser-session capability for ingestion does not change the boundary that JobBot does not
  automate application submission.

## Data Handling Notes

- Job payloads and artifacts may contain sensitive personal job-search context.
- Resume generation uses a local YAML inventory file and should remain grounded to that file.
- Failure logs intentionally avoid storing raw Celery args/kwargs in full.

## Security-Relevant Follow-Ups

Tracked in
[docs/exec-plans/tech-debt-tracker.md](/Users/marcoparedes/dev/jobbot/docs/exec-plans/tech-debt-tracker.md):

- lightweight docs/link linting
- stronger reference automation
- possible API exposure of `source_role` to reduce UI-side inference
