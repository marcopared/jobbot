# Documentation Corrections — Truthfulness Update

**Date:** 2026-03-16  
**Scope:** Docs-only PR; no code changes.  
**Goal:** Align all docs with current repository state.

## Stale statements corrected

- **POST /api/jobs/{id}/resolve** — Previously documented as "not implemented"; corrected to implemented in docs/README.md, docs/SPEC.md, docs/ARCHITECTURE.md, docs/IMPLEMENTATION_STATUS.md, docs/FOLLOWUP_DISCOVERY.md, docs/CODING_AGENT_GUIDE.md. Added to root README Useful endpoints table.

- **job_resolution_attempts table** — Previously documented as "not implemented"; corrected to implemented in docs/README.md, docs/SPEC.md, docs/ARCHITECTURE.md, docs/IMPLEMENTATION_STATUS.md, docs/FOLLOWUP_DISCOVERY.md. ARCHITECTURE §5.3 now lists it under "Implemented (migration 004)".

- **Generation gate for discovery** — FOLLOWUP_DISCOVERY.md previously said "PR 5 must implement"; corrected to "Implemented (PR 5)".

- **GET /api/jobs/ready-to-apply** — FOLLOWUP_PR3.md previously said "not yet implemented"; corrected to implemented.

- **Current vs target queue/state model** — docs/README.md and docs/ARCHITECTURE.md now explicitly separate:
  - Current queues: default, scrape, ingestion
  - Target queues: discovery, resolution, analysis, generation, maintenance
  - Current pipeline states: INGESTED, SCORED, REJECTED, CLASSIFIED, ATS_ANALYZED, RESUME_READY
  - Target pipeline states: DISCOVERED, NORMALIZED, DEDUPED, etc.

- **ARCHITECTURE §5.1 jobs columns** — Previously framed all columns as "Target additions"; split into "Implemented (migration 004)" and "Target (not yet added)".

- **ARCHITECTURE §5.3 tables** — Previously framed job_resolution_attempts and generation_runs as "to add"; corrected to "Implemented (migration 004)".

- **ARCHITECTURE §7 pipeline states** — Added §7.0 "Current pipeline states (implemented)" distinct from §7.1 "Target pipeline states (aspirational)".

- **IMPLEMENTATION_STATUS "What is Only Documented"** — Removed job_resolution_attempts from aspirational; removed from "Still aspirational" paragraph.

- **Non-goals** — Kept explicit across docs: no browser automation, no auto-apply; manual apply remains final step.
