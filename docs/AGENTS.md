# AGENTS.md — JobBot Coding Agent Instructions

This is the canonical instruction layer for coding agents working in this repo.
Follow current implemented behavior over aspirational descriptions when they diverge.

## Project overview

JobBot is a local-first job discovery and decision-support tool. It ingests jobs from multiple
sources, scores and classifies them, runs ATS analysis, generates tailored resume artifacts for
eligible jobs, and surfaces a ready-to-apply queue. The final application step is always manual.

**Implemented ingestion lanes:**
- Canonical ATS: Greenhouse, Lever, Ashby — `POST /api/jobs/run-ingestion`
- Discovery scrape: JobSpy — `POST /api/jobs/run-scrape`
- Broad discovery: AGG-1 (Adzuna), SERP1 (DataForSEO Google Jobs) — `POST /api/jobs/run-discovery` (both feature-flagged)
- URL ingest: supported ATS URLs — `POST /api/jobs/ingest-url` (feature-flagged)

**Implemented pipeline:** INGESTED → SCORED/REJECTED → CLASSIFIED → ATS_ANALYZED → RESUME_READY

**Celery queues (current):** `default`, `scrape`, `ingestion`

**Source confidence order:** canonical ATS > Adzuna (AGG-1) > DataForSEO (SERP1)

---

## Setup

```bash
cp .env.example .env
pip install -r requirements.txt
playwright install chromium
alembic upgrade head
cd ui && npm install && cd ..
```

## Run

```bash
# Option A — all-in-one
bash scripts/dev.sh

# Option B — manual terminals
docker compose up -d
alembic upgrade head
PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000
PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape,ingestion
cd ui && npm run dev -- --host 127.0.0.1 --port 5173
```

## Verify

```bash
# Full test suite
pytest

# Focused — run only tests touching files you changed
pytest <path/to/relevant/tests>

# UI build check
cd ui && npm run build
```

---

## Task routing

| Question | Go to |
|---|---|
| Product behavior, goals, non-goals | `docs/SPEC.md` |
| System design, data flow, queues, APIs | `docs/ARCHITECTURE.md` |
| Current implemented vs aspirational | `docs/README.md` + `docs/IMPLEMENTATION_STATUS.md` |
| PR boundaries, merge order, sequencing | `docs/IMPLEMENTATION_PLAN.md` |
| Agent operating rules and escalation | `docs/CODING_AGENT_GUIDE.md` |
| Backlog and milestones | `docs/TODO.md` *(load only when needed)* |
| Adzuna connector/provider work | `docs/swagger-specs/adzuna swagger spec.json` *(load only when working on AGG-1)* |
| DataForSEO connector/provider work | `docs/swagger-specs/dataforseo openapi spec.yaml` *(load only when working on SERP1)* |

---

## Hard product boundaries — never violate

- **Manual apply is the final step.** No automated application submission.
- **No browser automation for application flows.**
- **Discovery sources are not canonical truth by default.** Do not let AGG-1 or SERP1 drive artifact generation without eligibility rules.
- **SERP1 (DataForSEO) stays feature-flagged and lower-confidence.** Never treat as canonical.
- **No generic arbitrary crawling** as a first-wave requirement.

---

## Prohibited patterns

- Treating discovery records as canonical during merge/normalization
- Collapsing source roles (canonical / discovery / direct URL) — keep them distinct
- Adding a schema migration for convenience; prefer `raw_payload` for provider-specific fields
- Mixing provider work, verification, and UI work in a single PR
- Starting UI polish before backend verification is green
- Auto-applying or adding browser automation under any name
- Writing against scaffold, synthetic summaries, or old aspirational docs instead of the real repo

---

## PR discipline

Keep PRs small and focused. Each PR must have:
- One clear purpose
- An explicit out-of-scope statement
- Focused tests for touched code paths
- No speculative extra scope

Preferred sequencing for provider/discovery work:
1. Provider PR (one provider at a time)
2. Verification PR after provider PRs are green
3. UI work only after backend is verified

---

## Escalation — stop and ask when

- A required provider field cannot fit the current schema without a migration
- A route contract change would break multiple existing consumers
- Provider normalization cannot fit the confidence model without a product decision
- DataForSEO cannot be implemented cleanly within the bounded synchronous task model

---

## Completion checklist

Before marking work done, confirm:
- [ ] `pytest` passes (or focused paths for touched areas)
- [ ] `cd ui && npm run build` passes (if UI was touched)
- [ ] No new browser automation or auto-apply code introduced
- [ ] Source roles remain distinct; no discovery-as-canonical leakage
- [ ] SERP1 remains feature-flagged
- [ ] Migration added only if truly required for correctness (not convenience)
- [ ] PR has explicit out-of-scope statement
