# JobBot Close-Out Audit — Docs vs Code Alignment

**Date:** 2026-03-16  
**Scope:** Final no-code audit after docs cleanup. Source of truth: real repository only.  
**Goal:** Decide whether the repo is ready to resume feature work.

> Historical snapshot only. This file records a point-in-time audit from 2026-03-16.
> Do not use it as sole evidence that the current branch is stable or fully verified.
> Check `IMPLEMENTATION_STATUS.md` and `KNOWN_ISSUES.md` first.

---

## 1. Cross-Doc Consistency

| Document | Check | Result |
|----------|-------|--------|
| **README** vs **docs/README** | Ingestion paths, endpoints, resolution, ready-to-apply | ✓ Aligned |
| **IMPLEMENTATION_STATUS** vs **ACCEPTANCE_REPORT** | resolve endpoint, job_resolution_attempts, generation gate, ready-to-apply | ✓ Aligned |
| **FOLLOWUP_DISCOVERY** vs others | Resolution implemented; generation gate; ready-to-apply (notes "when implemented" for source_confidence filter) | ✓ Aligned; FOLLOWUP correctly frames source_confidence as future |

At the time of this audit, no contradictions were identified between the listed docs.
That statement does **not** automatically apply to later branches.

---

## 2. Code Alignment

### jobs.py
| Doc claim | Code | Match |
|-----------|------|-------|
| `POST /api/jobs/{id}/resolve` | `@router.post("/{job_id}/resolve")` (L416–447) | ✓ |
| Discovery jobs only; enqueues `resolve_discovery_job` | Checks `source_role != SourceRole.DISCOVERY`; `resolve_discovery_job.delay()` | ✓ |
| `GET /api/jobs/ready-to-apply` | Filters: `RESUME_READY`, `artifact_ready_at`, `user_status=NEW` | ✓ |

### resolution.py
| Doc claim | Code | Match |
|-----------|------|-------|
| Records attempts in `job_resolution_attempts` | `JobResolutionAttempt` created on success/failure (L115, 127, 140, 158, 175, 193, 250) | ✓ |
| Chains to score → classify → ats_match → gate | `(score_jobs.s(...) \| classify_jobs.s() \| ats_match_resume.s() \| evaluate_generation_gate.s()).delay()` (L269–273) | ✓ |
| Discovery-only; fetches canonical when URL maps to G/L/A | `source_role != "discovery"` early exit; `parse_supported_url`; connector fetch | ✓ |

### scrape.py
| Doc claim | Code | Match |
|-----------|------|-------|
| JobSpy sets `source_role=discovery` | `source_role=SourceRole.DISCOVERY.value` (L195) | ✓ |
| JobSpy sets `source_confidence`, `resolution_status=pending` | `source_confidence=_compute_jobspy_source_confidence(...)`; `resolution_status=ResolutionStatus.PENDING.value` (L196–199) | ✓ |
| Chain includes `evaluate_generation_gate` | `(score_jobs.s() \| classify_jobs.s() \| ats_match_resume.s() \| evaluate_generation_gate.s()).delay()` (L317) | ✓ |

### generation.py
| Doc claim | Code | Match |
|-----------|------|-------|
| Evaluates ATS_ANALYZED jobs; queues for eligible | `evaluate_generation_eligibility(job, config)`; `generate_grounded_resume_task.delay()` | ✓ |
| queued=0 when flag off | `gate_config_from_settings` reads `enable_auto_resume_generation` | ✓ |
| Receives `chain_output` with `job_ids` | `chain_output.get("job_ids")` (L41–42) | ✓ |

### core/db/models.py
| Doc claim | Code | Match |
|-----------|------|-------|
| `job_resolution_attempts` table | `JobResolutionAttempt.__tablename__ = "job_resolution_attempts"` (L434) | ✓ |
| Job has `resolution_attempts` relationship | `Job.resolution_attempts` (L319–320) | ✓ |

---

## 3. All Four Paths Chain to Gate (verified)

| Path | File | Chain includes gate |
|------|------|---------------------|
| JobSpy scrape | scrape.py L317 | ✓ |
| Canonical ingest | ingest.py L327, L531 | ✓ |
| Discovery | discovery.py L261 | ✓ |
| Resolution (post-resolve) | resolution.py L269–273 | ✓ |

---

## 4. Non-Blocking Observations

- **discovery.py L294:** Comment says "Chains to score -> classify -> ats_match. No auto-generation in this PR." Code chains to gate. Comment is stale; behavior is correct. Does not affect runtime.
- **ACCEPTANCE_REPORT §4:** Refers to `(score | classify | ats_match | generation_gate)` — shorthand for `evaluate_generation_gate`; no confusion.

---

## 5. Recommendation

### Historical recommendation only

**Rationale:**
- This was the recommendation for the audited snapshot on 2026-03-16.
- Current-branch readiness must be re-evaluated against current code and focused regression suites.

---

## 6. Remaining Contradictions

None were found in the audited snapshot. Re-audit current code before repeating that claim.

---

## 7. Suggested Next Steps

- Use IMPLEMENTATION_PLAN §6 (UI throughput mode) and TODO.md for prioritization.
- When touching discovery pipeline, consider refreshing `discovery.py` L294 comment to include the gate.
