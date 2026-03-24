# AGENTS.md — JobBot Agent Map

> Start here. This file is intentionally short.
> Treat implemented code as the source of truth when older documentation disagrees.

## What JobBot Is

JobBot is a local-first job discovery and decision-support system. It ingests jobs from canonical
ATS providers and lower-confidence discovery lanes, scores and classifies them, runs ATS analysis,
generates grounded resume artifacts for eligible jobs, and stops at a manual ready-to-apply queue.

## Hard Product Boundaries

1. Manual apply is the final human step.
2. Do not add auto-apply or browser automation for applications.
3. Keep discovery sources distinct from canonical ATS sources.
4. SERP1 is feature-flagged and lower-confidence than AGG-1 and canonical ATS.
5. Follow current implemented behavior over aspirational plans.

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
├── references/              <- Agent-friendly reference summaries
├── DESIGN.md                <- System design baseline
├── FRONTEND.md              <- UI surface and operator flow
├── PLANS.md                 <- Plan index
├── PRODUCT_SENSE.md         <- Product intent and boundaries
├── QUALITY_SCORE.md         <- Current quality assessment
├── RELIABILITY.md           <- Invariants, tests, and verification limits
└── SECURITY.md              <- Security-relevant boundaries and controls
```

## Read Order

1. [ARCHITECTURE.md](/Users/marcoparedes/dev/jobbot/ARCHITECTURE.md)
2. [docs/PRODUCT_SENSE.md](/Users/marcoparedes/dev/jobbot/docs/PRODUCT_SENSE.md)
3. [docs/RELIABILITY.md](/Users/marcoparedes/dev/jobbot/docs/RELIABILITY.md)
4. [docs/design-docs/index.md](/Users/marcoparedes/dev/jobbot/docs/design-docs/index.md)
5. [docs/product-specs/index.md](/Users/marcoparedes/dev/jobbot/docs/product-specs/index.md)
6. [README.md](/Users/marcoparedes/dev/jobbot/README.md)

## Change Rules

1. Preserve the source-role model:
   `canonical` / `discovery` / `url_ingest` are distinct and should stay distinct.
2. Keep the implemented pipeline coherent:
   `INGESTED -> SCORED or REJECTED -> CLASSIFIED -> ATS_ANALYZED -> RESUME_READY`.
3. Preserve the manual-generation invariant:
   `POST /api/jobs/{id}/generate-resume` must persist a `GenerationRun` before queueing the worker.
4. Preserve run durability:
   `ScrapeRun` and `GenerationRun` rows should reach terminal states on success, skip, or failure.
5. Keep resume generation grounded in inventory data, not freeform LLM output.

## Where To Look

| Need | Document |
| --- | --- |
| Runtime architecture and data flow | [ARCHITECTURE.md](/Users/marcoparedes/dev/jobbot/ARCHITECTURE.md) |
| Product boundaries and operating model | [docs/PRODUCT_SENSE.md](/Users/marcoparedes/dev/jobbot/docs/PRODUCT_SENSE.md) |
| Reliability invariants and regression suites | [docs/RELIABILITY.md](/Users/marcoparedes/dev/jobbot/docs/RELIABILITY.md) |
| Active product specs | [docs/product-specs/index.md](/Users/marcoparedes/dev/jobbot/docs/product-specs/index.md) |
| Current design beliefs | [docs/design-docs/core-beliefs.md](/Users/marcoparedes/dev/jobbot/docs/design-docs/core-beliefs.md) |
| UI pages and operator flow | [docs/FRONTEND.md](/Users/marcoparedes/dev/jobbot/docs/FRONTEND.md) |
| Provider/reference summaries | [docs/references](/Users/marcoparedes/dev/jobbot/docs/references) |

## Verification Minimum

- Backend pipeline, contracts, or worker changes: run `bash scripts/run_regression_invariants.sh`
- UI changes: run `cd ui && npm run build`
- Runtime-affecting changes: confirm docs still match code before closing the task
