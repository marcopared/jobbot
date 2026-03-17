# JobBot Product Specification

## Document purpose

This document defines the **product contract** for JobBot. It describes the current system (source of truth: the real repository), remaining gaps, and non-goals.

It supersedes older v1 documentation. Treat this document as the product source of truth for implementation work.

## 1. Executive summary

JobBot is a personal job discovery and preparation engine.

Its purpose is to:
- ingest jobs from multiple sources
- normalize and deduplicate them
- score and rank them against the user's profile
- run ATS-oriented analysis
- automatically generate tailored resume artifacts for eligible jobs
- present a ready-to-apply queue where the user can download the resume and open the job application page

JobBot stops at artifact-ready plus outbound application link. The user still applies manually.

## 2. Product goals

JobBot optimizes for:
- broader ingestion coverage
- stable and realistic integrations
- high-quality canonical job data when possible
- automated throughput from ingestion to artifact-ready
- minimal operator intervention in the happy path
- preservation of the final manual-apply boundary

## 3. Non-goals

The following remain out of scope:
- automated application submission
- browser automation for application workflows
- interview scheduling or CRM-style follow-up
- arbitrary generic web crawling as a primary ingestion strategy
- treating SERP/search results as canonical truth by default

## 4. Implemented vs remaining

Source of truth: the real repository.

### Implemented now
- **Canonical ATS:** Greenhouse, Lever, Ashby via `POST /api/jobs/run-ingestion`
- **Discovery:** JobSpy (scrape); AGG-1 and SERP1 (feature-flagged: `ENABLE_AGG1_DISCOVERY`, `ENABLE_SERP1_DISCOVERY`)
- **URL ingest:** supported Greenhouse/Lever/Ashby job URLs via `POST /api/jobs/ingest-url` (feature-flagged: `URL_INGEST_ENABLED`)
- **Processing:** score → classify → ATS analysis → generation gate; auto-generation when `ENABLE_AUTO_RESUME_GENERATION=true`
- **Ready-to-apply:** `GET /api/jobs/ready-to-apply` feed; UI has ReadyToApplyPage
- **Manual apply:** user downloads artifact and opens job URL externally; no browser automation

### Partially implemented
- UI throughput mode: ready-to-apply default view and URL ingest entry point exist but may need polish

### Still remaining
- Full target pipeline states (DISCOVERED, NORMALIZED, DEDUPED, etc.); current model uses INGESTED, SCORED, REJECTED, CLASSIFIED, ATS_ANALYZED, RESUME_READY
- SKIPPED state with explicit reason (e.g. low score, duplicate absorbed)

## 5. Core product rule

**Discover broadly, generate narrowly.**

JobBot should ingest from as many useful lanes as practical, but it should only generate artifacts for jobs that meet explicit quality and eligibility thresholds.

Broad discovery volume is good.
Blind artifact generation for the full corpus is bad.

## 6. Source model

### 6.1 Canonical ATS sources
These are the highest-confidence sources for job content and apply flow.

- Greenhouse (implemented)
- Lever (implemented)
- Ashby (implemented)

Expected properties:
- stable or semi-stable external identifiers
- full descriptions or rich HTML/plain content
- explicit apply URLs or hosted posting URLs
- cleaner location/workplace-type metadata
- better fit for ATS analysis and resume generation

These are **not** broad discovery APIs. They are curated per-company sources.

### 6.2 Broad discovery sources
These maximize coverage across many companies.

- AGG-1 = Adzuna (planned provider for this implementation wave)
- JobSpy (existing scrape lane)
- SERP1 = DataForSEO Google Jobs (planned provider for this implementation wave; higher-risk lane)

Expected properties:
- query-driven retrieval
- variable field completeness
- lower trust than canonical ATS sources
- suitable for discovery, filtering, and ranking
- may require later canonical enrichment when possible

### 6.3 Direct URL ingest
The user should be able to paste a supported job URL and force deterministic ingestion.

First supported providers:
- Greenhouse
- Lever
- Ashby

This is the fastest path from a discovered posting to a tailored resume.

## 7. User-facing workflow

### 7.1 Broad discovery flow
1. JobBot ingests jobs from discovery and canonical sources.
2. Jobs are normalized and deduplicated.
3. JobBot attempts canonical enrichment when possible.
4. Jobs are scored and analyzed.
5. Eligible jobs get an automatically generated tailored resume.
6. The user opens the ready-to-apply queue.
7. The user downloads the artifact and clicks the job posting to apply manually.

### 7.2 Direct URL flow
1. User pastes a supported ATS job URL.
2. JobBot detects the provider.
3. JobBot ingests the job via the provider-specific connector.
4. The same downstream scoring/analysis/generation pipeline runs.
5. The job appears in the ready-to-apply queue if it passes eligibility.

## 8. Primary product surfaces

### 8.1 Ready to Apply
Default operational view.
Contains jobs where:
- artifact is ready
- apply URL is present
- job is not stale
- user has not marked it as applied/archived

### 8.2 Promising / In Progress
Jobs that have cleared ingestion and scoring but are not yet artifact-ready.

### 8.3 Needs Resolution
Discovery jobs that look promising but could not yet be resolved to a higher-confidence canonical record.

### 8.4 All Jobs / Debug
Full corpus view with provenance, source confidence, and diagnostic information.

## 9. Alpha discovery provider contract

This section freezes the provider mapping for the alpha discovery implementation wave.

### 9.1 Provider mapping

- `AGG-1 = Adzuna`
- `SERP1 = DataForSEO Google Jobs`

These names remain the internal lane labels in the product and architecture docs. They are not placeholder abstractions for this wave.

### 9.2 Source-role expectations

- Adzuna is a `discovery` source with `medium` confidence.
- DataForSEO Google Jobs is a `discovery` source with lower confidence than Adzuna.
- Canonical ATS sources and URL-ingest remain higher-confidence than either discovery provider.
- DataForSEO Google Jobs must never be treated as canonical truth.

### 9.3 Generation policy for alpha discovery providers

- canonical ATS and URL-ingest remain the preferred path for scoring, ATS analysis, and generation
- Adzuna discovery jobs may auto-generate only under stricter thresholds than canonical ATS and URL-ingest jobs
- DataForSEO Google Jobs discovery jobs require the strictest thresholds in the system
- DataForSEO Google Jobs records must never be used as canonical truth during merge, resolution, or generation decisions
- unresolved lower-confidence discovery records must not flood artifact generation

## 10. Generation policy

Resume generation must be gated.

A job should only auto-generate if:
- score is above threshold
- ATS analysis completed successfully
- content quality is sufficient
- apply URL is present or otherwise verified usable
- source confidence is acceptable
- the job is not stale
- an equivalent artifact does not already exist for unchanged content

Default policy:
- canonical ATS records: eligible at moderate threshold
- Adzuna discovery records: eligible only at stricter thresholds than canonical ATS and URL-ingest
- DataForSEO Google Jobs discovery records: eligible only at the strictest discovery thresholds; never canonical and not eligible by default unless they clear the highest discovery gate

## 11. Done tonight

The alpha discovery implementation wave is done when all of the following are true:

- Adzuna real discovery is working
- DataForSEO real Google Jobs discovery is working
- both feed into `score -> classify -> ATS -> generation gate`
- at least one discovery-originated job can become artifact-ready
- ready-to-apply remains the operational output
- manual apply remains the final step

## 12. User workflow states

User workflow remains simple:
- `NEW`
- `SAVED`
- `APPLIED`
- `ARCHIVED`

The user should still explicitly mark when they applied.
The system must not apply on the user's behalf.

## 13. System pipeline states

### Implemented states (current model)
- `INGESTED`
- `SCORED`
- `REJECTED`
- `CLASSIFIED`
- `ATS_ANALYZED`
- `RESUME_READY`

### Target states (not yet implemented)
- `DISCOVERED`, `NORMALIZED`, `DEDUPED`
- `RESOLUTION_PENDING`, `RESOLVED_CANONICAL`, `RESOLVED_DISCOVERY_ONLY`
- `GENERATION_QUEUED` (persisted)
- `FAILED`, `SKIPPED` (with explicit reason)

`SKIPPED` should always include a reason, such as:
- low score
- low content quality
- missing apply URL
- unresolved low-confidence discovery result
- stale job
- duplicate absorbed

## 14. Product boundaries for the coding agents

The following requirements are mandatory:
- keep manual apply as the final human step
- do not add browser automation
- do not add auto-apply
- do not make generic crawling a core dependency in the first implementation wave
- do not let discovery-only low-confidence jobs flood artifact generation

## 15. Delivery priorities

Priority order (see `IMPLEMENTATION_PLAN.md` for PR boundaries). Stabilization first; no new scope in docs-only PRs.

1. Documentation refresh (docs-only stabilization)
2. DB and model foundation
3. Official ATS expansion (Lever, Ashby, URL ingest) — implemented
4. Broad discovery lane (AGG-1 first; SERP optional, feature-flagged) — implemented
5. Automation funnel and generation gate — implemented
6. UI throughput mode (ready-to-apply default) — partially implemented

## 16. Acceptance criteria (implemented)

The following criteria are satisfied:
- JobBot can ingest from Greenhouse, Lever, and Ashby through a generalized connector flow
- JobBot can ingest a supported job URL directly
- JobBot can ingest discovery results from AGG-1
- jobs can be marked as discovery vs canonical
- jobs flow automatically from ingestion through artifact-ready when eligible
- the user can work primarily from a ready-to-apply queue
- manual application remains the final step
