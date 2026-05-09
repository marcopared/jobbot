# FRONTEND.md — MVP Operator Surface

The UI is a local operator console for reviewing job recommendations. It is not an auto-apply interface and not a custom resume builder.

## Primary screens

## Ready to Apply / Recommendations

Purpose: show jobs that have an existing-resume recommendation ready.

The row/detail should emphasize:

- job title/company/location
- total score
- persona/classification
- recommended resume label/path
- recommendation rationale, especially years-of-experience fit
- direct job/apply link
- user status controls: saved, applied, archived

## Job Detail

Purpose: show enough information for the user to decide whether to manually apply.

Should include:

- full job description
- direct URL and apply URL
- scoring breakdown
- ATS keyword found/missing summary
- persona information
- `resume_suggestion`

Custom generated artifacts are not part of the active MVP.

## All Jobs

Purpose: browse and filter all locally known jobs.

## Runs / Run Detail

Purpose: inspect local ingestion/discovery runs and failures.

## Manual Intake

Purpose: paste a job description and direct apply URL when automated ingestion is unavailable.

## UI non-goals

- browser automation controls
- auto-apply status flows
- generated resume PDF preview as a primary flow
- custom resume editor
- cloud/admin controls
