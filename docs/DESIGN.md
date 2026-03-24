# DESIGN.md — JobBot System Design

## Design Baseline

JobBot is designed around one clear boundary: automate preparation, not application.

The system is intentionally narrow:

- ingest jobs from a small number of bounded sources
- normalize and score them deterministically
- classify them into a small persona model
- extract ATS-oriented signals
- generate grounded artifacts only for eligible jobs
- hand the final apply action back to the user

## Design Principles

1. Broad discovery, narrow generation.
2. Discovery is coverage; canonical ATS is truth.
3. Resume generation must be grounded in structured inventory, not freeform LLM output.
4. Manual apply is a permanent product boundary.
5. Current code beats stale phase narratives.
6. Tests and persisted run records are part of the product contract.

## Source Model

### Canonical ATS

- Greenhouse
- Lever
- Ashby

These are the high-confidence providers for job content and apply URLs.

### Discovery

- JobSpy
- AGG-1 = Adzuna
- SERP1 = DataForSEO Google Jobs

These maximize coverage and should not be treated as canonical by default.

### Direct URL ingest

Supported ATS URLs let the user force deterministic ingestion from a known provider.

### Manual intake

Manual intake is the fallback when the user has a posting but not a supported direct ingest path.

## Pipeline Design

### Intake paths

- canonical ingestion
- discovery run
- URL ingest
- JobSpy scrape
- manual intake

### Shared downstream chain

`score -> classify -> ats_match -> generation_gate`

That chain is the main architectural spine of the application. All intake lanes eventually flow
through it, and discovery resolution rewinds enriched jobs back into it.

### Artifact generation

Artifact generation is deliberately conservative:

- requires completed ATS analysis
- uses the experience inventory YAML as the only content source
- selects and lightly rewrites grounded bullets
- renders HTML, then PDF via Playwright

## Current Operator Surfaces

- Ready to Apply
- All Jobs
- Runs
- Job detail
- Run detail
- Manual job intake

The UI is an operator console, not a consumer product and not an autonomous agent controller.

## Design Decisions Worth Preserving

1. `GenerationRun` is durable and created before queueing generation work.
2. `ScrapeRun.items_json` has a canonical reader/writer normalization layer.
3. Resolution enriches the existing discovery job instead of creating a second canonical job row.
4. Discovery confidence is explicit and feeds generation gating.
5. Signed artifact URLs are generated on demand for GCS-backed storage.

## What This Design Does Not Promise

- no full state-machine redesign
- no auto-apply flow
- no arbitrary crawling platform
- no claim that every provider path is fully end-to-end verified at all times
