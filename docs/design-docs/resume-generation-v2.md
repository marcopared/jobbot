# Resume Generation V2

This note summarizes the implemented resume-generation-v2 contract. It is intentionally narrow and
code-truth oriented.

## Trigger Paths

- manual trigger: `POST /api/jobs/{id}/generate-resume`
  - allowed only for `ATS_ANALYZED` and `RESUME_READY`
  - persists `GenerationRun(triggered_by="manual")`, commits it, then queues the worker with the
    same `generation_run_id`
- automatic trigger: `evaluate_generation_gate`
  - runs after ATS analysis when `ENABLE_AUTO_RESUME_GENERATION=true`
  - canonical ATS and `url_ingest` jobs use the canonical score threshold
  - discovery jobs use stricter score plus confidence/content checks
  - SERP discovery is not auto-eligible by default

## Evidence Model

Required sources:

- `inventory`
- `target_job_description`

Optional local sources:

- `current_resume`
- `current_role`
- `achievements`
- `project_writeups`

Implemented source-kind values:

- `inventory-only`
- `inventory-plus-local-files`

Grounding rules that matter in practice:

- `target_job_description` is targeting-only, not a source of candidate facts
- `current_resume` is preference context, not a factual source by itself
- factual supplemental bullets come from grounded inventory/local evidence

## Artifact Contract

Successful generation persists one logical bundle:

- primary PDF: `artifact_role=resume_pdf_primary`
- payload sidecar: `artifact_role=resume_payload`
- diagnostics sidecar: `artifact_role=resume_diagnostics`

All three artifacts share:

- `artifact_bundle_id`
- a `resume_v2` metadata envelope with `payload_schema_version`, `inputs_hash`, `fit_outcome`,
  `fit_diagnostics`, and `evidence_completeness`

Sidecar schemas:

- payload: `resume-payload-sidecar-v1`
- diagnostics: `resume-diagnostics-sidecar-v1`

API/UI summary fields come from artifact metadata, not client-side reconstruction:

- `artifact_role`
- `payload_version`
- `inputs_hash`
- `fit_status`
- `evidence_completeness`

## Fit Behavior

Implemented fit outcomes:

- `fit_success_one_page`
- `fit_success_multi_page_fallback`
- `fit_failed_overflow`

Fit rules:

- default page geometry is Letter with 0.5in margins
- generation uses deterministic fit planning plus bounded compaction
- rendered PDFs are validated by actual page count
- overflow fails closed unless `RESUME_GENERATION_ALLOW_MULTI_PAGE_FALLBACK=true`

## Operator Boundary

- the Ready to Apply queue remains the output surface
- the operator moves into Job Detail to review the PDF and optional sidecars
- the external application step remains manual
- no auto-apply or hidden browser submission behavior is part of this contract
