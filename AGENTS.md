# AGENTS.md — JobBot Agent Map

Treat implemented code and the active docs listed here as the source of truth. Archived docs/code are historical reference only.

## What JobBot Is Now

JobBot is a local-first job description triage and existing-resume recommendation system.

Active MVP flow:

```text
get job descriptions
  -> match job descriptions to existing resumes, especially years of experience
  -> suggest the best existing resume
  -> give the user the direct job/apply link
  -> user applies manually on the job site
```

## Hard Product Boundaries

1. Manual apply is the final user step.
2. Do not add auto-apply.
3. Do not add browser automation for application forms.
4. Do not make custom resume generation part of the active MVP.
5. Keep local-first operation as the default assumption.
6. Future Raspberry Pi/authenticated-browser work is infrastructure only unless explicitly re-scoped.
7. Keep source roles distinct: `canonical`, `discovery`, and `url_ingest`.
8. Current active docs beat archived plans.

## Active Repository Map

```text
AGENTS.md
ARCHITECTURE.md
README.md
docs/
├── DESIGN.md
├── FRONTEND.md
├── PRODUCT_SENSE.md
├── design-docs/
│   ├── index.md
│   └── core-beliefs.md
├── generated/
│   └── db-schema.md
└── archive/
    └── 2026-05-07-architecture-cleanup/
archive/
└── code/
    └── 2026-05-07-custom-resume-generation/
```

## Read Order

1. [ARCHITECTURE.md](ARCHITECTURE.md)
2. [docs/DESIGN.md](docs/DESIGN.md)
3. [docs/PRODUCT_SENSE.md](docs/PRODUCT_SENSE.md)
4. [docs/FRONTEND.md](docs/FRONTEND.md)
5. [README.md](README.md)

## Active Code Areas

| Need | Files |
| --- | --- |
| Job/API contracts | `apps/api/routes/jobs.py`, `apps/api/schemas.py` |
| Worker pipeline | `apps/worker/tasks/score.py`, `classify.py`, `ats_match.py`, `generation.py` |
| Existing resume matching | `core/resume_matching.py`, `data/resumes.yaml` |
| Job scoring/classification/ATS extraction | `core/scoring`, `core/classification`, `core/ats` |
| Ingestion | `core/connectors`, `core/ingestion`, `core/scraping` |

## Change Rules

1. Preserve the active pipeline: `INGESTED -> SCORED or REJECTED -> CLASSIFIED -> ATS_ANALYZED -> RESUME_READY`.
2. In the MVP, `RESUME_READY` means an existing-resume recommendation is ready.
3. Store and expose `resume_suggestion`; do not queue custom resume generation.
4. Preserve direct job/apply links.
5. Keep archived custom-resume generation code out of active docs unless re-scoped.
6. Update docs when product boundaries change.

## Verification Minimum

- Backend/API/worker changes: run focused pytest suites for the changed path.
- UI changes: run `cd ui && npm run build`.
- Before closing architecture cleanup, run smoke tests that import the app and exercise resume matching.
