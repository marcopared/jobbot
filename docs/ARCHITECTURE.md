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
- **Discovery:** JobSpy scrape; AGG-1 and SERP1 lanes exist behind feature flags
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
- AGG-1 = Adzuna for this alpha implementation wave
- SERP1 = DataForSEO Google Jobs for this alpha implementation wave

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
- Adzuna is a medium-confidence discovery provider
- DataForSEO Google Jobs is a lower-confidence discovery provider than Adzuna
- SERP-derived sources must remain lower-confidence and feature-flagged

### 3.3 Provider-specific alpha discovery contract

The target provider contract for this wave is:

- `AGG-1 -> Adzuna`
- `SERP1 -> DataForSEO Google Jobs`

Current repo truth and target state must remain distinct:

- current repo truth: AGG-1 and SERP1 lanes exist, but the docs must not imply the Adzuna and DataForSEO implementations are already complete unless code lands
- alpha implementation target: Adzuna is the real structured discovery provider and DataForSEO Google Jobs is the real SERP discovery provider for this wave

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

### 4.3 Adzuna discovery design

Adzuna is the real `AGG-1` provider for this implementation wave.

Retrieval design:

- use the page-based search endpoint: `/jobs/{country}/search/{page}`
- fetch sequential pages per run until the per-run cap is reached or the provider returns no more useful results
- support a bounded page count so one discovery run cannot expand without limit

Query parameters and filters to support in alpha:

- `what` for the primary title/keyword search
- `where` for human-readable location targeting
- `distance` when a radius filter is supplied
- `results_per_page`
- `max_days_old`
- `sort_by=date` as the default freshness-oriented mode
- `salary_min`
- `salary_max`
- `full_time`
- `part_time`
- `contract`
- `permanent`
- `category` when the caller supplies a mapped category filter

Per-run fetch cap:

- impose a hard cap on total Adzuna jobs fetched per discovery run
- page count and `results_per_page` should both participate in that cap
- the cap is an implementation setting, but the architecture requires it to be explicit and enforced

Fields to map into the discovery model:

- `id -> external_id`
- `title`
- `company.display_name -> company`
- `location.display_name -> location`
- `description`
- `redirect_url -> apply_url` and source outbound URL
- `created -> posted_at`
- `category.label` or `category.tag` into discovery metadata when useful
- `salary_min`, `salary_max`, `contract_time`, `contract_type`, `latitude`, `longitude` when present

All provider fields that are not cleanly represented in the current schema should remain in `raw_payload`.

#### Alpha provider mapping fields

For the alpha implementation, the Adzuna normalization contract is frozen as:

- `id -> external_id`
- `title -> title`
- `company.display_name -> company`
- `location.display_name -> location`
- `description -> description`
- `redirect_url -> apply_url` and `source_url`
- `created -> posted_at`
- `salary_min -> salary_min`
- `salary_max -> salary_max`
- `contract_time -> contract_time`
- `contract_type -> contract_type`

Any Adzuna fields not mapped above must still be preserved in `raw_payload`.

### 4.4 DataForSEO Google Jobs discovery design

DataForSEO Google Jobs is the real `SERP1` provider target for this implementation wave.

Provider scope:

- use Google Jobs endpoints only
- do not broaden SERP1 to generic web search, arbitrary crawling, or non-jobs endpoints in this wave

Authentication:

- use DataForSEO basic auth credentials on each request

Synchronous wrapper design:

- submit a task with `/v3/serp/google/jobs/task_post`
- poll for readiness in a bounded loop using `/v3/serp/google/jobs/tasks_ready`
- fetch advanced normalized results with `/v3/serp/google/jobs/task_get/advanced/{id}`
- do not rely on postback/pingback for the alpha implementation
- do not use the HTML endpoint for the core alpha path

Request parameters to support in alpha:

- `keyword`
- one of `location_name` or `location_code`
- one of `language_code` or `language_name`
- `depth`
- `employment_type`
- `location_radius`
- `priority=1` by default unless the implementation later introduces an explicit reason to pay for higher priority

Normalization targets from advanced results:

- `job_id -> external_id`
- `title`
- `employer_name -> company`
- `location`
- `source_url -> apply_url` when usable
- `source_name`
- `salary`
- `contract_type`
- `timestamp` or `time_ago` into posted-time metadata
- `check_url` and raw item metadata into provenance/debug fields

Timeout and failure behavior:

- polling must be bounded by both attempt count and wall-clock timeout
- if `task_post` fails, the discovery run records a provider error and exits cleanly
- if polling times out, the run records a timeout or incomplete-provider result and does not block the rest of the pipeline
- if `task_get/advanced` fails after readiness, the run records the failure and does not fabricate partial normalized jobs

Confidence semantics:

- DataForSEO Google Jobs remains lower-confidence than Adzuna and lower-confidence than canonical ATS
- the results are discovery candidates only
- they must never be treated as canonical truth during merge, resolution, or generation decisions

#### Alpha provider mapping fields

For the alpha implementation, the DataForSEO Google Jobs normalization contract is frozen as:

- use a stable provider job id as `external_id` when present; otherwise derive a deterministic id from stable job fields
- `title -> title`
- `employer` or `company` provider field -> `company`
- `location -> location`
- `snippet` or `description` when available -> `description`
- `source_url` and `apply_url` when available -> `source_url` and `apply_url`
- `posted_at` when available -> `posted_at`
- all unmatched provider fields must be preserved in `raw_payload`

If the provider returns additional provenance or debugging fields such as `check_url`, timestamps, or result metadata, keep them in `raw_payload` unless there is already a first-class schema field for them.

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

### 5.1 Schema decision for the alpha discovery wave

- assume no new migration by default
- use the existing schema and `raw_payload` for provider-specific fields that do not yet map cleanly
- only add a new migration later if implementation proves a required provider field cannot be represented cleanly without harming correctness or debuggability

### 5.2 `jobs` columns

**Implemented (migration 004):** source_role, source_confidence, canonical_source_name, canonical_external_id, canonical_url, workplace_type, employment_type, department, team, requisition_id, salary_currency, salary_interval, location_structured_json, content_quality_score, generation_eligibility, generation_reason, artifact_ready_at, auto_generated_at, resolution_status, resolution_confidence, stale_flag

**Target (not yet added):**
- job_url_status
- apply_url_verified
- salary_text
- source_last_seen_at
- source_updated_at
- closed_at

### 5.3 `job_sources` columns

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

### 5.4 Tables

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

Current vs target must stay explicit in implementation work:

- current repo truth: discovery and downstream work may still share the current queue layout
- target design: provider-specific discovery, resolution, analysis, and generation should separate onto clearer queues as the implementation matures

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

Provider notes for the alpha path:

- Adzuna enters this path directly from a page-based fetch loop
- DataForSEO Google Jobs enters this path through `task_post -> bounded polling -> task_get/advanced -> normalize`

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
- Adzuna discovery jobs: eligible only at stricter threshold and sufficient content quality
- DataForSEO Google Jobs discovery jobs: stricter still and not eligible by default unless they clear the higher discovery gate

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
