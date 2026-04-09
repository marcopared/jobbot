# Manual Intake And Generation

## Manual Intake

Manual intake exists for jobs the user wants to process when:

- URL ingest is not available
- the source is unsupported
- the user already copied the relevant posting details manually

Required fields:

- title
- company
- location
- apply URL
- description

Current entry points:

- route: `POST /api/jobs/manual-ingest`
- UI page: `/jobs/manual-intake`

Manual intake creates a `ScrapeRun`, writes a canonical job-like row, and starts the same
downstream pipeline as the automated lanes.

Current persisted provenance:

- `source=manual_intake`
- `source_role=canonical`
- `pipeline_status=INGESTED`

## Resume Generation

### Manual trigger

Allowed when the job is `ATS_ANALYZED` or `RESUME_READY`.

Contract:

- create and persist `GenerationRun(triggered_by="manual")`
- commit it before queueing work
- queue the worker with the same `generation_run_id`
- return the same `generation_run_id` in the API response

### Automatic trigger

Allowed only when:

- auto-generation is enabled
- the generation gate passes
- canonical ATS and `url_ingest` jobs meet the canonical score threshold
- discovery jobs meet the stricter discovery score plus confidence/content checks
- SERP discovery remains ineligible by default unless explicitly overridden

### Grounding rule

Resume generation must stay grounded in the experience inventory YAML plus deterministic local
user-side evidence inputs when present, with deterministic selection logic. It should not become a
freeform narrative generation feature or a live external-source enrichment feature.

Current evidence package sources:

- required `inventory`
- required `target_job_description`
- optional `current_resume`
- optional `current_role`
- optional `achievements`
- optional `project_writeups`

Current source-kind values:

- `inventory-only`
- `inventory-plus-local-files`

Additional grounding constraints:

- the target job description is a targeting signal only and must not become a source of candidate
  facts
- emitted resume bullets must carry provenance back to factual evidence
- `current_resume` may influence preference-level behavior such as phrasing or ordering, but it is
  not a standalone fact source unless backed by other grounded evidence
- `current_role`, `achievements`, and `project_writeups` may contribute factual supplemental bullets
  when present

### Fit and artifact trust

- the default template keeps Letter page size with 0.5in margins
- resume generation includes deterministic fit planning with bounded compaction passes
- required contact/header/core sections are not dropped during compaction
- optional highlights and projects are trimmed before experience bullets and role count
- fit outcomes are explicit:
  - `fit_success_one_page`
  - `fit_failed_overflow`
  - `fit_success_multi_page_fallback` only when explicitly enabled
- default behavior is fail-closed on overflow; a multi-page render must not be recorded as a
  successful artifact unless `RESUME_GENERATION_ALLOW_MULTI_PAGE_FALLBACK=true`

### Persisted generation artifacts

On successful generation, JobBot persists:

- the primary operator-facing PDF artifact with `artifact_role=resume_pdf_primary`
- a structured payload sidecar artifact with `artifact_role=resume_payload`
- a diagnostics sidecar artifact with `artifact_role=resume_diagnostics`

Current persisted metadata contract:

- all three artifacts share an `artifact_bundle_id`
- artifact metadata includes a `resume_v2` envelope with:
  - `payload_schema_version`
  - `inputs_hash`
  - `fit_outcome`
  - `fit_diagnostics`
  - `evidence_completeness`
- the payload sidecar document schema is `resume-payload-sidecar-v1`
- the diagnostics sidecar document schema is `resume-diagnostics-sidecar-v1`

The PDF remains the primary operator artifact for preview/download and ready-to-apply workflow.
Sidecars are inspectable support files; they do not create a new operator workflow or replace the
manual apply boundary.
