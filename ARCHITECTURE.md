# JobBot Architecture

JobBot is now a local-first job description triage and existing-resume recommendation tool. It does **not** generate custom resumes and does **not** auto-apply.

## MVP flow

1. Get job descriptions from local/manual intake, supported ATS URLs, canonical ATS connectors, or simple discovery sources.
2. Normalize and deduplicate jobs into the local database.
3. Score jobs and classify the role/persona.
4. Extract ATS-style keywords and years-of-experience signals from the job description.
5. Match the job against the user's existing resume catalog in [`data/resumes.yaml`](data/resumes.yaml), emphasizing years of experience, persona fit, and skill overlap.
6. Mark jobs with a recommendation as ready for review.
7. Show the user the direct job/apply link and the recommended existing resume.
8. The user goes to the external job site and applies manually with their own resume.

## Runtime topology

### API

- Framework: FastAPI
- Entry point: [`apps/api/main.py`](apps/api/main.py)
- Active job routes: [`apps/api/routes/jobs.py`](apps/api/routes/jobs.py)
- Run routes: [`apps/api/routes/runs.py`](apps/api/routes/runs.py)
- Debug/WebSocket routes remain local-dev helpers only.

### Worker

- Framework: Celery with Redis broker/result backend
- Entry point: [`apps/worker/celery_app.py`](apps/worker/celery_app.py)
- Active queues:
  - `scrape`
  - `ingestion`
  - `default`
- Active pipeline tasks:
  - scrape/discovery/ingest/manual intake
  - [`score_jobs`](apps/worker/tasks/score.py)
  - [`classify_jobs`](apps/worker/tasks/classify.py)
  - [`ats_match_resume`](apps/worker/tasks/ats_match.py)
  - [`evaluate_generation_gate`](apps/worker/tasks/generation.py) — compatibility name; now performs existing-resume recommendation, not generation.

### UI

- Framework: React + Vite + Tailwind
- Entry point: [`ui/src/App.tsx`](ui/src/App.tsx)
- Primary operator views:
  - ready-to-apply/recommendation queue
  - all jobs
  - job detail
  - runs/run detail
  - manual job intake

### Persistence

- PostgreSQL via SQLAlchemy
- Redis for Celery and local debug visibility
- Existing artifact/generation tables remain for compatibility and future reuse, but the active MVP should not rely on custom resume generation.

## Active domain model

### Source roles

Keep source roles distinct because confidence differs:

- `canonical`: Greenhouse, Lever, Ashby connector ingest.
- `url_ingest`: supported direct ATS job URLs.
- `discovery`: lower-confidence discovery sources.

Discovery is coverage, not truth. Canonical ATS and direct URL ingest are higher confidence for job content and apply URLs.

### Pipeline statuses

Active pipeline progression:

```text
INGESTED -> SCORED or REJECTED -> CLASSIFIED -> ATS_ANALYZED -> RESUME_READY
```

In the current MVP, `RESUME_READY` means **an existing-resume recommendation is ready**, not that JobBot generated a new resume artifact. `artifact_ready_at` is currently reused as a recommendation-ready timestamp for database compatibility.

## Resume recommendation

- Catalog: [`data/resumes.yaml`](data/resumes.yaml)
- Matching code: [`core/resume_matching.py`](core/resume_matching.py)
- Inputs:
  - job title
  - job description
  - classified persona
  - existing resume metadata: resume id, label, path, persona, years of experience, skills
- Output stored on `JobAnalysis.persona_specific_scores["resume_suggestion"]` and surfaced by job list/detail API responses.

Recommendation factors:

1. Skill overlap with the job description.
2. Persona match between job classification and resume metadata.
3. Years-of-experience fit, with explicit job-description requirements weighted strongly.

## Archived/future scope

Archived under [`archive/code/2026-05-07-custom-resume-generation`](archive/code/2026-05-07-custom-resume-generation) and [`docs/archive/2026-05-07-architecture-cleanup`](docs/archive/2026-05-07-architecture-cleanup):

- custom grounded resume generation
- generation runs as an active operator loop
- resume PDF/payload/diagnostics artifact bundle docs
- old reliability/security/plan documents
- old ingestion-v2/browser-heavy planning notes

These may be useful later, but they are not part of the current MVP architecture.

## Hard boundaries

1. No auto-apply.
2. No browser automation for application flows.
3. No custom resume creation in the active MVP.
4. Local-first operation is assumed; future Raspberry Pi/browser-session work is infrastructure only.
5. bb-browser/authenticated browser work is not an active product requirement right now.
6. Documentation must describe the current MVP, not old plans.

## Verification minimum

- Backend/API/worker changes: run `pytest` or focused tests around the changed pipeline.
- UI changes: run `cd ui && npm run build`.
- Smoke check: import the FastAPI app and run at least one resume-matching test path.
