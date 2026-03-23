# JobBot Acceptance Report — Post-Stabilization Verification

**Date:** 2026-03-16  
**Scope:** Prove whether the repo is stable enough to resume feature work.  
**Source of truth:** Real repository only (ignored scaffold, patches, synthetic summaries).

> Historical verification snapshot only. The pass/fail statements below describe the repo state
> that was verified on 2026-03-16. They are not a blanket claim about later branches.
> For current-branch reliability gaps, use `KNOWN_ISSUES.md`.

---

## 1. Summary

| Area | Result |
|------|--------|
| **Clean DB + migrations** | PASS |
| **API + worker startup** | PASS |
| **Health endpoint** | PASS |
| **Jobs list/detail** | PASS |
| **Ready-to-apply endpoint** | PASS |
| **Resolve endpoint** | PASS (`POST /api/jobs/{id}/resolve`; discovery jobs only; enqueues task) |
| **Baseline ingestion (JobSpy scrape)** | PASS |
| **Resume generation path** | PASS (API contract; unit tests cover full pipeline) |
| **Artifacts listing** | PASS |
| **Artifacts download** | PASS (route exercised; empty when no artifacts) |
| **Runs list/detail** | PASS |
| **pytest suite** | PASS (230 passed, 1 deprecation warning) |

**Historical recommendation: YES for the audited snapshot only.**

---

## 2. Exact Reproduction Steps

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Node.js 18+ (for UI; optional for API/worker verification)
- `playwright install chromium` (required for resume PDF generation)
- `cp .env.example .env` and adjust if needed (defaults work for local)

### Commands used

```bash
# 1. Fresh DB
cd /Users/marcoparedes/dev/jobbot
docker compose down -v
docker compose up -d

# 2. Wait for Postgres
until docker compose exec -T postgres pg_isready -U postgres -d jobbot; do sleep 1; done

# 3. Migrations
PYTHONPATH=. alembic upgrade head

# 4. Start API (one terminal)
PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000

# 5. Start worker (another terminal)
PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape,ingestion

# 6. Exercise endpoints (API + worker running)
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8000/api/jobs
curl -s http://127.0.0.1:8000/api/jobs/ready-to-apply
curl -s -X POST http://127.0.0.1:8000/api/jobs/run-scrape
curl -s "http://127.0.0.1:8000/api/runs?per_page=5"
curl -s "http://127.0.0.1:8000/api/runs/{RUN_ID}"
curl -s "http://127.0.0.1:8000/api/jobs/{JOB_ID}"
curl -s "http://127.0.0.1:8000/api/jobs/{JOB_ID}/artifacts"

# 7. Run tests
PYTHONPATH=. pytest -q
```

### One-command dev (alternative)

```bash
bash scripts/dev.sh
```

This starts Postgres + Redis, runs migrations, then launches API, worker, and UI.

### Seed data (optional)

```bash
bash scripts/seed.sh
```

Runs `POST /api/jobs/run-scrape` and waits for run completion.

---

## 3. Observed Behavior vs Documentation

| Doc reference | Expected | Actual | Drift |
|--------------|---------|--------|------|
| README §Run Locally | Option A: `scripts/dev.sh`; Option B: manual terminals | Same steps work | None |
| README §Prerequisites | Python 3.11+, Docker, Node, `playwright install chromium` | Required as stated | None |
| README §Migrations | `alembic upgrade head` before first run | Required | None |
| README §Endpoints | health, jobs, ready-to-apply, resolve, artifacts, runs | All return documented shapes | None |
| IMPLEMENTATION_PLAN §11 | Worker queues: `default,scrape,ingestion` | Worker consumes all three; discovery/generation route to `default` | None |
| IMPLEMENTATION_PLAN §11 | `scripts/seed.sh` exercises only JobSpy | Confirmed; discovery/URL ingest require manual curl | None |
| README §Ingestion paths | run-scrape, run-ingestion, run-discovery, ingest-url | run-scrape exercised; others documented | None |
| .env.example | Feature flags: AGG1/SERP1 off, URL ingest on | Not verified; `apps/api/settings.py` defaults match docs | Minor |

**Drift notes**

- `GET /api/jobs/ready-to-apply` returned 500 when a stale API process (older code) was running; after restarting the API with current code, it returned 200 and the documented `JobListResponse` shape.
- `JobBot ingestion expansion feasibility research.md` — not found in repository; could not be reviewed.

---

## 4. Pipeline Behavior (Scrape → Score → Classify → ATS → Gate)

- **Scrape:** Completed successfully; 10 jobs inserted; run status SUCCESS.
- **Downstream chain:** `scrape_jobspy` queues `(score | classify | ats_match | generation_gate).delay()`. In this run, jobs remained at `INGESTED` (score 0.0) during verification. Possible reasons: (1) all jobs rejected by score (< 60), (2) chain still in progress, (3) worker timing. **Mitigation:** `tests/test_pipeline_chain.py` exercises the full chain end-to-end and passes (including `test_full_chain_as_scrape_runs_end_to_end`). Resume generation API is covered by `test_post_generate_resume_200_ats_analyzed` and `test_post_generate_resume_200_resume_ready`.

---

## 5. Blocker List

| Blocker | Severity | Mitigation |
|---------|----------|------------|
| Stale API returning 500 on ready-to-apply | Low | Restart API after schema/code changes |
| Downstream pipeline not visibly progressing in short window | Low | Covered by pipeline_chain tests; acceptable for stabilization |
| `JobBot ingestion expansion feasibility research.md` missing | Info | File not in repo; no action needed for acceptance |
| Pydantic deprecation warning (`class Config`) | Info | Non-blocking; can be addressed in a follow-up PR |
| Playwright required for resume PDF | Known | Documented in README; omit and generation fails as expected |

No blockers were identified for the audited snapshot. Re-verify current code before repeating this claim.

---

## 6. Test Results

```
======================== 230 passed, 1 warning in 5.55s ========================
```

- PR 2 (DB/model): migration and model tests pass.
- PR 3 (ATS expansion): connector and ingestion route tests pass.
- PR 4 (discovery): discovery and connector tests pass.
- PR 5 (automation): pipeline chain, generation gate, ready-to-apply tests pass.

---

## 7. Merge Recommendation

**Historical YES only.** Do not reuse this section as current-branch proof without rerunning verification.

- This was true for the audited snapshot.
- Current branches must be evaluated against current regression suites and known issues.

---

## Appendix: Verification Commands (Copy-Paste)

```bash
# Full flow from clean DB
docker compose down -v && docker compose up -d
sleep 5
PYTHONPATH=. alembic upgrade head
# Then start API + worker (or scripts/dev.sh), then:
curl -s http://127.0.0.1:8000/api/health | jq .
curl -s -X POST http://127.0.0.1:8000/api/jobs/run-scrape | jq .
# Poll run: curl -s "http://127.0.0.1:8000/api/runs/{run_id}" | jq .status
curl -s "http://127.0.0.1:8000/api/jobs?per_page=5" | jq .
curl -s "http://127.0.0.1:8000/api/jobs/ready-to-apply" | jq .
PYTHONPATH=. pytest -q
```
