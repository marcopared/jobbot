# Codex adapter for JobBot

> Read `../AGENTS.md` first.
> This file exists to make Codex sessions self-sufficient and implementation-oriented without drifting from the root instruction layer.

## Canonical Rule

- `../AGENTS.md` is the canonical instruction layer.
- If this file and the root file ever diverge, follow the root file.
- Treat implemented code as the source of truth when older documentation or stale plans disagree.

## What JobBot Is

JobBot is a local-first job discovery and decision-support system. It ingests jobs from canonical
ATS providers and lower-confidence discovery lanes, scores and classifies them, runs ATS analysis,
generates grounded resume artifacts for eligible jobs, and stops at a manual ready-to-apply queue.

Current approved ingestion-v2 direction:
- widen ingestion through source adapters and acquisition backends
- keep JobBot-owned persistence, run tracking, and downstream analysis as the center of gravity
- use Scrapling as the default acquisition-backend direction for most non-API and non-auth-heavy sources
- use bb-browser only as a bounded authenticated browser/session capability layer for a small subset of auth-bound or browser-native ingestion sources

## Hard Boundaries

1. Manual apply is the current implemented final human step.
2. Do not add auto-apply or browser automation for application flows.
3. Do not add form-fill logic, application submission logic, or hidden browser apply flows.
4. Keep discovery sources distinct from canonical ATS sources.
5. SERP1 is always feature-flagged and lower-confidence than AGG-1 and canonical ATS.
6. Keep acquisition infrastructure separate from product/business logic.
7. Do not document approved direction as implemented runtime unless the code now does it.

## Current Pipeline Truths To Preserve

- Source-role distinctions matter:
  - `canonical`
  - `discovery`
  - `url_ingest`
- The implemented pipeline remains:
  `INGESTED -> SCORED or REJECTED -> CLASSIFIED -> ATS_ANALYZED -> RESUME_READY`
- The downstream analysis spine remains:
  `score -> classify -> ats_match -> generation_gate`
- Manual generation must persist `GenerationRun` before queueing work.
- `ScrapeRun` and `GenerationRun` must reach durable terminal states.
- Resume generation must remain grounded in structured inventory data, not freeform LLM output.
- Run-item payloads must stay backward-compatible with the UI contract.

## Ingestion-V2 Rules

When working on ingestion-v2:
- prefer widening the acquisition layer over rewriting persistence or downstream analysis
- keep JobBot core stable
- treat source adapters as source-specific extraction, field-mapping, and provenance logic
- treat acquisition backends as transport/browser/session mechanics only
- use Scrapling as the default backend direction for most new non-auth-heavy sources
- use bb-browser only where an authenticated browser/session is genuinely needed
- do not let bb-browser own:
  - trust policy
  - source-role policy
  - scoring
  - classification
  - ATS analysis
  - generation gating
  - persistence contracts
  - application logic
- single-session sequential bb-browser use is acceptable
- do not build parallel browser-worker architecture unless a task explicitly requires it
- do not treat bb-browser as a CAPTCHA or anti-bot strategy

## Repository Map

```text
AGENTS.md                     <- Root canonical instruction layer
.codex/AGENTS.md              <- This Codex-specific adapter
ARCHITECTURE.md               <- Runtime topology, subsystem map, dependency rules
README.md                     <- Setup, run commands, quick start
docs/
├── DESIGN.md                 <- System design baseline + approved ingestion-v2 direction
├── PRODUCT_SENSE.md          <- Product intent and boundaries
├── RELIABILITY.md            <- Invariants, tests, and verification limits
├── SECURITY.md               <- Security-relevant boundaries and controls
├── FRONTEND.md               <- UI surface and operator flow
├── PLANS.md                  <- Plan index
├── design-docs/
│   ├── index.md
│   └── core-beliefs.md
├── product-specs/
│   ├── index.md
│   ├── source-lanes-and-manual-apply.md
│   ├── ready-to-apply-operator-loop.md
│   └── manual-intake-and-generation.md
├── exec-plans/
│   ├── active/
│   │   └── 2026-04-02-ingestion-v2-docs-and-architecture.md
│   ├── completed/
│   └── tech-debt-tracker.md
└── references/
```

## Read Order For Codex

1. `../AGENTS.md`
2. `../ARCHITECTURE.md`
3. `../docs/DESIGN.md`
4. `../docs/PRODUCT_SENSE.md`
5. `../docs/RELIABILITY.md`
6. `../docs/SECURITY.md`
7. `../docs/design-docs/index.md`
8. `../docs/product-specs/index.md`
9. `../docs/exec-plans/active/2026-04-02-ingestion-v2-docs-and-architecture.md`
10. `../README.md`

## Change Rules

1. Preserve the source-role model.
2. Preserve current route names unless a task explicitly requires a new route and the change is justified.
3. Preserve current queue names unless a task explicitly requires otherwise and the change is justified.
4. Preserve current pipeline states unless a task explicitly requires otherwise and the change is justified.
5. Preserve ScrapeRun durability and items_json compatibility.
6. Prefer compatibility adapters and bounded refactors over broad rewrites when introducing ingestion-v2 seams.
7. Keep UI changes minimal and operator-centric.
8. Do not let docs drift behind runtime-affecting code changes.

## Verification Minimum

- Backend pipeline, worker, contract, or ingestion changes:
  - `bash scripts/run_regression_invariants.sh`
- UI changes:
  - `cd ui && npm run build`
- Runtime-affecting changes:
  - confirm docs still match code before closing the task

## Where To Look

| Need | File |
| --- | --- |
| Root rules and boundaries | `../AGENTS.md` |
| Runtime topology | `../ARCHITECTURE.md` |
| Design baseline and ingestion-v2 direction | `../docs/DESIGN.md` |
| Product boundary | `../docs/PRODUCT_SENSE.md` |
| Reliability invariants | `../docs/RELIABILITY.md` |
| Security and authenticated-browser ingestion limits | `../docs/SECURITY.md` |
| Design-doc index | `../docs/design-docs/index.md` |
| Product specs | `../docs/product-specs/index.md` |
| Active ingestion-v2 plan | `../docs/exec-plans/active/2026-04-02-ingestion-v2-docs-and-architecture.md` |
| Setup and commands | `../README.md` |
