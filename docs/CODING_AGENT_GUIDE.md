# JobBot Coding Agent Guide

## Purpose

This document is for coding agents and reviewers.

It defines:
- what documents to trust
- what product constraints must not be violated
- how to scope work safely
- how to avoid building against stale or outdated product scope

## 1. Documents to trust

Use these in order:
1. `docs/SPEC.md`
2. `docs/ARCHITECTURE.md`
3. `docs/KNOWN_ISSUES.md`
4. `docs/TODO.md`
5. `docs/IMPLEMENTATION_PLAN.md`
6. the real repo for current baseline implementation
7. the provider specs committed in the repo for the current wave (Adzuna swagger spec and DataForSEO OpenAPI spec)

Do **not** infer product scope from older comments, scaffold, patches, or synthetic repo summaries.
Do **not** treat `ACCEPTANCE_REPORT.md` or `CLOSEOUT_AUDIT.md` as proof that the current branch is fully verified.

## 2. Product constraints

These are hard constraints:
- manual apply remains the final human step
- no automated application submission
- no browser automation for applications
- discovery sources are not canonical truth by default
- generic arbitrary crawling is not a first-wave requirement
- `SERP1` remains lower-confidence and feature-flagged

## 3. Provider mapping for this wave

These provider identities are fixed for tonight's implementation wave:
- `AGG-1 = Adzuna`
- `SERP1 = DataForSEO Google Jobs`

Do not treat these lane names as placeholders during this wave.

## 4. Source-confidence discipline

Always distinguish:
- canonical ATS sources
- discovery sources
- direct URL ingest

Confidence order for this wave:
- canonical ATS > Adzuna > DataForSEO

Rules:
- canonical ATS wins during merge/reconciliation
- Adzuna remains discovery, not canonical truth
- DataForSEO remains discovery, not canonical truth
- DataForSEO must be treated as lower-confidence than Adzuna in merge, resolution, and generation decisions

## 5. Review discipline

Prefer small PRs.

Tonight's PR order:
1. provider PR: Adzuna only
2. provider PR: DataForSEO only
3. verification PR after provider PRs
4. UI only after backend is green

Each PR should have:
- one clear purpose
- explicit out-of-scope statement
- focused tests
- no speculative extra scope

## 6. Safe assumptions

Safe assumptions from the current repo baseline (verify against real repo):
- **Canonical ATS:** Greenhouse, Lever, Ashby connectors exist; generalized `POST /api/jobs/run-ingestion`
- **Discovery:** JobSpy scrape; AGG-1 and SERP1 lanes exist via `POST /api/jobs/run-discovery`
- **URL ingest:** `POST /api/jobs/ingest-url` for supported Greenhouse/Lever/Ashby URLs
- **Resume generation:** manual via `POST /api/jobs/{id}/generate-resume`; auto when `ENABLE_AUTO_RESUME_GENERATION=true` and job passes generation gate
- **Ready-to-apply:** `GET /api/jobs/ready-to-apply` feed exists
- **Resolution:** `POST /api/jobs/{id}/resolve` for discovery-to-canonical enrichment; attempts recorded in `job_resolution_attempts`
- **Manual apply** is the final user step; no browser automation

Implementation and verification env vars for this wave:
- `ADZUNA_APP_ID`
- `ADZUNA_APP_KEY`
- `ENABLE_AGG1_DISCOVERY`
- `DATAFORSEO_LOGIN`
- `DATAFORSEO_PASSWORD`
- `DATAFORSEO_BASE_URL`
- `DATAFORSEO_LOCATION_NAME`
- `DATAFORSEO_LANGUAGE_NAME`
- `ENABLE_SERP1_DISCOVERY`

## 7. Unsafe assumptions

Do not assume:
- existing schema needs a new migration for provider work
- existing queue topology should be rewritten for this wave
- discovery records should auto-generate resumes by default
- any SERP/provider integration can be treated as canonical truth
- generic crawling should be introduced while implementing DataForSEO
- UI polish should start before backend verification is green
- historical "GO"/"PASS"/"merge recommendation YES" docs still apply to the current branch

## 7.1 Mandatory invariants

When touching pipeline or worker code, preserve these invariants and rerun the matching regression suites:

- batch scoring must create/update `JobAnalysis` for every job in the batch
- run-item payloads must keep the canonical UI schema and backward-compatible normalization
- discovery resolution must reprocess jobs that were already past `INGESTED`
- disabled-feature worker exits must persist terminal skipped runs
- manual and auto generation must both persist durable `GenerationRun` lifecycle state

## 8. Provider-specific implementation guardrails

### Adzuna (`AGG-1`)
- Adzuna is page-based and query-driven.
- Use the search endpoint shape documented in the Adzuna spec.
- Keep runs bounded by page count and/or total job cap.
- Preserve provider-specific fields in `raw_payload` when they do not map cleanly into the existing schema.

### DataForSEO Google Jobs (`SERP1`)
- Use Google Jobs endpoints only.
- Use basic auth.
- Implement SERP1 as a bounded synchronous wrapper over the provider task API for this alpha.
- Preferred flow: `task_post` -> bounded readiness polling -> `task_get/advanced`.
- Do not expand SERP1 into generic search, arbitrary crawling, or unrelated DataForSEO surfaces.
- Do not rely on postback/pingback for the alpha implementation.

## 9. Schema discipline

Default rule:
- prefer the existing schema and `raw_payload`
- do not introduce a new migration unless it is truly required for correctness

Use a migration only if a required provider field cannot be represented without breaking correctness, provenance, or debuggability.

## 10. Good changes vs bad changes

### Good changes
- small provider-specific PRs
- explicit feature-flag checks for risky lanes
- bounded provider calls and timeout handling
- source-role-aware normalization
- preserving raw provider payloads for debugging
- targeted verification after provider PRs land

### Bad changes
- hidden state coupling
- source-role ambiguity
- treating DataForSEO as canonical
- adding a migration for convenience rather than necessity
- mixing Adzuna, DataForSEO, verification, and UI work in one PR
- adding browser automation or auto-apply scope

## 11. PR template for tonight

Each PR description should include:
- purpose
- exact provider or verification scope
- files touched
- out of scope
- migration impact
- feature flags added/changed
- env vars required for verification
- tests added/updated
- known follow-up dependencies

## 12. Escalation rules

Stop and ask for review if:
- DataForSEO Google Jobs cannot be implemented cleanly within the bounded synchronous task model
- Adzuna credential or field limitations materially change the design
- a required provider field truly cannot fit the current schema without a migration
- a route contract change would break multiple existing consumers
- provider normalization cannot fit the canonical/discovery confidence model without more product decisions

## 13. Definition of success for coding agents

You are successful tonight when the system moves toward:
- Adzuna working with real credentials
- DataForSEO Google Jobs working with real credentials
- discovery-originated jobs reaching artifact-ready
- ready-to-apply throughput staying usable

without violating:
- manual apply boundary
- source-confidence discipline
- small-PR discipline
- tonight's stop conditions
