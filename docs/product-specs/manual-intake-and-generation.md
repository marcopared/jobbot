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

## Resume Generation

### Manual trigger

Allowed when the job is `ATS_ANALYZED` or `RESUME_READY`.

Contract:

- create and persist `GenerationRun(triggered_by="manual")`
- queue the worker with the same `generation_run_id`
- return the same `generation_run_id` in the API response

### Automatic trigger

Allowed only when:

- auto-generation is enabled
- the generation gate passes
- source confidence and content quality are sufficient for the lane

### Grounding rule

Resume generation must stay grounded in the experience inventory YAML and deterministic selection
logic. It should not become a freeform narrative generation feature.
