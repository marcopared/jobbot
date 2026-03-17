# Follow-up Dependencies (PR 3: Official ATS Expansion)

This document lists explicit follow-up work that depends on PR 3.

## Discovery Lane (PR 4)
- AGG-1 connector will use the same canonical ingestion contract (`CanonicalJobPayload`, dedup pipeline).
- `POST /api/jobs/run-discovery` route for AGG-1; separate from `run-ingestion`.

## Automation Funnel (PR 5)
- Generation gate and auto-resume flow will consume jobs from Greenhouse, Lever, Ashby, and URL ingest.
- Source role (`canonical`, `url_ingest`) already in model for eligibility rules.
- No changes needed to PR 3 connectors; downstream pipeline unchanged.

## UI (PR 6)
- URL ingest entry point: frontend form that calls `POST /api/jobs/ingest-url`.
- Ready-to-apply default view: backend feed `GET /api/jobs/ready-to-apply` implemented.
- Source/provenance visibility: Job model has `source`, `source_role`, `canonical_source_name`.

## Feature Flags (Optional)
- `ENABLE_LEVER_CONNECTOR`, `ENABLE_ASHBY_CONNECTOR`, `ENABLE_URL_INGEST` are supported via settings.
- Default: all enabled. Can be toggled via `LEVER_ENABLED=false`, etc.
