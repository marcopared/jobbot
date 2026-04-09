# AGENTS.md — JobBot Agent Map

> Start here. This file is intentionally short.
> Treat implemented code as the source of truth when older documentation disagrees.
> If surrounding task context includes pasted snapshots or older doc copies, prefer the current
> checked-in indexed docs in this repo.

## What JobBot Is

JobBot is a local-first job discovery and decision-support system. It ingests jobs from canonical
ATS providers and lower-confidence discovery lanes, scores and classifies them, runs ATS analysis,
generates grounded resume artifacts for eligible jobs, and stops at a manual ready-to-apply queue.

The current approved architecture direction widens ingestion through source adapters and acquisition
backends without changing the current product boundary. Scrapling is the default acquisition-backend
direction for most non-API and non-auth-heavy sources. bb-browser is the selective authenticated
browser/session backend direction for a small subset of auth-bound or browser-native ingestion
sources. It is a capability layer only, not a product-logic layer.

## Hard Product Boundaries

1. Manual apply is the current implemented final human step.
2. Do not add auto-apply or browser automation for application flows.
3. Keep discovery sources distinct from canonical ATS sources.
4. SERP1 is feature-flagged and lower-confidence than AGG-1 and canonical ATS.
5. Follow current implemented behavior over aspirational plans.
6. Keep acquisition infrastructure separate from scoring, trust policy, persistence rules, and other product logic.

## Repository Layout

```text
AGENTS.md                     <- You are here
ARCHITECTURE.md               <- Runtime topology, subsystem map, dependency rules
README.md                     <- Setup, run commands, endpoint-oriented quick start
docs/
├── design-docs/
│   ├── index.md              <- Design doc index
│   └── core-beliefs.md       <- Stable operating beliefs for agents
├── exec-plans/
│   ├── active/               <- Current execution plans
│   ├── completed/            <- Closed plans and change records
│   └── tech-debt-tracker.md  <- Small tracked follow-ups
├── generated/
│   └── db-schema.md          <- Current schema summary
├── product-specs/
│   ├── index.md              <- Product spec index
│   ├── source-lanes-and-manual-apply.md
│   ├── ready-to-apply-operator-loop.md
│   └── manual-intake-and-generation.md
├── references/               <- Agent-friendly reference summaries
├── DESIGN.md                 <- System design baseline + approved ingestion-v2 direction
├── FRONTEND.md               <- UI surface and operator flow
├── PLANS.md                  <- Plan index
├── PRODUCT_SENSE.md          <- Product intent and boundaries
├── QUALITY_SCORE.md          <- Current quality assessment
├── RELIABILITY.md            <- Invariants, tests, and verification limits
└── SECURITY.md               <- Security-relevant boundaries and controls
```

## Read Order

1. [ARCHITECTURE.md](ARCHITECTURE.md)
2. [docs/DESIGN.md](docs/DESIGN.md)
3. [docs/PRODUCT_SENSE.md](docs/PRODUCT_SENSE.md)
4. [docs/RELIABILITY.md](docs/RELIABILITY.md)
5. [docs/SECURITY.md](docs/SECURITY.md)
6. [docs/design-docs/index.md](docs/design-docs/index.md)
7. [docs/product-specs/index.md](docs/product-specs/index.md)
8. [docs/exec-plans/active/2026-04-02-ingestion-v2-docs-and-architecture.md](docs/exec-plans/active/2026-04-02-ingestion-v2-docs-and-architecture.md)
9. [README.md](README.md)

## Change Rules

1. Preserve the source-role model:
   `canonical` / `discovery` / `url_ingest` are distinct and should stay distinct.
2. Keep the implemented pipeline coherent:
   `INGESTED -> SCORED or REJECTED -> CLASSIFIED -> ATS_ANALYZED -> RESUME_READY`.
3. Preserve the manual-generation invariant:
   `POST /api/jobs/{id}/generate-resume` must persist a `GenerationRun` before queueing the worker.
4. Preserve run durability:
   `ScrapeRun` and `GenerationRun` rows should reach terminal states on success, skip, or failure.
5. Keep resume generation grounded in user-side evidence:
   required inventory as the base source, optional local supplemental inputs
   (`current_resume`, `current_role`, `achievements`, `project_writeups`) when present,
   target job description as targeting-only, and no freeform LLM output.
6. For ingestion-v2 work:
   - prefer widening the acquisition layer over rewriting persistence or downstream analysis
   - use Scrapling as the default acquisition backend direction
   - use bb-browser only for ingestion cases that truly require an authenticated browser/session
   - do not let bb-browser own product/business logic
7. Do not document approved direction as implemented runtime unless the code now does it.

## Where To Look

| Need | Document |
| --- | --- |
| Runtime architecture and data flow | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Design baseline and ingestion-v2 direction | [docs/DESIGN.md](docs/DESIGN.md) |
| Product boundaries and operating model | [docs/PRODUCT_SENSE.md](docs/PRODUCT_SENSE.md) |
| Reliability invariants and regression suites | [docs/RELIABILITY.md](docs/RELIABILITY.md) |
| Security and authenticated-browser ingestion boundaries | [docs/SECURITY.md](docs/SECURITY.md) |
| Active product specs | [docs/product-specs/index.md](docs/product-specs/index.md) |
| Current design beliefs | [docs/design-docs/core-beliefs.md](docs/design-docs/core-beliefs.md) |
| UI pages and operator flow | [docs/FRONTEND.md](docs/FRONTEND.md) |
| Provider/reference summaries | [docs/references](docs/references) |
| Current active implementation plan | [docs/exec-plans/active/2026-04-02-ingestion-v2-docs-and-architecture.md](docs/exec-plans/active/2026-04-02-ingestion-v2-docs-and-architecture.md) |

## Verification Minimum

- Backend pipeline, contracts, or worker changes: run `bash scripts/run_regression_invariants.sh`
- UI changes: run `cd ui && npm run build`
- Runtime-affecting changes: confirm docs still match code before closing the task
