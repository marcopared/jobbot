# JobBot — V1 Implementation Tasks

> **How to use this with Cursor Agent**:
>
> 1. Open Cursor Agent / Composer.
> 2. Say: `"Implement TASK-01 only. Read SPEC.md and ARCHITECTURE.md for context. Follow the acceptance checks. Run commands. Fix until green. Stop."`
> 3. Wait for all acceptance checks to pass.
> 4. Say: `"Proceed to TASK-02."`
> 5. Repeat until done.
>
> **NEVER ask Cursor to implement all tasks at once.**

---

## TASK-01 — Project Scaffold + Docker + Health Endpoint

### Scope

Create the full folder structure, configuration files, and a minimal running
FastAPI app with Docker infrastructure.

### Files to Create

- `jobbot/` root directory
- `requirements.txt` — all Python dependencies
- `.env.example` — copy of env vars from SPEC.md §6
- `.env` — copy of `.env.example` (for local dev)
- `.gitignore` — Python, Node, env, storage, profiles
- `docker-compose.yml` — Postgres + Redis (see SPEC.md §16)
- `apps/__init__.py`
- `apps/api/__init__.py`
- `apps/api/main.py` — FastAPI app with `/api/health`
- `apps/api/settings.py` — Pydantic Settings reading `.env`
- `apps/api/deps.py` — placeholder
- `core/__init__.py`
- `storage/artifacts/.gitkeep`
- `storage/profiles/.gitkeep`
- `scripts/dev.sh`
- `README.md` — setup instructions

### Requirements.txt Contents

```
fastapi>=0.109.0
uvicorn[standard]>=0.25.0
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
psycopg2-binary>=2.9.0
alembic>=1.13.0
celery[redis]>=5.3.0
redis>=5.0.0
python-jobspy>=1.1.0
pdfplumber>=0.10.0
playwright>=1.40.0
httpx>=0.26.0
python-dotenv>=1.0.0
pydantic-settings>=2.1.0
```

### Docker Compose

Use SPEC.md §16 exactly. Postgres 16 + Redis 7 with healthchecks.

### Settings Class

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_env: str = "dev"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jobbot"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/jobbot"
    redis_url: str = "redis://localhost:6379/0"
    artifact_dir: str = "./storage/artifacts"
    profile_dir: str = "./storage/profiles"
    ui_base_url: str = "http://localhost:5173"
    # ... all other env vars from SPEC.md §6

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

### Health Endpoint

```python
@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

### Acceptance Checks

```bash
# 1. Start Docker
cd jobbot && docker compose up -d

# 2. Verify services
docker compose ps  # postgres and redis should be healthy

# 3. Start API
uvicorn apps.api.main:app --reload --port 8000

# 4. Test health
curl http://localhost:8000/api/health
# Expected: {"status":"ok"}
```

**STOP after all checks pass.**

### Completion Notes (2026-03-03)

- Status: DONE
- What changed:
  - Added `jobbot/core/resumes/manager.py` with `prepare_resume()` (tailor attempt + fallback copy + artifact DB record).
  - Added `jobbot/apps/worker/tasks/resume.py` task and wired `jobbot/apps/worker/tasks/apply.py` to create an application + prepare resume artifact.
  - Added `jobbot/apps/api/routes/applications.py` and `jobbot/apps/api/routes/artifacts.py`.
  - Mounted applications/artifacts routers in `jobbot/apps/api/main.py`.
  - Added HEAD support on artifact endpoints so `curl -I` returns 200.
- Commands run:
  - `docker compose up -d && docker compose ps`
  - `PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000`
  - `PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape,apply`
  - `echo "test resume content" > storage/base_resume.pdf`
  - `curl -X POST http://127.0.0.1:8000/api/jobs/$JOB_ID/queue-apply`
  - `curl http://127.0.0.1:8000/api/applications?job_id=$JOB_ID`
  - `ls storage/artifacts/$JOB_ID`
  - `curl -I http://127.0.0.1:8000/api/artifacts/$ARTIFACT_ID/download`

---

## TASK-02 — Database Models + Auto-Create Tables

### Scope

Implement all SQLAlchemy models from SPEC.md §7 and auto-create tables on
API startup. No Alembic migrations yet.

### Files to Create/Edit

- `core/db/__init__.py`
- `core/db/base.py` — SQLAlchemy `DeclarativeBase`
- `core/db/models.py` — All 6 models: Company, Job, ScrapeRun, Application, Artifact, Intervention
- `core/db/session.py` — Async engine factory, session factory, `get_db` dependency
- `apps/api/deps.py` — Export `get_db` and `get_settings`
- `apps/api/main.py` — Add lifespan handler that creates all tables

### Model Requirements

- Use `mapped_column` with type annotations (SQLAlchemy 2.0 style).
- All UUIDs use `uuid.uuid4` as default.
- All `created_at` fields use `func.now()` server default.
- All `updated_at` fields use `func.now()` with `onupdate=func.now()`.
- Enums: define as Python `str, Enum` classes (see SPEC.md §7.1). Store as TEXT in DB.
- JSONB columns use `sqlalchemy.dialects.postgresql.JSONB`.
- Foreign keys with proper `relationship()` definitions.
- Include `__tablename__` on every model.

### Acceptance Checks

```bash
# 1. Docker running
docker compose up -d

# 2. Start API (tables auto-create)
uvicorn apps.api.main:app --reload --port 8000

# 3. Verify tables exist
docker exec -it jobbot-postgres-1 psql -U postgres -d jobbot -c "\dt"
# Expected: companies, jobs, scrape_runs, applications, artifacts, interventions

# 4. Verify columns
docker exec -it jobbot-postgres-1 psql -U postgres -d jobbot -c "\d jobs"
# Expected: all columns from SPEC.md §7.2
```

**STOP after all checks pass.**

### Completion Notes (2026-03-03)

- Status: DONE
- What changed:
  - Added browser automation package and runner:
    - `jobbot/apps/browser/runner.py`
    - `jobbot/apps/browser/detectors.py`
    - `jobbot/apps/browser/__init__.py`
  - Added ATS handler skeletons:
    - `jobbot/apps/browser/ats/base.py`
    - `jobbot/apps/browser/ats/greenhouse.py`
    - `jobbot/apps/browser/ats/lever.py`
    - `jobbot/apps/browser/ats/ashby.py`
    - `jobbot/apps/browser/ats/workday.py`
    - `jobbot/apps/browser/ats/yc.py`
    - `jobbot/apps/browser/ats/__init__.py`
  - Updated `jobbot/apps/worker/tasks/apply.py` to delegate to browser runner.
  - Runner now creates an application, prepares resume, opens Playwright browser, detects blocks, captures screenshot/html artifacts, creates intervention records, and updates statuses safely.
- Commands run:
  - `playwright install chromium`
  - `PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000`
  - `PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape,apply`
  - `curl -X POST http://127.0.0.1:8000/api/jobs/$JOB_ID/queue-apply`
  - `curl http://127.0.0.1:8000/api/applications?job_id=$JOB_ID`
  - `ls storage/artifacts/$JOB_ID`

---

## TASK-03 — JobSpy Scraper + Scrape Task + Run Logging

### Scope

Implement the JobSpy scraper wrapper, the Celery scrape task, and the
`POST /api/jobs/run-scrape` endpoint.

### Files to Create/Edit

- `core/scraping/__init__.py`
- `core/scraping/base.py` — `BaseScraper`, `ScrapeParams`, `ScrapeResult`, `NormalizedJob` (see SPEC.md §9.1)
- `core/scraping/jobspy_scraper.py` — JobSpy implementation (see SPEC.md §9.2)
- `apps/worker/__init__.py`
- `apps/worker/celery_app.py` — Celery app instance
- `apps/worker/tasks/__init__.py`
- `apps/worker/tasks/scrape.py` — `scrape_jobspy` task
- `apps/api/routes/__init__.py`
- `apps/api/routes/jobs.py` — `POST /api/jobs/run-scrape` + `GET /api/jobs`
- `apps/api/main.py` — Mount jobs router

### Celery Configuration

```python
celery_app = Celery("jobbot")
celery_app.config_from_object({
    "broker_url": settings.redis_url,
    "result_backend": settings.redis_url,
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "task_routes": {
        "apps.worker.tasks.scrape.*": {"queue": "scrape"},
        "apps.worker.tasks.apply.*": {"queue": "apply"},
        "apps.worker.tasks.score.*": {"queue": "default"},
        "apps.worker.tasks.notify.*": {"queue": "default"},
    },
})
```

### Scraper Logic

1. Call `jobspy.scrape_jobs()` with params from settings.
2. Iterate DataFrame rows → create `NormalizedJob` objects.
3. For each job: compute `dedup_hash` (see SPEC.md §9.3).
4. Upsert company by name (find existing or create new).
5. Detect ATS type from URL (see SPEC.md §9.4).
6. Insert job with `ON CONFLICT (dedup_hash) DO NOTHING`.
7. Track stats: fetched, inserted, duplicates, errors.
8. Update `scrape_run` record.

### Important

- Celery tasks use **synchronous** DB sessions (psycopg2), not async.
  The Celery worker cannot use asyncpg. Use `database_url_sync` for workers.
- Create a `get_sync_session()` factory for worker tasks.

### Acceptance Checks

```bash
# 1. Docker running
docker compose up -d

# 2. Start API
uvicorn apps.api.main:app --reload --port 8000

# 3. Start Celery worker
celery -A apps.worker.celery_app worker -l info -Q default,scrape,apply

# 4. Trigger scrape
curl -X POST http://localhost:8000/api/jobs/run-scrape
# Expected: {"run_id": "...", "status": "RUNNING"}

# 5. Wait ~30 seconds, then check jobs
curl http://localhost:8000/api/jobs | python -m json.tool
# Expected: {"items": [...], "total": N} where N > 0

# 6. Check scrape run
docker exec -it jobbot-postgres-1 psql -U postgres -d jobbot -c "SELECT source, status, stats_json FROM scrape_runs ORDER BY started_at DESC LIMIT 1;"
# Expected: status=SUCCESS, stats_json shows counts
```

**STOP after all checks pass.**

### Completion Notes (2026-03-03)

- Status: DONE
- What changed:
  - Added notification layer:
    - `jobbot/core/notify/base.py`
    - `jobbot/core/notify/pushover.py`
    - `jobbot/core/notify/ntfy.py`
    - `jobbot/core/notify/__init__.py`
  - Added worker notification task:
    - `jobbot/apps/worker/tasks/notify.py`
    - exported in `jobbot/apps/worker/tasks/__init__.py`
  - Added intervention API:
    - `jobbot/apps/api/routes/interventions.py` (`GET list/detail`, `POST resolve/abort/retry-apply`)
    - mounted in `jobbot/apps/api/main.py`
  - Updated `jobbot/apps/browser/runner.py` to enqueue push notifications on intervention/success/failure paths.
- Commands run:
  - `docker compose up -d && docker compose ps`
  - `PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000`
  - `PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape,apply`
  - `curl -X POST http://127.0.0.1:8000/api/jobs/$JOB_ID/queue-apply`
  - `curl http://127.0.0.1:8000/api/interventions?status=OPEN`
  - `curl -X POST http://127.0.0.1:8000/api/interventions/$INT_ID/resolve -H "Content-Type: application/json" -d '{"notes":"test resolve"}'`
  - `curl -X POST http://127.0.0.1:8000/api/interventions/$INT_ID/retry-apply`

---

## TASK-04 — Scoring Engine + Auto-Score After Scrape

### Scope

Implement rule-based scoring and wire it to run automatically after scraping.

### Files to Create/Edit

- `core/scoring/__init__.py`
- `core/scoring/rules.py` — Scoring rules config (see SPEC.md §10.1)
- `core/scoring/scorer.py` — `score_job()` function (see SPEC.md §10.2)
- `apps/worker/tasks/score.py` — `score_jobs` task
- `apps/worker/tasks/scrape.py` — Chain: after scrape → enqueue `score_jobs`

### Scoring Behavior

- Input: a Job record with `status=NEW`.
- Output: `score_total` (float), `score_breakdown_json` (dict), `status=SCORED`.
- If a job has no description, only title + location scoring applies.
- Score can be negative (penalty keywords). That's fine.

### Acceptance Checks

```bash
# 1. Run a scrape (or use existing data)
curl -X POST http://localhost:8000/api/jobs/run-scrape

# 2. Wait for scoring to complete (~10 seconds after scrape finishes)

# 3. Check jobs have scores
docker exec -it jobbot-postgres-1 psql -U postgres -d jobbot -c \
  "SELECT title, company_name_raw, score_total, status FROM jobs WHERE status='SCORED' ORDER BY score_total DESC LIMIT 5;"
# Expected: jobs with SCORED status and non-zero score_total

# 4. Check breakdown exists
docker exec -it jobbot-postgres-1 psql -U postgres -d jobbot -c \
  "SELECT score_breakdown_json FROM jobs WHERE score_total > 0 LIMIT 1;"
# Expected: JSON object with keys like "title_match", "description_keywords", "location"
```

**STOP after all checks pass.**

### Completion Notes (2026-03-03)

- Status: DONE
- What changed:
  - Added `jobbot/ui/src/pages/InterventionsPage.tsx` with OPEN/RESOLVED/ABORTED tabs, data loading, and single-column card layout.
  - Added `jobbot/ui/src/components/InterventionCard.tsx` with reason badge colors, screenshot preview expand/collapse, Last URL link, and Resolve/Abort/Retry actions.
  - Updated `jobbot/ui/src/App.tsx` to route `/interventions`.
  - Updated `jobbot/ui/src/components/Layout.tsx` to poll OPEN interventions every 15s and show sidebar/mobile badge counts.
  - Updated `jobbot/ui/src/api.ts` with intervention API client methods (`fetchInterventions`, `resolveIntervention`, `abortIntervention`, `retryIntervention`).
- Commands run:
  - `cd jobbot/ui && npm install`
  - `PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000`
  - `PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape,apply`
  - `cd jobbot/ui && npm run dev -- --host 127.0.0.1 --port 5173`
  - `open http://localhost:5173/interventions`
  - `curl http://127.0.0.1:8000/api/interventions?status=OPEN`
  - `curl http://127.0.0.1:8000/api/interventions?status=RESOLVED`
  - `curl http://127.0.0.1:8000/api/interventions?status=ABORTED`

---

## TASK-05 — ATS Resume Matching + Tailoring Engine

### Scope

Build the ATS resume-to-job matching scorer and rule-based resume tailoring
engine. After job scoring, automatically compute how well the operator's
resume aligns with each job posting using ATS-style keyword analysis. Provide
a tailoring engine that can rewrite the resume to improve the match (wired
into the apply flow in TASK-08).

### Files to Create/Edit

- `core/resumes/__init__.py`
- `core/resumes/parser.py` — PDF text extraction (uses `pdfplumber`)
- `core/resumes/ats_scorer.py` — Keyword extraction + ATS match score computation
- `core/resumes/keywords.py` — Tech keyword dictionaries + synonym normalization map
- `core/resumes/tailor.py` — Rule-based resume tailoring engine (replaces V2 stub)
- `apps/worker/tasks/ats_match.py` — `ats_match_resume` Celery task
- `apps/worker/tasks/scrape.py` — Update chain: `score_jobs` → `ats_match_resume`
- `apps/worker/celery_app.py` — Add task route: `apps.worker.tasks.ats_match.*` → `default` queue
- `core/db/models.py` — Add `ats_match_score` + `ats_match_breakdown_json` columns to Job model
- `requirements.txt` — Add `pdfplumber>=0.10.0`
- `.env.example` / `.env` — Add `MASTER_SKILLS_PATH`, `RESUME_TAILOR_ENABLED`

### Resume Parser

```python
# core/resumes/parser.py
import pdfplumber

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file."""
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)
```

### Keyword Dictionary

```python
# core/resumes/keywords.py

SYNONYM_MAP = {
    "js": "javascript", "ts": "typescript", "k8s": "kubernetes",
    "postgres": "postgresql", "mongo": "mongodb", "gcp": "google cloud",
    "react.js": "react", "node.js": "nodejs", "vue.js": "vue",
}

TECH_KEYWORDS = {
    "languages": {"python", "javascript", "typescript", "go", "java", "rust", "ruby", "c++", "scala", "kotlin"},
    "frameworks": {"fastapi", "django", "flask", "react", "nextjs", "express", "spring", "rails", "angular", "vue"},
    "databases": {"postgresql", "mysql", "mongodb", "redis", "elasticsearch", "dynamodb", "cassandra"},
    "cloud": {"aws", "google cloud", "azure", "docker", "kubernetes", "terraform", "ansible"},
    "tools": {"git", "jenkins", "github actions", "datadog", "grafana", "kafka", "rabbitmq", "celery"},
}

def normalize_keyword(kw: str) -> str:
    kw = kw.strip().lower()
    return SYNONYM_MAP.get(kw, kw)

def extract_keywords(text: str) -> set[str]:
    """Extract known tech keywords from text, with synonym normalization."""
    text_lower = text.lower()
    found = set()
    all_keywords = set().union(*TECH_KEYWORDS.values())
    for kw in all_keywords:
        if kw in text_lower:
            found.add(kw)
    return found
```

### ATS Match Scorer

```python
# core/resumes/ats_scorer.py

def compute_ats_match(resume_text: str, job_description: str) -> tuple[float, dict]:
    """
    Compare resume keywords against job description keywords.
    Returns (score 0-100, breakdown dict).
    """
    resume_kw = extract_keywords(resume_text)
    jd_kw = extract_keywords(job_description)

    if not jd_kw:
        return 0.0, {"error": "no_keywords_found_in_jd"}

    matched = resume_kw & jd_kw
    missing = jd_kw - resume_kw
    overlap_pct = len(matched) / len(jd_kw) * 100

    breakdown = {
        "keyword_overlap_pct": round(overlap_pct, 1),
        "skills_found": sorted(matched),
        "skills_missing": sorted(missing),
        "resume_extra_skills": sorted(resume_kw - jd_kw),
        "total_jd_keywords": len(jd_kw),
        "matched_keywords": len(matched),
        "suggestions": [f"Add '{kw}' to resume" for kw in sorted(missing)[:5]],
    }

    return round(overlap_pct, 1), breakdown
```

### Resume Tailor Engine (V1 Rule-Based)

```python
# core/resumes/tailor.py

def tailor_resume(
    resume_text: str,
    ats_breakdown: dict,
    master_skills: list[str],
    job_description: str,
) -> str:
    """
    Produce tailored resume text with improved ATS alignment.
    V1 strategy (rule-based):
      1. Parse resume into sections (skills, experience, education, summary).
      2. Skills section: reorder to front-load JD-matching skills; append
         missing skills the operator actually has (from master_skills list).
      3. Experience bullets: reorder within each role to prioritize bullets
         containing JD keywords. No rewriting in V1 — just reordering.
      4. Summary line: inject top 3 missing JD keywords if not already present.
      5. Return modified text (caller generates PDF from it).
    Falls back to original resume_text on any error.
    """
    missing = set(ats_breakdown.get("skills_missing", []))
    addable = missing & {normalize_keyword(s) for s in master_skills}
    # ... section parsing, reordering, keyword injection ...
    return modified_text
```

### Celery Task

```python
# apps/worker/tasks/ats_match.py

@celery_app.task
def ats_match_resume(job_ids: list[str] | None = None):
    """
    Compute ATS match score for SCORED jobs. Runs after score_jobs.
    Parses base resume once (cached per run), then compares against
    each job's description.
    """
    resume_text = extract_text_from_pdf(settings.base_resume_path)

    with get_sync_session() as session:
        if job_ids:
            jobs = session.query(Job).filter(Job.id.in_(job_ids)).all()
        else:
            jobs = session.query(Job).filter(Job.status == "SCORED").all()

        for job in jobs:
            if not job.description:
                continue
            score, breakdown = compute_ats_match(resume_text, job.description)
            job.ats_match_score = score
            job.ats_match_breakdown_json = breakdown

        session.commit()
```

### Task Chain Update

```
Scrape flow:  scrape_jobspy → score_jobs → ats_match_resume → send_notification
```

In `apps/worker/tasks/scrape.py`, after the `score_jobs.delay()` call at the end
of the scrape task, chain `ats_match_resume` to run after scoring completes.

### New Database Columns (jobs table)

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| ats_match_score | FLOAT | 0.0 | 0–100 ATS keyword match scale |
| ats_match_breakdown_json | JSONB | NULL | Keyword overlap details and suggestions |

### New Environment Variables

```bash
MASTER_SKILLS_PATH=./storage/master_skills.json   # JSON array of operator's full skills inventory
RESUME_TAILOR_ENABLED=true                         # Feature flag for rule-based resume tailoring
```

### Master Skills File Format

```json
[
  "python", "fastapi", "django", "flask",
  "javascript", "typescript", "react", "nextjs",
  "postgresql", "redis", "mongodb",
  "aws", "docker", "kubernetes", "terraform",
  "celery", "kafka", "git", "github actions"
]
```

This file represents skills the operator actually possesses. The tailor will only
inject missing keywords from this list (never fabricate skills).

### Acceptance Checks

```bash
# 1. Place a real PDF resume
cp /path/to/your/resume.pdf storage/base_resume.pdf

# 2. Create master skills file
echo '["python","fastapi","aws","docker","postgresql","react","typescript","celery","redis"]' > storage/master_skills.json

# 3. Docker + API + Worker running
docker compose up -d
uvicorn apps.api.main:app --reload --port 8000
celery -A apps.worker.celery_app worker -l info -Q default,scrape,apply

# 4. Run a scrape
curl -X POST http://localhost:8000/api/jobs/run-scrape

# 5. Wait for scoring + ATS matching (~15 seconds after scrape)

# 6. Check ATS match scores
docker exec -it jobbot-postgres-1 psql -U postgres -d jobbot -c \
  "SELECT title, score_total, ats_match_score FROM jobs WHERE status='SCORED' ORDER BY ats_match_score DESC LIMIT 5;"
# Expected: jobs with ats_match_score > 0

# 7. Check ATS breakdown
docker exec -it jobbot-postgres-1 psql -U postgres -d jobbot -c \
  "SELECT ats_match_breakdown_json FROM jobs WHERE ats_match_score > 0 LIMIT 1;"
# Expected: JSON with skills_found, skills_missing, suggestions keys

# 8. Test scorer directly (sanity check)
python -c "
from core.resumes.parser import extract_text_from_pdf
from core.resumes.ats_scorer import compute_ats_match
resume = extract_text_from_pdf('storage/base_resume.pdf')
score, bd = compute_ats_match(resume, 'Looking for Python developer with FastAPI, AWS, Kubernetes experience')
print(f'Score: {score}')
print(f'Found: {bd[\"skills_found\"]}')
print(f'Missing: {bd[\"skills_missing\"]}')
"
# Expected: score > 0, skills_found and skills_missing populated
```

**STOP after all checks pass.**

### Completion Notes (2026-03-03)

- Status: DONE
- What changed:
  - Added `jobbot/ui/src/pages/JobDetailPage.tsx` with description, score breakdown, company info, application history, artifacts, contextual actions, and intervention link.
  - Added `jobbot/ui/src/pages/ApplicationsPage.tsx` with status filter, applications table, and expandable detail row for error/fields data.
  - Added `jobbot/ui/src/components/ScoreBreakdown.tsx`.
  - Added `jobbot/ui/src/components/ArtifactViewer.tsx`.
  - Updated `jobbot/ui/src/App.tsx` routes for `/jobs/:id` and `/applications`.
  - Updated `jobbot/ui/src/components/JobTable.tsx` to include internal `View details` links.
  - Updated `jobbot/ui/src/api.ts` with applications API methods/types.
- Commands run:
  - `PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000`
  - `PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape,apply`
  - `cd jobbot/ui && npm run dev -- --host 127.0.0.1 --port 5173`
  - `cd jobbot/ui && npm run build`
  - Playwright UI checks over:
    - `http://127.0.0.1:5173/jobs/$JOB_ID`
    - `http://127.0.0.1:5173/applications`

---

## TASK-06 — Jobs API Endpoints + Minimal UI

### Scope

Implement full Jobs CRUD API and a minimal React UI that displays the jobs
table.

### Files to Create/Edit

- `apps/api/routes/jobs.py` — Complete: GET list, GET detail, POST approve/reject/queue-apply, bulk actions
- `ui/package.json`
- `ui/vite.config.ts` — proxy `/api` to FastAPI
- `ui/tsconfig.json`
- `ui/tailwind.config.js`
- `ui/postcss.config.js`
- `ui/index.html`
- `ui/src/main.tsx`
- `ui/src/App.tsx` — Router setup
- `ui/src/api.ts` — Fetch wrapper
- `ui/src/pages/JobsPage.tsx` — Jobs table with filters and actions
- `ui/src/components/Layout.tsx` — Navigation sidebar
- `ui/src/components/StatusBadge.tsx` — Color-coded status badges
- `ui/src/components/JobTable.tsx` — Reusable table component

### UI Requirements (V1 Minimal)

- Table columns: Title, Company, Source, Score, Status, Scraped At.
- Status filter dropdown (ALL, NEW, SCORED, APPROVED, REJECTED, etc.).
- Search input (filters title + company).
- Row click → expand or navigate to detail (can be inline for V1).
- Approve / Reject / Queue Apply buttons per row (shown based on current status).
- Mobile-responsive: stack on small screens.
- Use Tailwind CSS utility classes only.

### API List Endpoint

```
GET /api/jobs?status=SCORED&q=fintech&min_score=2.0&page=1&per_page=25&sort_by=score_total&sort_dir=desc
```

Returns paginated response with total count.

### Acceptance Checks

```bash
# 1. Install UI dependencies
cd ui && npm install && cd ..

# 2. Start API + UI
uvicorn apps.api.main:app --reload --port 8000 &
cd ui && npm run dev &

# 3. Open browser
open http://localhost:5173

# 4. Verify: jobs table visible with data from previous scrape
# 5. Verify: status filter works
# 6. Verify: search filters by title/company
# 7. Verify: Approve button changes status (check DB)
# 8. Verify: page works on mobile viewport (Chrome DevTools → responsive mode)
```

**STOP after all checks pass.**

### Completion Notes (2026-03-03)

- Status: DONE
- What changed:
  - Added `jobbot/apps/api/routes/runs.py` with `GET /api/runs` and `GET /api/runs/{id}`.
  - Added `jobbot/apps/api/routes/ws.py` with WebSocket stream endpoint at `/ws/logs`.
  - Updated `jobbot/apps/api/main.py` to mount runs + websocket routers.
  - Updated `jobbot/apps/worker/tasks/scrape.py` to publish basic scrape log messages to Redis pub/sub channel `jobbot:logs`.
  - Added `jobbot/ui/src/pages/RunsPage.tsx` with runs table, `Run Scrape Now` button, and polling while any run is `RUNNING`.
  - Updated `jobbot/ui/src/App.tsx` to add `/runs` route.
  - Updated `jobbot/ui/src/api.ts` with `fetchRuns()` and `runScrapeNow()` helpers and run response types.
- Commands run:
  - `PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000`
  - `PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape,apply`
  - `cd jobbot/ui && npm run dev -- --host 127.0.0.1 --port 5173`
  - `cd jobbot/ui && npm run build`
  - Browser/API acceptance script against `http://127.0.0.1:5173/runs` and `/api/runs`

---

## TASK-07 — Approve/Reject/Queue Apply + State Machine Enforcement

### Scope

Enforce valid state transitions on the API side. Wire `queue-apply` to
enqueue a Celery task.

### Files to Edit

- `apps/api/routes/jobs.py` — Add transition validation

### State Transition Rules

```
approve:     NEW|SCORED                     → APPROVED
reject:      NEW|SCORED|APPROVED            → REJECTED
queue_apply: APPROVED                       → APPLY_QUEUED  (enqueue celery task)
```

Invalid transitions return `409 Conflict`:
```json
{"detail": "Cannot transition from REJECTED to APPROVED"}
```

Idempotent: calling `approve` on an already-APPROVED job returns 200.

### Acceptance Checks

```bash
# 1. Get a SCORED job ID
JOB_ID=$(curl -s 'http://localhost:8000/api/jobs?status=SCORED&per_page=1' | python -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

# 2. Approve it
curl -X POST http://localhost:8000/api/jobs/$JOB_ID/approve
# Expected: {"id": "...", "status": "APPROVED"}

# 3. Approve again (idempotent)
curl -X POST http://localhost:8000/api/jobs/$JOB_ID/approve
# Expected: 200 OK

# 4. Try invalid transition
curl -X POST http://localhost:8000/api/jobs/$JOB_ID/reject
# Expected: 200 (APPROVED → REJECTED is valid)

# 5. Try rejecting a rejected job
curl -X POST http://localhost:8000/api/jobs/$JOB_ID/approve
# Expected: 409 (REJECTED → APPROVED is invalid)
```

**STOP after all checks pass.**

---

## TASK-08 — Application + Artifact Models + Resume Preparation

### Scope

Wire up the application and artifact tables. Implement resume preparation with
ATS-based tailoring (using the engine built in TASK-05). Falls back to base
resume copy when tailoring is disabled or ATS data is unavailable.

### Files to Create/Edit

- `core/resumes/manager.py` — `prepare_resume()` with tailor integration (see SPEC.md §11)
- `apps/worker/tasks/resume.py` — `prepare_resume` task
- `apps/worker/tasks/apply.py` — `apply_job` task skeleton (calls prepare_resume, logs application)
- `apps/api/routes/applications.py` — GET list, GET detail
- `apps/api/routes/artifacts.py` — GET download, GET preview
- `apps/api/main.py` — Mount new routers

### Resume Manager Logic

1. Check `BASE_RESUME_PATH` exists. If not, log warning and skip.
2. Create `ARTIFACT_DIR/{job_id}/` directory.
3. If `RESUME_TAILOR_ENABLED` and job has `ats_match_breakdown_json`:
   a. Call `tailor_resume()` with resume text + ATS breakdown + master skills.
   b. Generate tailored PDF with timestamped filename.
   c. Set `meta_json = {"tailored": true, "ats_match_score": ...}` on artifact.
4. Else: copy base resume with timestamped filename (original V1 behavior).
5. Create Artifact DB record.
6. Return artifact.

### Acceptance Checks

```bash
# 1. Place a test resume
echo "test resume content" > storage/base_resume.pdf

# 2. Queue apply on an approved job
JOB_ID=$(curl -s 'http://localhost:8000/api/jobs?status=APPROVED&per_page=1' | python -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")
curl -X POST http://localhost:8000/api/jobs/$JOB_ID/queue-apply

# 3. Wait for task to run

# 4. Check application created
curl http://localhost:8000/api/applications?job_id=$JOB_ID
# Expected: at least one application record

# 5. Check artifact created
ls storage/artifacts/$JOB_ID/
# Expected: resume_*.pdf file

# 6. Download artifact via API
ARTIFACT_ID=$(docker exec -it jobbot-postgres-1 psql -U postgres -d jobbot -At -c "SELECT id FROM artifacts WHERE job_id='$JOB_ID' LIMIT 1;")
curl -I http://localhost:8000/api/artifacts/$ARTIFACT_ID/download
# Expected: 200 with Content-Disposition header
```

**STOP after all checks pass.**

---

## TASK-09 — Playwright Runner + ATS Detection

### Scope

Implement the browser automation skeleton that opens a job URL, detects
ATS type, and records what happens.

### Files to Create/Edit

- `apps/browser/__init__.py`
- `apps/browser/runner.py` — Main `apply_job()` function (see SPEC.md §12.1)
- `apps/browser/detectors.py` — Block detection (see SPEC.md §12.3)
- `apps/browser/ats/__init__.py`
- `apps/browser/ats/base.py` — Abstract `BaseATSHandler`
- `apps/browser/ats/greenhouse.py` — Basic handler (find "Apply" button, log what's visible)
- `apps/browser/ats/lever.py` — Basic handler
- `apps/browser/ats/ashby.py` — Basic handler
- `apps/browser/ats/workday.py` — Stub → immediate intervention
- `apps/browser/ats/yc.py` — Stub → immediate intervention
- `apps/worker/tasks/apply.py` — Wire to call `runner.apply_job()`

### Runner Flow (V1)

1. Load job from DB.
2. Create application record (STARTED).
3. Launch Playwright persistent context.
4. Navigate to `apply_url` or `url`.
5. Wait for page load.
6. Run `detect_blocks()`.
7. If blocked → capture artifacts → create intervention → stop.
8. Detect ATS type from final URL (after redirects).
9. Dispatch to ATS handler.
10. V1 ATS handlers: find the "Apply" button, take a screenshot, mark as
    INTERVENTION_REQUIRED with reason "unexpected_field" (we're not filling
    forms yet, just proving the pipeline works).
11. On any exception: capture screenshot + error trace → FAILED.

### Important

- Install Playwright browsers first: `playwright install chromium`
- Use `PLAYWRIGHT_HEADFUL=true` so you can watch it during dev.
- All exceptions MUST be caught. Never crash the Celery worker.

### Acceptance Checks

```bash
# 1. Ensure Playwright is installed
playwright install chromium

# 2. Bootstrap Simplify session once (headed)
python scripts/bootstrap_simplify.py

# 3. Start worker (serialized apply execution)
celery -A apps.worker.celery_app worker -l info -Q default,scrape,apply -c 1

# 4. Queue apply on a job (pick one with a real URL)
curl -X POST http://localhost:8000/api/jobs/$JOB_ID/queue-apply

# 5. Watch the Celery worker output — browser should open, extension should load

# 6. Check application status
curl http://localhost:8000/api/applications?job_id=$JOB_ID
# Expected: application with status (INTERVENTION_REQUIRED or FAILED)

# 7. Check artifacts (screenshot + milestone logs should exist)
ls storage/artifacts/$JOB_ID/
# Expected: screenshot_*.png and/or page_*.html + browser_launched_*.log + extension_detected_*.log
```

**STOP after all checks pass.**

---

## TASK-10 — Intervention System + Push Notifications

### Scope

Wire intervention creation, push notifications, and the intervention API
endpoints.

### Files to Create/Edit

- `core/notify/__init__.py`
- `core/notify/base.py` — Abstract notifier
- `core/notify/pushover.py` — Pushover implementation (see SPEC.md §13)
- `core/notify/ntfy.py` — ntfy implementation
- `apps/worker/tasks/notify.py` — `send_notification` task
- `apps/api/routes/interventions.py` — GET list, GET detail, POST resolve/abort/retry
- `apps/api/main.py` — Mount interventions router
- `apps/browser/runner.py` — Wire intervention creation + notification after block detection

### Intervention API

```
GET /api/interventions?status=OPEN
GET /api/interventions/{id}
POST /api/interventions/{id}/resolve   — body: { "notes": "..." }
POST /api/interventions/{id}/abort
POST /api/interventions/{id}/retry-apply
```

### Retry Logic

`retry-apply` must:
1. Set intervention status to RESOLVED.
2. Set job status back to APPLY_QUEUED.
3. Create a new application record.
4. Enqueue new `apply_job` task.
5. Return the new application ID.

### Acceptance Checks

```bash
# 1. Trigger an apply that will create an intervention
# (Any job should create one since V1 ATS handlers don't fill forms)
curl -X POST http://localhost:8000/api/jobs/$JOB_ID/queue-apply

# 2. Check interventions
curl http://localhost:8000/api/interventions?status=OPEN
# Expected: at least one OPEN intervention

# 3. If Pushover is configured, check phone for push notification

# 4. Resolve the intervention
INT_ID=$(curl -s 'http://localhost:8000/api/interventions?status=OPEN' | python -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")
curl -X POST http://localhost:8000/api/interventions/$INT_ID/resolve -H "Content-Type: application/json" -d '{"notes": "test resolve"}'
# Expected: {"id": "...", "status": "RESOLVED"}

# 5. Retry apply
curl -X POST http://localhost:8000/api/interventions/$INT_ID/retry-apply
# Expected: {"id": "...", "new_application_id": "...", "task_id": "..."}
```

**STOP after all checks pass.**

---

## TASK-11 — Interventions UI + Screenshot Preview

### Scope

Build the Interventions page in the React UI with screenshot previews and
action buttons.

### Files to Create/Edit

- `ui/src/pages/InterventionsPage.tsx`
- `ui/src/components/InterventionCard.tsx`
- `ui/src/App.tsx` — Add route
- `ui/src/components/Layout.tsx` — Add nav link with open count badge

### UI Requirements

- Card layout (not table) — better for screenshot previews.
- Each card shows:
  - Job title + company name
  - Reason badge (color-coded: red for CAPTCHA, orange for MFA, yellow for unexpected_field)
  - Screenshot thumbnail (clickable to expand)
  - Last URL (clickable link)
  - Created timestamp
- Action buttons: Resolve, Abort, Retry Apply
- Resolve opens a small form for optional notes.
- Filter tabs: OPEN (default), RESOLVED, ABORTED
- Open count badge in sidebar navigation (polls every 15 seconds).
- Mobile-responsive: single column on small screens.

### Acceptance Checks

```bash
# 1. Ensure there are interventions in the DB (from TASK-10)

# 2. Open UI
open http://localhost:5173/interventions

# 3. Verify:
# - Cards displayed with screenshot preview
# - Reason badge visible
# - Resolve/Abort/Retry buttons work
# - Filter tabs switch between statuses
# - Badge count shows in sidebar
# - Mobile viewport works
```

**STOP after all checks pass.**

---

## TASK-12 — Job Detail Page + Applications + Artifacts UI

### Scope

Build the Job Detail page, Applications list page, and artifact viewer.

### Files to Create/Edit

- `ui/src/pages/JobDetailPage.tsx`
- `ui/src/pages/ApplicationsPage.tsx`
- `ui/src/components/ScoreBreakdown.tsx`
- `ui/src/components/ArtifactViewer.tsx`
- `ui/src/App.tsx` — Add routes

### Job Detail Page

- Full job description (rendered, not raw).
- Score breakdown (bar chart or table showing each rule's contribution).
- Company info.
- Application history table (linked to Applications page).
- Artifacts list with download links.
- Action buttons (Approve / Reject / Queue Apply — contextual).
- Link to intervention if one exists.

### Applications Page

- Table: Job Title, Company, Status, Method, Started At, Duration, Error
- Filter by status.
- Click row → expand to show error_text and fields_json.

### Acceptance Checks

```bash
# 1. Open a job detail page
open http://localhost:5173/jobs/$JOB_ID

# 2. Verify: description, score breakdown, artifacts, applications visible

# 3. Open applications page
open http://localhost:5173/applications

# 4. Verify: applications listed with correct statuses
```

**STOP after all checks pass.**

---

## TASK-13 — Scrape Runs Page + WebSocket Logs

### Scope

Build the Scrape Runs page and basic WebSocket log streaming.

### Files to Create/Edit

- `apps/api/routes/runs.py` — GET list, GET detail
- `apps/api/routes/ws.py` — WebSocket `/ws/logs`
- `apps/api/main.py` — Mount routes
- `ui/src/pages/RunsPage.tsx`
- `ui/src/App.tsx` — Add route

### Scrape Runs Page

- Table: Source, Status, Started At, Duration, Stats (fetched/inserted/duplicates)
- "Run Scrape Now" button → calls `POST /api/jobs/run-scrape`
- Auto-refresh while a run is in RUNNING status.

### WebSocket Logs (V1 Basic)

- API broadcasts Celery task log lines to connected WebSocket clients.
- V1: simple approach — worker writes log lines to Redis pub/sub, WebSocket
  endpoint subscribes and forwards.
- UI: optional log viewer panel (can be a collapsible drawer at bottom).

### Acceptance Checks

```bash
# 1. Open runs page
open http://localhost:5173/runs

# 2. Click "Run Scrape Now"
# 3. Verify: new run appears with RUNNING status
# 4. Wait for completion → status updates to SUCCESS
# 5. Stats visible (fetched, inserted, duplicates)
```

**STOP after all checks pass.**

---

## TASK-14 — Polish + End-to-End Smoke Test

### Scope

Final polish, error handling, and a full end-to-end test.

### Tasks

1. Add proper error handling to all API routes (400/404/409/500).
2. Add loading spinners / skeleton loaders to UI.
3. Add toast notifications for API errors in UI.
4. Ensure all directories auto-create on startup.
5. Write `scripts/dev.sh` that starts all services.
6. Write `scripts/seed.sh` that runs a scrape + scores.
7. Update `README.md` with complete setup instructions.

### End-to-End Smoke Test

Execute this sequence manually:

```bash
# 1. Clean start
docker compose down -v && docker compose up -d
uvicorn apps.api.main:app --reload --port 8000 &
celery -A apps.worker.celery_app worker -l info -Q default,scrape,apply &
cd ui && npm run dev &

# 2. Trigger scrape
curl -X POST http://localhost:8000/api/jobs/run-scrape

# 3. Wait for scrape + scoring (watch Celery output)

# 4. Open UI → Jobs page
# Verify: jobs visible with scores

# 5. Approve a job
# Click Approve → status changes

# 6. Queue Apply
# Click Queue Apply → status changes to APPLY_QUEUED

# 7. Watch Playwright open browser

# 8. Check: either SUBMITTED or INTERVENTION_REQUIRED

# 9. If intervention: check Interventions page
# Verify: card with screenshot, reason, actions

# 10. If Pushover configured: check phone notification

# 11. Resolve or retry intervention

# 12. Check Applications page: history visible

# 13. Check Runs page: scrape run with stats

# 14. Download an artifact via UI
```

ALL 14 steps must work. If any fail, fix and re-test.

### Acceptance Checks

The entire sequence above completes without errors.

### Completion Notes (2026-03-03)

- Status: DONE
- What changed:
  - Added global 500 handler and startup directory creation in `jobbot/apps/api/main.py`.
  - Added UI toast system: `jobbot/ui/src/notify.ts`, `jobbot/ui/src/components/ToastHost.tsx`, and mounted in `Layout`.
  - Added loading skeletons and toast-triggering error handling across major pages/components:
    - `JobsPage`, `InterventionsPage`, `ApplicationsPage`, `JobDetailPage`, `RunsPage`, `InterventionCard`.
  - Reworked `jobbot/scripts/dev.sh` to start Docker + API + worker + UI together (with cleanup trap).
  - Added `jobbot/scripts/seed.sh` to trigger and wait for a scrape run.
  - Updated `jobbot/README.md` with full setup/run/seed instructions.
- Commands run:
  - `docker compose down -v && docker compose up -d`
  - `PYTHONPATH=. uvicorn apps.api.main:app --reload --port 8000`
  - `PYTHONPATH=. celery -A apps.worker.celery_app worker -P solo -l info -Q default,scrape,apply`
  - `cd jobbot/ui && npm run dev -- --host 127.0.0.1 --port 5173`
  - `curl -X POST http://127.0.0.1:8000/api/jobs/run-scrape`
  - Full API/UI smoke checks via Playwright + HTTP validations for steps 4-14

**STOP. V1 is complete.**

---

## Summary

| Task | Description | Key Output |
|------|-------------|------------|
| 01 | Scaffold + Docker | Health endpoint running |
| 02 | DB Models | All 6 tables created |
| 03 | JobSpy Scraper | Jobs in database |
| 04 | Scoring | Jobs scored with breakdown |
| 05 | ATS Resume Matching | Resume scored against JDs, tailor engine ready |
| 06 | Jobs API + UI | View + filter jobs in browser |
| 07 | State Machine | Approve/reject/queue-apply enforced |
| 08 | Applications + Resumes | Tailored resume generated, application logged |
| 09 | Playwright Runner | Browser opens, ATS detected |
| 10 | Interventions + Push | Blocked jobs create interventions + notify |
| 11 | Interventions UI | Cards with screenshots + actions |
| 12 | Job Detail + Apps UI | Full detail + application history |
| 13 | Runs Page + Logs | Scrape history + real-time logs |
| 14 | Polish + E2E Test | Full pipeline verified |
