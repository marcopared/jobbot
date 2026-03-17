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
3. `docs/TODO.md`
4. `docs/IMPLEMENTATION_PLAN.md`
5. the real repo for current baseline implementation
6. the ingestion feasibility research doc for provider strategy (when available)

Do **not** infer product scope from older comments, scaffold, patches, or synthetic repo summaries.

## 2. Product constraints

These are hard constraints:
- manual apply remains the final human step
- no automated application submission
- no browser automation for applications
- discovery sources are not canonical truth by default
- SERP-derived sources are optional, lower-confidence, and feature-flagged
- generic arbitrary crawling is not a first-wave requirement

## 3. Source-role discipline

Always distinguish:
- canonical ATS sources
- discovery sources
- direct URL ingest

Never collapse these roles into one generic notion of “job source” without preserving role and confidence.

## 4. Review discipline

Prefer small PRs.

Each PR should have:
- one clear purpose
- explicit out-of-scope statement
- focused tests
- no speculative extra scope

## 5. Safe assumptions

Safe assumptions from the current repo baseline (verify against real repo):
- **Canonical ATS:** Greenhouse, Lever, Ashby connectors exist; generalized `POST /api/jobs/run-ingestion`
- **Discovery:** JobSpy scrape; AGG-1 and SERP1 (feature-flagged) via `POST /api/jobs/run-discovery`
- **URL ingest:** `POST /api/jobs/ingest-url` for supported Greenhouse/Lever/Ashby URLs
- **Resume generation:** manual via `POST /api/jobs/{id}/generate-resume`; auto when `ENABLE_AUTO_RESUME_GENERATION=true` and job passes generation gate
- **Ready-to-apply:** `GET /api/jobs/ready-to-apply` feed exists
- **Resolution:** `POST /api/jobs/{id}/resolve` for discovery-to-canonical enrichment; attempts recorded in `job_resolution_attempts`
- **Manual apply** is the final user step; no browser automation

## 6. Unsafe assumptions

Do not assume:
- existing schema already supports discovery vs canonical roles cleanly
- existing pipeline states are expressive enough for the new flow
- discovery records should auto-generate resumes by default
- any SERP/provider integration will be durable enough to use as canonical truth
- all docs in the repo are up to date unless they match the refreshed docs

## 7. Implementation guardrails

### Good changes
- additive migrations
- explicit state transitions
- source-role-aware models
- provider-specific URL ingestion
- generation gating
- feature flags for risky lanes

### Bad changes
- hidden state coupling
- source-role ambiguity
- auto-generating artifacts for the full corpus
- adding browser automation
- mixing UI, migrations, connectors, and worker logic in a single PR

## 8. PR templates for agents

Each PR description should include:
- purpose
- files touched
- out of scope
- migration impact
- feature flags added/changed
- tests added/updated
- known follow-up dependencies

## 9. Suggested agent order

1. docs / audit
2. DB/model layer
3. official ATS expansion + URL ingest
4. broad discovery lane
5. automation funnel
6. UI

## 10. Escalation rules

Stop and ask for review if:
- a schema change would force broad data loss or rewrite
- AGG-1 account/field limitations materially change the design
- a SERP provider requires behavior that conflicts with product constraints
- a route contract change would break multiple existing consumers
- provider normalization cannot fit the canonical model without more product decisions

## 11. Definition of success for coding agents

You are successful when the system moves toward:
- broader ingestion
- clearer provenance
- safer automation
- ready-to-apply throughput

without violating:
- manual apply boundary
- source-confidence discipline
- small-PR discipline
