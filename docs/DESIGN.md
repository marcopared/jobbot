# DESIGN.md — JobBot System Design

## Design Baseline

JobBot is designed around one clear boundary: automate preparation, not application.

The implemented system is intentionally narrow:

- ingest jobs from a small number of bounded sources
- normalize and persist them in JobBot-owned storage
- score them deterministically
- classify them into a small persona model
- extract ATS-oriented signals
- generate grounded artifacts only for eligible jobs
- stop at manual apply today

## Design Principles

1. Broad discovery, narrow generation.
2. Discovery is coverage; canonical ATS is truth.
3. Resume generation must be grounded in structured inventory, not freeform LLM output.
4. Manual apply is the current implemented product boundary.
5. Current code beats stale phase narratives.
6. Tests and persisted run records are part of the product contract.
7. Acquisition infrastructure should remain separate from downstream product logic.

## Current Implemented Design

### Source model

#### Canonical ATS

- Greenhouse
- Lever
- Ashby

These are the high-confidence providers for job content and apply URLs.

#### Discovery

- JobSpy
- AGG-1 = Adzuna
- SERP1 = DataForSEO Google Jobs
- startupjobs.nyc
- Tech:NYC Jobs
- Primary Venture Partners Jobs Board
- Greycroft Jobs Board
- Union Square Ventures Jobs Board
- Built In NYC
- Welcome to the Jungle

These maximize coverage and should not be treated as canonical by default.

Registered but currently gated or explicitly unsupported public-board adapters:

- TrueUp
- Underdog.io
- VentureLoop

#### Direct URL ingest

Supported ATS URLs let the user force deterministic ingestion from a known provider.

#### Manual intake

Manual intake is the fallback when the user has a posting but not a supported direct ingest path.

Current trust rules:

- canonical ATS remains the highest-trust source for content and apply URLs
- discovery remains distinct from canonical ATS
- SERP1 remains lower-confidence and feature-flagged
- direct URL ingest and manual intake still feed the same persisted job model

### Intake paths

- canonical ingestion
- discovery run
- source-adapter launch:
  - public boards
  - portfolio boards
  - auth boards
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
- ends in a ready-to-apply queue and external manual apply URL

### Current operator surfaces

- Ready to Apply
- All Jobs
- Runs:
  - legacy launchers for JobSpy, canonical ATS, and broad discovery
  - capability-backed source-adapter launcher for public-board, portfolio-board, and auth-board
    sources
- Job detail
- Run detail
- Manual job intake

The UI is an operator console, not a consumer product and not an autonomous agent controller.

### Preserved contracts

1. `GenerationRun` is durable and created before queueing generation work.
2. `ScrapeRun.items_json` has a canonical reader/writer normalization layer.
3. Resolution enriches the existing discovery job instead of creating a second canonical job row.
4. Discovery confidence is explicit and feeds generation gating.
5. Signed artifact URLs are generated on demand for GCS-backed storage.

## Approved Ingestion-V2 Direction

This section describes approved near-term architecture direction and the currently implemented
backend/source seams. It does not claim that every planned ingestion-v2 source family is already
implemented.

### Current vs approved direction

Current implementation mixes source-specific acquisition mechanics more tightly into provider and
worker paths than the target design intends.

Approved ingestion-v2 direction:

`source adapters -> acquisition backends -> JobBot-owned normalization/persistence -> score -> classify -> ats_match -> generation_gate`

Intended responsibilities:

- source adapters own source-specific extraction, field mapping, and provenance rules
- acquisition backends own transport, browser, and session mechanics only
- JobBot-owned normalization and persistence remain responsible for dedupe, schema mapping, run
  records, and durable job state
- the downstream analysis chain remains the same application spine after persistence

### Acquisition backend direction

- Scrapling is the approved default acquisition backend direction for most non-API and
  non-auth-heavy sources.
- bb-browser is the approved selective authenticated-session backend direction for a small subset
  of browser-native or auth-bound sources.
- The bb-browser session backend is now implemented for ingestion-only acquisition, with initial
  LinkedIn Jobs, Wellfound, and YC adapters behind explicit feature flags and backend config.
- bb-browser is a capabilities layer only. It does not own JobBot product logic, business rules,
  scoring, classification, ATS analysis, generation gating, or persistence contracts.
- The architecture is being shaped so that a browser-capability backend can be reused later where
  appropriate, but this document is only updating ingestion scope.

## What Ingestion-V2 Does Not Change

- the database remains the center of gravity
- downstream analysis remains the same spine: `score -> classify -> ats_match -> generation_gate`
- current product output still ends in manual apply
- the design is not becoming a mass-crawl platform
- the design is not making every source browser-first by default

## What This Design Does Not Promise

- no full state-machine redesign
- no auto-apply flow
- no arbitrary crawling platform
- no claim that every provider path is fully end-to-end verified at all times
