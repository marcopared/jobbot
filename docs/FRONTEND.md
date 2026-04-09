# FRONTEND.md — JobBot UI Surface

## Purpose

The frontend is a thin operator console over the REST API. It helps the user inspect jobs, trigger
ingestion paths, review pipeline results, and download artifacts. It does not contain core business
logic.

Approved ingestion-v2 work changes backend acquisition architecture, not the current route model or
the frontend's responsibility as an operator console over existing API contracts.

## Current Routes

Defined in [ui/src/App.tsx](../ui/src/App.tsx):

- `/ready` — ready-to-apply queue
- `/jobs` — all jobs view
- `/jobs/manual-intake` — manual intake form
- `/jobs/:id` — job detail and artifact actions
- `/runs` — run trigger and run list screen
- `/runs/:id` — run item inspection screen

## UI Responsibilities

1. Render current job and run state.
2. Trigger already-supported backend routes.
3. Expose manual operator actions:
   save, archive, applied, generate resume, run scrape/discovery/ingest/source-adapter, manual intake.
4. Keep the user oriented around manual apply, not hidden automation.

## Important Components

- layout shell:
  [ui/src/components/Layout.tsx](../ui/src/components/Layout.tsx)
- job table:
  [ui/src/components/JobTable.tsx](../ui/src/components/JobTable.tsx)
- artifact actions:
  [ui/src/components/ArtifactViewer.tsx](../ui/src/components/ArtifactViewer.tsx)
- score and ATS display:
  [ui/src/components/ScoreBreakdown.tsx](../ui/src/components/ScoreBreakdown.tsx)

## Current Interaction Model

### Ready to Apply

- default landing route
- shows only `RESUME_READY` jobs with `artifact_ready_at` and `user_status=NEW`
- supports bulk save/archive/applied actions
- the Apply column routes the user to Job Detail for artifact review and outbound apply
- URL ingest and manual intake shortcuts are available from the page header, but the final apply
  step remains manual

### All Jobs

- broader search/filter/sort surface
- includes a debug toggle for rejected jobs
- intended for review and triage, not just immediate application

### Runs

- current operator launchpad for:
  - JobSpy scrape
  - discovery run
  - canonical ingestion
  - source-adapter launch
- the Source Adapters card is capability-driven:
  - the UI reads family, backend, labels, and launch gating from `GET /api/jobs/run-source-adapter`
  - the UI does not guess public vs portfolio vs auth families from ad hoc source-name parsing
- current operator-facing adapter families are:
  - public boards
  - portfolio boards
  - authenticated boards
- lists runs and links into per-item inspection

### Job Detail

- shows score, ATS details, persona, description, and artifacts
- reads `latest_generation_run` from `GET /api/jobs/{id}` for operator-visible generation progress
- uses lightweight delayed refetch from Job Detail for queued/running/failed visibility rather than
  a dedicated run-status stream
- keeps the resume PDF as the primary operator-facing artifact
- exposes payload/diagnostics sidecars as optional supporting files, not as a replacement workflow
- surfaces backend-provided artifact summary fields:
  - `artifact_role`
  - `payload_version`
  - `inputs_hash`
  - `fit_status`
  - `evidence_completeness`
- exposes manual resume generation only when `pipeline_status` is `ATS_ANALYZED` or
  `RESUME_READY`
- keeps Preview/Download/Open Application together inside the manual apply workflow

### Manual Intake

- fallback workflow for unsupported URLs or manually sourced roles
- persists a canonical job-like record and starts the same downstream pipeline

## Frontend Constraints

1. UI should not infer discovery vs canonical from new ad hoc rules.
   Use backend data or the existing constrained source mapping.
2. UI should not infer source-adapter family or backend semantics from string parsing when the
   backend capability read model already provides them.
3. Do not present automation that violates the manual-apply boundary.
4. Avoid letting UI-only conveniences redefine backend contracts.
5. Keep the API client shapes aligned with the run-item normalization contract.

## Known Frontend Gaps

- the UI infers source-role labels from `source` in list views because the list item schema does
  not currently expose `source_role`
- the visual design is functional, not opinionated
- there is no dedicated verification/status surface beyond runs and toasts
- generation status polling is still lightweight; Job Detail relies on `latest_generation_run`
  plus a delayed refetch rather than a dedicated run-status stream

Those are follow-ups, not documentation debt.
