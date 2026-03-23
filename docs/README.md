# JobBot

JobBot is a personal job discovery, ranking, and resume-tailoring system.

This documentation set describes the **current system** (source of truth: the real repository) and remaining gaps.

## Current branch caveat

- Treat `KNOWN_ISSUES.md` as required reading before making readiness or stability claims.
- Treat `ACCEPTANCE_REPORT.md` and `CLOSEOUT_AUDIT.md` as historical snapshots, not current-branch proof.
- Do not describe the system as fully verified unless the focused regression suites relevant to your change have been rerun successfully.

## Current system (implemented)

- **Canonical ATS:** Greenhouse, Lever, Ashby via `POST /api/jobs/run-ingestion`
- **Discovery:** JobSpy (scrape); AGG-1 and SERP1 (feature-flagged: `ENABLE_AGG1_DISCOVERY`, `ENABLE_SERP1_DISCOVERY`)
- **URL ingest:** supported ATS job URLs via `POST /api/jobs/ingest-url` (feature-flagged: `URL_INGEST_ENABLED`)
- **Processing:** score → classify → ATS analysis → generation gate; auto-generation when `ENABLE_AUTO_RESUME_GENERATION=true`
- **Resolution:** `POST /api/jobs/{id}/resolve` for discovery-to-canonical enrichment (discovery jobs only); attempts recorded in `job_resolution_attempts`
- **Ready-to-apply:** `GET /api/jobs/ready-to-apply` feed; UI has ReadyToApplyPage
- **Manual apply:** user downloads artifact and opens job URL externally; no browser automation
- **Celery queues:** `default`, `scrape`, `ingestion`

## Current vs target models

**Current queue model (implemented):** `default`, `scrape`, `ingestion`

**Target queue model (aspirational):** `discovery`, `resolution`, `analysis`, `generation`, `maintenance`

**Current pipeline states (implemented):** INGESTED, SCORED, REJECTED, CLASSIFIED, ATS_ANALYZED, RESUME_READY

**Target pipeline states (aspirational):** DISCOVERED, NORMALIZED, DEDUPED, RESOLUTION_PENDING, RESOLVED_CANONICAL, RESOLVED_DISCOVERY_ONLY, GENERATION_QUEUED (persisted), FAILED, SKIPPED (with explicit reason)

## Remaining gaps

- Full target pipeline states (DISCOVERED, NORMALIZED, DEDUPED, etc.) — not yet implemented
- Target queue model (discovery, resolution, analysis queues) — not yet implemented
- UI throughput mode: ready-to-apply default view and URL ingest entry point are partially implemented
- Closeout/readiness claims must be checked against the current branch, not older audit notes
- Provider-backed end-to-end verification still requires manual/local verification beyond unit tests

## Known issues / reliability gaps

See `KNOWN_ISSUES.md` for the short current-branch reliability summary and the mandatory regression suites.

## Authoritative docs

- `SPEC.md` — product contract, goals, non-goals, source strategy, and user-visible behavior
- `ARCHITECTURE.md` — engineering design, data model, pipeline, queues, APIs, and rollout shape
- `TODO.md` — prioritized backlog and phased milestones
- `IMPLEMENTATION_PLAN.md` — PR boundaries, merge order, and delivery plan
- `CODING_AGENT_GUIDE.md` — operating instructions and constraints for coding agents
- `IMPLEMENTATION_STATUS.md` — backend verification audit (what is implemented vs aspirational)
- `KNOWN_ISSUES.md` — current branch reliability gaps and mandatory invariant suites

## Hard non-goals

These remain out of scope even in the more ambitious version:
- automated job application submission
- browser automation for application flows
- interview scheduling or outbound recruiting workflow automation
- generic arbitrary-page crawling as a first implementation path

## Source roles

JobBot uses a layered source model. Roles are fixed; do not collapse them:

- **Canonical ATS sources** (high-confidence; trusted job content and apply flow)
  - Greenhouse
  - Lever
  - Ashby
- **Broad discovery sources** (coverage; not canonical truth by default)
  - JobSpy (scrape lane)
  - AGG-1 (structured, query-driven multi-company API; feature-flagged)
  - SERP1 (optional; feature-flagged; lower-confidence)
- **Direct URL ingest** (paste supported ATS job URL)
  - Greenhouse, Lever, Ashby

Rules:
- **Discovery** sources maximize coverage; they are not canonical truth by default.
- **Canonical ATS** sources maximize content quality and stable apply flow.
- **Resume generation** is selective: canonical or high-confidence jobs first; never for every ingested job.

## Implementation order (historical; phases 2–5 implemented)

1. Documentation refresh (docs-only stabilization)
2. DB and model foundation — **implemented**
3. Official ATS expansion (Lever, Ashby, URL ingest) — **implemented**
4. Broad discovery lane (AGG-1 first; SERP optional, feature-flagged) — **implemented**
5. Automation funnel and generation gate — **implemented**
6. UI throughput mode (ready-to-apply default) — **partially implemented**

See `IMPLEMENTATION_PLAN.md` for PR boundaries, merge rules, and acceptance criteria per phase.

## Do not touch

- **Auto-apply / browser automation** — out of scope; final application is always manual.
- **Generic arbitrary crawling** — not a first-wave requirement.
- **Treating discovery as canonical** — discovery sources are lower-confidence; do not let them drive artifact generation without explicit eligibility rules.
- **SERP lane** — keep feature-flagged; never treat as canonical truth.

## Notes for contributors

Use this documentation set and the real repo as the planning baseline. Ignore scaffold, patches, and synthetic repo summaries.
