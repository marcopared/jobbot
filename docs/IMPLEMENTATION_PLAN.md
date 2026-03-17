# JobBot Implementation Plan

## Purpose

This document translates the product spec and architecture into reviewable engineering delivery boundaries.

It is intentionally written to support small PRs and coding-agent delegation.

## 1. Implementation order

**Stabilization first. No new product scope in docs-only PRs.**

1. **Documentation refresh** — docs-only; no code changes
2. DB and model foundation — **implemented**
3. Official ATS expansion (Lever, Ashby, URL ingest) — **implemented**
4. Broad discovery lane (AGG-1 first; SERP optional, feature-flagged) — **implemented**
5. Automation funnel and generation gate — **implemented**
6. UI throughput mode — **partially implemented**

The real repository is the source of truth for current state. Do not reorder; each phase depends on the previous.

## 2. Do not touch yet

- **SERP lane** — feature-flag only; implement after AGG-1 and core automation are stable.
- **Auto-apply / browser automation** — out of scope; manual application is the final step.
- **Generic arbitrary crawling** — not a first-wave requirement.
- **UI** — do not start with UI; stabilize model and connectors first.
- **Treating discovery as canonical** — discovery sources are not canonical truth; do not auto-generate for low-confidence discovery-only jobs without explicit eligibility rules.

## 3. Delivery philosophy

Constraints:
- do not implement the whole roadmap in one PR
- do not treat discovery and canonical sources as equivalent
- do not enable high-risk lanes before the core system is stable
- do not start with UI

Working principle:
- stabilize the model first
- stabilize canonical sources second
- add discovery third
- add automation fourth
- update UI last

## 4. Recommended PR order

### PR 1 — documentation refresh (docs-only stabilization)

**Scope:** Documentation only. No code changes. No new product scope.

Files:
- `docs/SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/TODO.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/CODING_AGENT_GUIDE.md`
- `docs/README.md`
- root `README.md`

Outcome:
- docs describe the current system accurately (real repo is source of truth)
- implemented vs partially implemented vs remaining clearly distinguished
- source roles (canonical ATS, discovery, URL ingest) explicit
- implementation order and do-not-touch sections present for agents

### PR 2 — DB and model foundation
Scope:
- SQLAlchemy models
- Alembic migrations
- enums/constants required for model state

Goals:
- source role support
- resolution support
- generation eligibility tracking
- provenance extensions
- generation run tracking

Out of scope:
- connectors
- worker flow changes beyond what is strictly required for model integrity
- UI

### PR 3 — official ATS expansion
Scope:
- generalized canonical ingestion route/schema
- Lever connector
- Ashby connector
- supported ATS URL ingest

Goals:
- Greenhouse, Lever, and Ashby share a common canonical ingestion contract
- user can ingest via supported ATS URL

Out of scope:
- AGG-1
- SERP
- broad discovery logic
- auto-generation redesign

### PR 4 — discovery lane
Scope:
- AGG-1 connector
- optional SERP connector behind feature flag
- discovery route/schema
- minimal provenance wiring for discovery records

Goals:
- add broad multi-company discovery without pretending it is canonical truth
- discovery records remain explicitly lower-confidence unless resolved

Out of scope:
- UI
- full automation funnel redesign if not already prepared

### PR 5 — automation funnel
Scope:
- generation gate
- explicit state transitions
- generation run tracking
- ready-to-apply backend feed
- worker flow hardening

Goals:
- automate everything up to artifact-ready for eligible jobs
- keep manual apply boundary intact

Out of scope:
- UI redesign beyond what is required for contract testing

### PR 6 — UI throughput mode
Scope:
- ready-to-apply default view
- URL ingest entry point
- source/provenance visibility
- generation status visibility

Goals:
- ready-to-apply queue as primary operational view; no manual review checkpoint required

## 5. Merge rules

- PR 2 must land before PR 3 and PR 4
- PR 3 should land before PR 5
- PR 4 can begin after PR 2, but should merge before finalizing PR 5 if automation depends on discovery source metadata
- PR 6 should land last

## 6. Feature-flag guidance

Recommended flags:
- `ENABLE_LEVER_CONNECTOR`
- `ENABLE_ASHBY_CONNECTOR`
- `ENABLE_URL_INGEST`
- `ENABLE_AGG1_DISCOVERY`
- `ENABLE_SERP1_DISCOVERY`
- `ENABLE_AUTO_RESUME_GENERATION`

Recommended enable order:
1. Lever
2. Ashby
3. URL ingest
4. AGG-1
5. auto-generation
6. SERP

## 7. Test expectations by PR

### PR 2
- migration tests
- model integrity tests
- backfill safety

### PR 3
- connector normalization tests
- ingestion route tests
- URL-provider detection tests

### PR 4
- discovery route tests
- discovery connector normalization tests
- provenance/state assertions

### PR 5
- task-chain tests
- generation-gate tests
- ready-to-apply endpoint tests

### PR 6
- frontend API contract tests where present
- basic interaction tests if available

## 8. Explicit anti-patterns

Do not do these:
- one mega-PR with schema, connectors, workers, discovery, and UI mixed together
- SERP as canonical truth
- auto-generating resumes for every ingested job
- generic arbitrary crawling as a first pass
- touching browser automation/apply flows

## 9. Acceptance criteria per phase

| Phase | Acceptance criteria |
|-------|---------------------|
| **PR 1 (docs)** | Docs describe current system accurately; implemented vs remaining distinguished; implementation order and do-not-touch sections present |
| **PR 2 (DB/model)** | Source role, resolution, generation eligibility in model; migrations safe; backfill tests pass |
| **PR 3 (ATS expansion)** | Lever, Ashby, URL ingest work; shared canonical contract; provider detection for supported URLs |
| **PR 4 (discovery)** | AGG-1 connector works; discovery records marked distinctly; provenance wired |
| **PR 5 (automation)** | Generation gate runs; eligible jobs auto-generate; ready-to-apply feed exists; manual apply unchanged |
| **PR 6 (UI)** | Ready-to-apply default view; URL ingest entry point; source/provenance visible |

## 10. Done criteria for the implementation plan

This implementation plan has been executed successfully when:
- official ATS expansion is stable
- AGG-1 discovery is stable
- generation is automatic for eligible jobs
- ready-to-apply backend and UI exist
- manual apply remains the final step

## 11. Runtime assumptions to verify

When running locally or deploying, verify:

- **Worker queues:** Celery worker must consume `default`, `scrape`, and `ingestion`. Scrape → `scrape`, ingest → `ingestion`; discovery, classify, ats_match, generation_gate → `default`. Confirm `-Q default,scrape,ingestion` is sufficient (as in `scripts/dev.sh`).
- **Seed script:** `scripts/seed.sh` exercises only the JobSpy scrape path; discovery, URL ingest, and canonical ATS are not exercised by seed. Manual curl or UI required for those paths.
- **Feature flags:** Defaults: `ENABLE_AGG1_DISCOVERY=false`, `ENABLE_SERP1_DISCOVERY=false`, `URL_INGEST_ENABLED=true`, `ENABLE_AUTO_RESUME_GENERATION=false`. Discovery and auto-generation are off unless explicitly enabled.
- **Playwright:** `playwright install chromium` is required for PDF resume generation; omit and generation fails.
- **GCS signed URLs:** Preview/download for GCS-backed artifacts requires a service account with private key; `gcloud auth application-default login` credentials cannot sign URLs.
