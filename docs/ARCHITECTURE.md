# JobBot Architecture

## Document purpose

This document describes the **current architecture** (source of truth: the real repository), implemented components, and remaining gaps.

It should be read together with:
- `SPEC.md` for product behavior and boundaries
- `TODO.md` for milestones and backlog
- `IMPLEMENTATION_PLAN.md` for PR boundaries and merge order
- `CODING_AGENT_GUIDE.md` for coding-agent operating instructions
- `IMPLEMENTATION_STATUS.md` for a verification audit of what is implemented vs aspirational

## 1. Current system (implemented)

Source of truth: the real repository. The codebase has:
- **Canonical ATS:** Greenhouse, Lever, Ashby ingestion
- **Discovery:** JobSpy scrape; AGG-1 and SERP1 (feature-flagged)
- **URL ingest:** supported ATS job URLs (Greenhouse, Lever, Ashby)
- Deterministic scoring, rules-based classification, ATS analysis
- Generation gate; manual and auto resume generation (auto when `ENABLE_AUTO_RESUME_GENERATION=true`)
- Ready-to-apply feed (`GET /api/jobs/ready-to-apply`) and UI
- React + Vite UI
- Redis + Celery worker topology using `default`, `scrape`, and `ingestion` queues

The current end-to-end flow:
- scrape/ingest/discovery/url -> score -> classify -> ats_match -> generation gate -> (manual or auto) generate-resume -> manual apply

## 2. Current end-to-end flow

The implemented flow:
1. ingest from discovery and canonical source lanes (JobSpy, AGG-1, SERP1, Greenhouse, Lever, Ashby, URL ingest)
2. normalize and deduplicate
3. score
4. classify
5. run ATS analysis
6. evaluate generation gate
7. automatically generate artifact when eligible (or manual via `POST /api/jobs/{id}/generate-resume`)
8. surface in ready-to-apply queue
9. user manually applies

Discovery-to-canonical resolution is implemented via `POST /api/jobs/{id}/resolve`; resolution attempts are recorded in `job_resolution_attempts`.

## 3. Source architecture

### 3.1 Source roles

All sources must be treated as one of three roles.

#### Canonical sources
High-confidence, provider-specific sources used for trusted job content and apply flow.

Initial canonical set:
- Greenhouse
- Lever
- Ashby

#### Discovery sources
Broad, query-driven sources used for coverage.

Initial discovery set:
- JobSpy
- AGG-1
- one optional SERP provider

#### Direct URL ingest
Deterministic provider-specific ingest using a pasted job URL.

Initial direct URL providers:
- Greenhouse
- Lever
- Ashby

### 3.2 Source strategy rules

- discovery sources are not canonical truth by default
- canonical sources win during merge/reconciliation
- discovery sources may still be sufficient for downstream processing if their content quality and apply URL quality are strong enough
- SERP-derived sources must remain lower-confidence and feature-flagged

## 4. Connector architecture

The existing connector abstraction should be extended, not discarded.

### 4.1 Connector classes

Target conceptual split:
- `CanonicalConnector`
- `DiscoveryConnector`
- `UrlResolver` or provider detector for direct URL ingest

The current `fetch_raw_jobs()` and `normalize(raw_job)` shape is still directionally correct.

### 4.2 Target payload types

#### DiscoveredJobPayload
Used for broad discovery sources.
Likely fields:
- source_name
- external_id
- title
- company
- location
- description
- apply_url
- source_url
- posted_at
- raw_payload
- normalized_title
- normalized_company
- normalized_location
- source_confidence
- content_quality_score

#### CanonicalJobPayload
Used for high-confidence provider sources.
Likely fields:
- source_name
- external_id
- title
- company
- location
- employment_type
- workplace_type
- description
- apply_url
- source_url
- posted_at
- requisition_id
- department
- salary_min
- salary_max
- salary_currency
- salary_interval
- raw_payload
- normalized_title
- normalized_company
- normalized_location

## 5. Data model

The current backbone remains valid:
- `jobs`
- `job_sources`
- `job_analyses`
- `scrape_runs`
- artifacts table

The next wave should extend this model instead of replacing it.

### 5.1 `jobs` columns

**Implemented (migration 004):** source_role, source_confidence, canonical_source_name, canonical_external_id, canonical_url, workplace_type, employment_type, department, team, requisition_id, salary_currency, salary_interval, location_structured_json, content_quality_score, generation_eligibility, generation_reason, artifact_ready_at, auto_generated_at, resolution_status, resolution_confidence, stale_flag

**Target (not yet added):**
- job_url_status
- apply_url_verified
- salary_text
- source_last_seen_at
- source_updated_at
- closed_at

### 5.2 `job_sources` columns

Target (not yet added):
- `source_role`
- `source_priority`
- `provider_url`
- `resolved_from_job_source_id`
- `last_seen_at`
- `response_fetched_at`
- `content_hash`
- `discovery_query`
- `search_metadata_json`
- `raw_description_present`
- `url_present`

### 5.3 Tables

#### Implemented (migration 004)

**`job_resolution_attempts`** — Records discovery-to-canonical resolution attempts (success/failure, confidence, reason). Used by `POST /api/jobs/{id}/resolve` and `resolve_discovery_job` task.

**`generation_runs`** — Records automatic and manual generation attempts; tracks status, inputs hash, failure reason, artifact linkage.

#### Target (optional)

**`source_configs`**
Purpose:
- feature-flag sources
- manage credentials and rate-limit caps
- keep source-specific settings out of hardcoded logic

## 6. Deduplication and reconciliation

The current deterministic dedup hash remains useful but is not sufficient by itself once multiple discovery and canonical lanes coexist.

### 6.1 Priority order

1. exact source identity: `(source_name, external_id)`
2. canonical job URL or apply URL
3. deterministic hash of normalized company/title/location and requisition ID when available
4. fuzzy assist for discovery-only cases

### 6.2 Merge rule

Canonical records must be able to absorb weaker discovery records.

Discovery records must not overwrite stronger canonical data.

### 6.3 Resolution rule

When a discovery job resolves to a supported ATS source later, the canonical record becomes the primary job view and the discovery record becomes provenance.

## 7. Pipeline states

### 7.0 Current pipeline states (implemented)

The system uses these states today:
- `INGESTED`
- `SCORED`
- `REJECTED`
- `CLASSIFIED`
- `ATS_ANALYZED`
- `RESUME_READY`

### 7.1 Target pipeline states (aspirational)

Target pipeline states:
- `DISCOVERED`
- `NORMALIZED`
- `DEDUPED`
- `RESOLUTION_PENDING`
- `RESOLVED_CANONICAL`
- `RESOLVED_DISCOVERY_ONLY`
- `SCORED`
- `REJECTED`
- `CLASSIFIED`
- `ATS_ANALYZED`
- `GENERATION_QUEUED`
- `RESUME_READY`
- `FAILED`
- `SKIPPED`

### 7.2 Skip reasons

`SKIPPED` must include an explicit reason:
- low score
- low content quality
- unresolved low-confidence discovery result
- duplicate absorbed
- missing or invalid apply URL
- stale job
- generation threshold not met

## 8. Worker topology

### 8.1 Current baseline queues
- `default`
- `scrape`
- `ingestion`

### 8.2 Target queues
- `discovery`
- `ingestion`
- `resolution`
- `analysis`
- `generation`
- `maintenance`

The migration to this queue model can be incremental, but the target behavior should be clear from the beginning.

## 9. Task graph

### 9.1 Discovery path
`run_discovery_task`
-> normalize discovery results
-> dedup/provenance
-> `resolve_job_task`
-> score
-> classify
-> ats_match
-> generation gate
-> generate resume when eligible

### 9.2 Canonical ingest path
`ingest_canonical_task`
-> normalize canonical job
-> dedup/merge
-> score
-> classify
-> ats_match
-> generation gate
-> generate resume when eligible

### 9.3 URL ingest path
`ingest_url_task`
-> detect provider
-> canonical ingest using provider-specific connector
-> same downstream pipeline

## 10. Generation gate

The generation gate is the throughput control for the entire system.

A job is generation-eligible only when:
- score threshold met
- ATS analysis completed
- description/content quality sufficient
- apply URL present and usable
- source confidence acceptable
- stale flag false
- no equivalent artifact already exists for unchanged content

Recommended default behavior:
- canonical ATS jobs: eligible at moderate threshold
- AGG-1 discovery jobs: eligible only at stricter threshold and sufficient content quality
- SERP-only unresolved jobs: not eligible by default

## 11. API design

### 11.1 Keep and generalize current routes
The current baseline already includes jobs, artifacts, runs, and manual generate-resume routes.

### 11.2 Routes (implemented unless noted)

#### `POST /api/jobs/run-ingestion` — implemented
Generalized canonical-source ingestion.
Supported connectors: greenhouse, lever, ashby

#### `POST /api/jobs/run-discovery` — implemented
Broad discovery ingestion.
Supported connectors: agg1, optional serp1 (feature-flagged)

#### `POST /api/jobs/ingest-url` — implemented
Deterministic ATS URL ingest.
Supported providers: greenhouse, lever, ashby

#### `POST /api/jobs/{id}/resolve` — implemented
Force canonical enrichment attempt for a discovery record. Records attempts in `job_resolution_attempts`.

#### `POST /api/jobs/{id}/generate-resume` — implemented
Manual override and regeneration.

#### `GET /api/jobs/ready-to-apply` — implemented
Primary backend feed for the default workflow.

#### expanded `GET /api/jobs`
Should support filters for:
- source role
- source confidence
- generation eligibility
- artifact-ready
- canonical source
- workplace type
- needs-resolution
- include rejected/skipped when debugging

## 12. UI architecture

The UI should shift from review-centric to throughput-centric.

### 12.1 Primary views
- Ready to Apply
- Promising / In Progress
- Needs Resolution
- All Jobs / Debug
- Runs

### 12.2 Job detail page
Must show:
- source stack / provenance
- canonical vs discovery status
- score breakdown
- ATS gaps
- generation status
- artifact download
- apply link

### 12.3 URL ingest
A top-level entry point should allow pasting a supported ATS job URL.

## 13. Source-specific rules

### 13.1 Greenhouse — implemented
Canonical baseline. Generalizes into the broader canonical-source model.

### 13.2 Lever — implemented
Official ATS connector. Treat as canonical source.

### 13.3 Ashby — implemented
Official ATS connector. Treat as canonical source.

### 13.4 AGG-1 — implemented
Structured broad discovery lane. Treat as discovery, not canonical truth.
Query-driven retrieval; feature-flagged (`ENABLE_AGG1_DISCOVERY`).

### 13.5 SERP provider — implemented (stub)
Optional and feature-flagged (`ENABLE_SERP1_DISCOVERY`).
Treat as discovery-only and lower-confidence.
Stub returns empty; full implementation optional.

## 14. Observability

Add explicit metrics for:
- ingestion volume by source
- resolution success rate
- dedup absorption rate
- generation eligibility rate
- generation success/failure rate
- stale URL rate
- jobs ready-to-apply per day

Add structured logging context for:
- `trace_id`
- `job_id`
- `source_name`
- `source_role`
- `run_id`
- `generation_run_id`

## 15. Failure handling

The system should fail explicitly and observably.

Required behaviors:
- retry transient network/provider errors with backoff
- record resolution failures separately from generation failures
- keep discovery-only low-confidence jobs from silently auto-generating
- mark stale or invalid apply URLs explicitly

## 16. Implementation constraints

These constraints are mandatory:
- no auto-apply
- no browser automation
- no generic arbitrary crawling in the first implementation wave
- do not treat SERP/discovery-only records as equivalent to canonical ATS records
- keep rollout incremental and feature-flagged where appropriate

## 17. Rollout shape

**Implementation order** (phases 2–5 implemented; see `IMPLEMENTATION_PLAN.md`):
1. documentation refresh
2. DB/model foundation — implemented
3. official ATS expansion + URL ingest — implemented
4. AGG-1 discovery lane (SERP optional, feature-flagged) — implemented
5. generation gate + automatic artifact flow — implemented
6. UI ready-to-apply rework — partially implemented

**Do not touch:** SERP as canonical truth; auto-apply or browser automation; generic arbitrary crawling. See `IMPLEMENTATION_PLAN.md` §2.

## 18. Definition of done (mostly satisfied)

The following are implemented:
- source roles are explicit in the model and APIs
- Greenhouse, Lever, and Ashby work as canonical connectors
- supported ATS URL ingest works
- AGG-1 discovery works (feature-flagged)
- generation is automated for eligible jobs when `ENABLE_AUTO_RESUME_GENERATION=true`
- ready-to-apply feed exists
- manual application remains the final step

**Still remaining:** full target pipeline states; UI polish.
