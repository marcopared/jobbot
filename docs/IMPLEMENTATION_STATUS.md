# JobBot Implementation Status (Backend Verification)

**Date:** 2026-03-16  
**Scope:** Core pipeline, state transitions, generation trigger, runs tracking.  
**Note:** Aligns with docs truthfulness cleanup; SPEC, ARCHITECTURE, TODO, docs/README distinguish implemented vs remaining.

## Current-branch caution

This document is useful as a status map, but it is not by itself proof that the current branch is
fully verified. For branch-specific reliability gaps and the minimum regression suites to rerun,
see `KNOWN_ISSUES.md`.

## Implemented / Partial / Aspirational Matrix

| Item | Implemented | Partial | Aspirational |
|------|-------------|---------|--------------|
| **resolve endpoint** | ✓ `POST /api/jobs/{id}/resolve` | | |
| **job_resolution_attempts** | ✓ Table + model; `resolve_discovery_job` records attempts | | |
| **JobSpy source_role** | ✓ Sets `source_role=discovery`, `source_confidence`, `resolution_status=pending` | | |
| **Generation gate** | ✓ All paths chain to gate; JobSpy uses discovery rules; queued=0 when flag off | | |
| **Ready-to-apply** | ✓ `GET /api/jobs/ready-to-apply`; RESUME_READY + artifact_ready_at + user_status=NEW | | |
| **Pipeline status** | ✓ INGESTED→SCORED/REJECTED→CLASSIFIED→ATS_ANALYZED→RESUME_READY | GENERATION_QUEUED not persisted | Target states (DISCOVERED, NORMALIZED, etc.) |
| **Queues** | ✓ default, scrape, ingestion | | Target: discovery, resolution, analysis queues |
| **Skip reasons** | ✓ Disabled-feature worker exits persist terminal `ScrapeRun` state | | Full target state machine still aspirational |
| **Manual generation tracking** | ✓ Manual and auto generation persist `GenerationRun` lifecycle | | |

---

## Summary

| Area | Status |
|------|--------|
| **Worker task chaining** | Implemented; JobSpy scrape path includes generation gate in chain |
| **Pipeline statuses** | Explicit: INGESTED → SCORED/REJECTED → CLASSIFIED → ATS_ANALYZED → (gate) → RESUME_READY |
| **Generation trigger** | Mixed: manual via `POST /api/jobs/{id}/generate-resume`; auto when `ENABLE_AUTO_RESUME_GENERATION=true` |
| **Runs tracking** | Implemented (ScrapeRun, GenerationRun) |
| **Ready-to-apply** | Implemented (`GET /api/jobs/ready-to-apply`) |
| **Resolution** | Implemented (`POST /api/jobs/{id}/resolve`; `job_resolution_attempts`; `resolve_discovery_job` task) |

---

## What is Actually Implemented

| Component | Detail |
|-----------|--------|
| **Ingestion paths** | Greenhouse, Lever, Ashby (canonical); JobSpy (scrape); AGG-1, SERP1 (discovery, feature-flagged); URL ingest |
| **Post-ingestion chain** | score → classify → ats_match → evaluate_generation_gate (all four paths) |
| **State transitions** | `pipeline_status` updated: INGESTED → SCORED/REJECTED → CLASSIFIED → ATS_ANALYZED |
| **Generation gate** | Eligibility rules for canonical, URL ingest, AGG-1, SERP; queued=0 when `ENABLE_AUTO_RESUME_GENERATION=false` |
| **Manual generation** | `POST /api/jobs/{id}/generate-resume` enforces ATS_ANALYZED prerequisite |
| **Artifact retrieval** | `GET /api/artifacts/{id}/download`, `GET /api/artifacts/{id}/preview`; local + GCS providers |
| **Ready-to-apply feed** | `GET /api/jobs/ready-to-apply` returns artifact-ready jobs with apply URLs |
| **Runs** | `ScrapeRun` for ingestion; `GenerationRun` for resume generation |
| **Resolution** | `POST /api/jobs/{id}/resolve`; `job_resolution_attempts` table; `resolve_discovery_job` task records attempts |
| **JobSpy discovery metadata** | Scrape path sets `source_role=discovery`, `source_confidence` (heuristic), `resolution_status=pending`; gate uses discovery rules (stricter threshold + content quality) |

---

## Pipeline status writes (audit)

| pipeline_status | Written by | File |
|-----------------|------------|------|
| INGESTED | scrape_jobspy, run_discovery_persist, ingest_canonical, ingest_url | scrape.py, discovery.py, ingest.py |
| SCORED | score_jobs (when score ≥ threshold) | score.py |
| REJECTED | score_jobs (when score < threshold) | score.py |
| CLASSIFIED | classify_jobs | classify.py |
| ATS_ANALYZED | ats_match_resume | ats_match.py |
| RESUME_READY | generate_grounded_resume (after artifact ready) | grounded_generator.py |

Generation gate does not write pipeline_status; it queues generation. GENERATION_QUEUED is not persisted. Transitions are consistent: INGESTED → SCORED/REJECTED → CLASSIFIED → ATS_ANALYZED → RESUME_READY.

---

## What is Partial

| Component | Detail |
|-----------|--------|
| **Pipeline status** | `RESUME_READY` set when artifact is ready; `GENERATION_QUEUED` not persisted as explicit status |
| **Target pipeline states (SPEC §11)** | Full set (DISCOVERED, NORMALIZED, DEDUPED, RESOLUTION_PENDING, etc.) not implemented; current model uses INGESTED, SCORED, REJECTED, CLASSIFIED, ATS_ANALYZED, RESUME_READY |
| **Seed script** | Exercises only JobSpy path; discovery and URL ingest require manual verification |
| **Readiness confidence** | Focused regression suites exist, but provider-backed end-to-end verification is still partly manual |

---

## What is Only Documented (aspirational)

| Item | Reference |
|------|-----------|
| **Target pipeline states** | SPEC §11, ARCH §7 |
| **Target queue model** | discovery, resolution, analysis, generation queues (ARCH §8.2) — current: default, scrape, ingestion |
| **Expanded persisted state machine** | SPEC §11 target states like GENERATION_QUEUED / FAILED / SKIPPED as first-class pipeline states |

---

## Known issues / reliability gaps

- Historical acceptance/closeout docs should not be used as the sole basis for current-branch readiness claims.
- The regression suites cover specific correctness invariants, not full provider/runtime reliability.
- Real-provider verification, ready-to-apply throughput, and PDF generation still require local/manual checks when those systems change.
- There is still no expanded persisted pipeline state machine beyond the implemented statuses listed above.

---

## Resume Generation: Manual vs Automated

- **Manual:** `POST /api/jobs/{id}/generate-resume`; available when job is ATS_ANALYZED or RESUME_READY; persists a `GenerationRun`.
- **Automated:** When `ENABLE_AUTO_RESUME_GENERATION=true`, `evaluate_generation_gate` queues `generate_grounded_resume_task` for eligible jobs.
- **Default:** `ENABLE_AUTO_RESUME_GENERATION=false` → manual only.
- **Eligibility:** Canonical/URL ingest at score ≥ threshold; AGG-1 at stricter threshold + content quality; SERP not eligible by default.

---

## Implemented vs still aspirational

**Implemented:** JobSpy discovery metadata (source_role, source_confidence, resolution_status); generation gate behavior for JobSpy (explicit, tested); pipeline_status writes audited and consistent; INGESTED→SCORED/REJECTED→CLASSIFIED→ATS_ANALYZED→RESUME_READY flow; resolution endpoint and job_resolution_attempts.

**Still aspirational (docs-only):** Full target pipeline states (DISCOVERED, NORMALIZED, DEDUPED, RESOLUTION_PENDING, etc.); GENERATION_QUEUED as persisted status; target queue model (discovery, resolution, analysis queues); SKIPPED with explicit reason.

Do not implement the full aspirational state machine unless genuinely required. Prefer comments, docs, and tests over introducing unnecessary state complexity.

---

## Verification Notes

1. **JobSpy chain:** `scrape_jobspy` chains `score → classify → ats_match → evaluate_generation_gate`; gate receives job_ids from ats_match result.
2. **Test:** `test_full_chain_as_scrape_runs_end_to_end` verifies full Celery chain (score→classify→ats→gate) runs end-to-end.
3. **JobSpy discovery metadata:** Scrape path sets source_role, source_confidence, resolution_status; gate applies discovery rules (stricter threshold + content quality).
