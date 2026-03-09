# JobBot — V1 Full System Specification

> **Purpose**: This is the single source of truth for the entire JobBot system. Every
> implementation decision, data model, endpoint, worker task, and UI behavior is
> defined here. Cursor agents MUST consult this document before writing any code.

---

## 1. Objective

Build a **local-first, VM-ready** automated job discovery and application engine.

The system:
1. Scrapes job listings from multiple sources (JobSpy as V1 primary).
2. Stores, deduplicates, and scores them against a configurable profile.
3. Presents jobs in a mobile-responsive UI for human review (approve / reject).
4. Scores resume–job ATS alignment and generates tailored resume artifacts per approved job.
5. Launches a Playwright browser worker to apply on ATS platforms.
6. Detects CAPTCHA / MFA / unexpected form states and creates intervention records.
7. Captures screenshots + HTML artifacts for debugging.
8. Sends push notifications when human intervention is needed.
9. Tracks full state history for every job and application attempt.
10. Exposes a clean REST API so OpenClaw (or any agent framework) can integrate later without engine changes.

---

## 2. Non-Goals (V1)

- No automatic CAPTCHA solving (NopeCHA, undetected-chromedriver, Buster). Treat blocks as intervention events.
- No OpenClaw integration yet. The API is designed to be agent-friendly, but no agent framework is wired in V1.
- No multi-user auth. Single operator. Optional basic auth can be added later.
- No perfect universal ATS coverage. V1 handles Greenhouse, Lever, Ashby. Workday and others route to intervention.
- No LLM-based resume rewriting. V1 uses rule-based ATS keyword optimization for resume tailoring. LLM-powered rewriting is a V2 extension.
- No Wellfound, BuiltInNYC, or YC scrapers wired end-to-end in V1. Modules are scaffolded with adapters but disabled behind feature flags.

---

## 3. Success Criteria (end-to-end proof)

All of the following must work in sequence on a single local machine:

1. `docker compose up -d` starts Postgres + Redis.
2. `uvicorn apps.api.main:app --reload` starts the API.
3. `celery -A apps.worker.celery_app worker -l info` starts the worker.
4. `POST /api/jobs/run-scrape` triggers a JobSpy scrape.
5. Jobs appear in the UI at `/ui/jobs` with scores.
6. Approving a job in the UI sets `status=APPROVED`.
7. Clicking "Queue Apply" sets `status=APPLY_QUEUED` and enqueues a Celery task.
8. The Playwright worker opens the apply URL, detects ATS type, attempts basic interaction.
9. If blocked (CAPTCHA, MFA, unexpected form): screenshot + HTML artifacts are captured, an intervention record is created, a push notification is sent.
10. The intervention is visible in the UI at `/ui/interventions` with screenshot preview and Resolve / Abort / Retry actions.
11. If apply succeeds: `application.status=SUBMITTED`, `job.status=APPLIED`, push notification sent.
12. All artifacts (screenshots, HTML, resume copies) are stored in `storage/artifacts/` and downloadable via `/api/artifacts/{id}/download`.

---

## 4. Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Language | Python 3.11+ | Entire backend + workers |
| API Framework | FastAPI + Uvicorn | REST + WebSocket |
| Database | PostgreSQL 16 | Via Docker |
| ORM | SQLAlchemy 2.0 (async) | Models + session management |
| Migrations | Alembic (optional V1) | Auto-create tables on startup is acceptable |
| Task Queue | Celery 5.x + Redis | Background scraping, scoring, applying |
| Browser Automation | Playwright (Chromium) | Headful with persistent profile |
| Job Scraping | JobSpy (`python-jobspy`) | LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter |
| Push Notifications | Pushover (primary), ntfy (fallback) | Deep links to intervention UI |
| UI | React + Vite + Tailwind CSS | Mobile-responsive; served by FastAPI or standalone |
| Artifact Storage | Local filesystem (`storage/artifacts/`) | Paths stored in DB |
| Browser Profiles | Local filesystem (`storage/profiles/`) | Persistent Chromium profiles |

---

## 5. Project Structure

```
jobbot/
├── README.md
├── SPEC.md                          # This file
├── ARCHITECTURE.md                  # System architecture doc
├── TASKS.md                         # Implementation task list
├── .cursorrules                     # Cursor agent rules
├── .env.example
├── .gitignore
├── requirements.txt
├── docker-compose.yml
│
├── alembic/                         # Optional migrations
│   ├── alembic.ini
│   └── versions/
│
├── storage/
│   ├── artifacts/                   # Runtime artifacts (screenshots, resumes, HTML)
│   └── profiles/                    # Persistent Chromium browser profiles
│
├── apps/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app factory, lifespan, static serving
│   │   ├── settings.py              # Pydantic Settings class (reads .env)
│   │   ├── deps.py                  # Dependency injection (DB session, settings)
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── jobs.py              # /api/jobs CRUD + state transitions
│   │       ├── applications.py      # /api/applications read
│   │       ├── interventions.py     # /api/interventions CRUD + resolve/retry
│   │       ├── artifacts.py         # /api/artifacts download
│   │       ├── runs.py              # /api/runs scrape history
│   │       └── ws.py                # /ws/logs WebSocket stream
│   │
│   ├── worker/
│   │   ├── __init__.py
│   │   ├── celery_app.py            # Celery app instance + config
│   │   └── tasks/
│   │       ├── __init__.py
│   │       ├── scrape.py            # scrape_jobspy task
│   │       ├── score.py             # score_jobs task
│   │       ├── ats_match.py         # ats_match_resume task
│   │       ├── apply.py             # apply_job task
│   │       ├── resume.py            # prepare_resume task
│   │       └── notify.py            # send_notification task
│   │
│   └── browser/
│       ├── __init__.py
│       ├── runner.py                # Playwright orchestrator (apply_job entry)
│       ├── detectors.py             # CAPTCHA / MFA / block detection
│       └── ats/
│           ├── __init__.py
│           ├── base.py              # Abstract ATS handler
│           ├── greenhouse.py
│           ├── lever.py
│           ├── ashby.py
│           ├── workday.py           # Stub → intervention
│           └── yc.py                # Stub → intervention
│
├── core/
│   ├── __init__.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py                  # SQLAlchemy declarative base
│   │   ├── models.py                # All ORM models
│   │   └── session.py               # Async engine + session factory
│   │
│   ├── scraping/
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract scraper interface
│   │   ├── jobspy_scraper.py        # JobSpy wrapper
│   │   ├── wellfound.py             # Stub (disabled V1)
│   │   ├── builtinnyc.py            # Stub (disabled V1)
│   │   └── yc.py                    # Stub (disabled V1)
│   │
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── scorer.py                # Score computation
│   │   └── rules.py                 # Scoring rules config
│   │
│   ├── resumes/
│   │   ├── __init__.py
│   │   ├── manager.py               # Resume copy + tailor dispatch
│   │   ├── parser.py                # PDF text extraction (pdfplumber)
│   │   ├── ats_scorer.py            # ATS keyword match scorer
│   │   ├── keywords.py              # Tech keyword dictionaries + synonyms
│   │   └── tailor.py                # Rule-based resume tailoring engine
│   │
│   └── notify/
│       ├── __init__.py
│       ├── base.py                  # Abstract notifier
│       ├── pushover.py              # Pushover implementation
│       └── ntfy.py                  # ntfy implementation
│
├── ui/                              # React + Vite + Tailwind
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api.ts                   # API client (fetch wrapper)
│       ├── pages/
│       │   ├── JobsPage.tsx
│       │   ├── JobDetailPage.tsx
│       │   ├── ApplicationsPage.tsx
│       │   ├── InterventionsPage.tsx
│       │   ├── RunsPage.tsx
│       │   └── SettingsPage.tsx
│       └── components/
│           ├── Layout.tsx
│           ├── JobTable.tsx
│           ├── StatusBadge.tsx
│           ├── ScoreBreakdown.tsx
│           ├── ArtifactViewer.tsx
│           └── InterventionCard.tsx
│
└── scripts/
    ├── dev.sh                       # Start all services locally
    ├── seed.sh                      # Seed DB with test data
    └── run_scrape_once.py           # One-shot scrape for testing
```

---

## 6. Environment Variables

```bash
# === Core ===
APP_ENV=dev
API_HOST=0.0.0.0
API_PORT=8000
UI_BASE_URL=http://localhost:5173   # Used in push notification deep links

# === Database ===
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/jobbot
DATABASE_URL_SYNC=postgresql+psycopg2://postgres:postgres@localhost:5432/jobbot

# === Redis ===
REDIS_URL=redis://localhost:6379/0

# === File Storage ===
ARTIFACT_DIR=./storage/artifacts
PROFILE_DIR=./storage/profiles

# === Scraper Defaults ===
DEFAULT_SEARCH_QUERY=backend engineer fintech
DEFAULT_LOCATION=New York, NY
SCRAPE_HOURS_OLD=48
SCRAPE_RESULTS_WANTED=50

# === Feature Flags (scrapers) ===
JOBSPY_ENABLED=true
WELLFOUND_ENABLED=false
BUILTINNYC_ENABLED=false
YC_ENABLED=false

# === Apollo (optional enrichment) ===
APOLLO_API_KEY=

# === ScrapeOps (only if using Scrapy LinkedIn — not V1) ===
SCRAPEOPS_API_KEY=

# === Push Notifications ===
PUSH_PROVIDER=pushover              # pushover | ntfy | none
PUSHOVER_TOKEN=
PUSHOVER_USER=
NTFY_TOPIC_URL=

# === Resume ===
BASE_RESUME_PATH=./storage/base_resume.pdf

# === Resume ATS Matching ===
MASTER_SKILLS_PATH=./storage/master_skills.json   # Operator's full skills inventory
RESUME_TAILOR_ENABLED=true                         # Enable rule-based resume tailoring

# === Playwright ===
PLAYWRIGHT_HEADFUL=true
PLAYWRIGHT_SLOW_MO_MS=0
PLAYWRIGHT_PROFILE_NAME=default
PLAYWRIGHT_TIMEOUT_MS=30000
SIMPLIFY_ENABLED=false
SIMPLIFY_EXTENSION_PATH=                      # required only when SIMPLIFY_ENABLED=true
SIMPLIFY_PROFILE_DIR=                         # required only when SIMPLIFY_ENABLED=true
```

---

## 7. Database Schema

### 7.1 Enums

```python
# Job status lifecycle
class JobStatus(str, Enum):
    NEW = "NEW"
    SCORED = "SCORED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLY_QUEUED = "APPLY_QUEUED"
    APPLIED = "APPLIED"
    APPLY_FAILED = "APPLY_FAILED"
    INTERVENTION_REQUIRED = "INTERVENTION_REQUIRED"

# Application attempt status
class ApplicationStatus(str, Enum):
    STARTED = "STARTED"
    SUBMITTED = "SUBMITTED"
    FAILED = "FAILED"
    INTERVENTION_REQUIRED = "INTERVENTION_REQUIRED"
    SKIPPED = "SKIPPED"

# Intervention status
class InterventionStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    ABORTED = "ABORTED"

# Scrape run status
class ScrapeRunStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

# ATS type detection
class ATSType(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKDAY = "workday"
    YC = "yc"
    CUSTOM = "custom"
    UNKNOWN = "unknown"

# Artifact kind
class ArtifactKind(str, Enum):
    SCREENSHOT = "screenshot"
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
    LOG = "log"
    OTHER = "other"

# Job source
class JobSource(str, Enum):
    JOBSPY = "jobspy"
    WELLFOUND = "wellfound"
    BUILTINNYC = "builtinnyc"
    YC = "yc"
    MANUAL = "manual"
    OTHER = "other"

# Intervention reason
class InterventionReason(str, Enum):
    CAPTCHA = "captcha"
    MFA = "mfa"
    UNEXPECTED_FIELD = "unexpected_field"
    BLOCKED = "blocked"
    LOGIN_REQUIRED = "login_required"
    OTHER = "other"

# Apply method
class ApplyMethod(str, Enum):
    PLAYWRIGHT = "playwright"
    MANUAL = "manual"
```

### 7.2 Tables

#### `companies`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default uuid4 | |
| name | TEXT | NOT NULL | |
| domain | TEXT | NULLABLE | e.g. `stripe.com` |
| linkedin_url | TEXT | NULLABLE | |
| apollo_id | TEXT | NULLABLE | For future enrichment |
| stage | TEXT | NULLABLE | e.g. `Series A`, `Seed` |
| headcount | INT | NULLABLE | |
| last_enriched_at | TIMESTAMPTZ | NULLABLE | |
| created_at | TIMESTAMPTZ | NOT NULL, default now | |
| updated_at | TIMESTAMPTZ | NOT NULL, default now, on update | |

**Indexes**: `companies(name)` (for lookup during scrape dedup)

#### `jobs`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default uuid4 | |
| source | TEXT | NOT NULL | `JobSource` enum value |
| source_job_id | TEXT | NULLABLE | Original platform ID |
| title | TEXT | NOT NULL | |
| company_id | UUID | FK → companies.id, NULLABLE | |
| company_name_raw | TEXT | NOT NULL | Keep raw for debugging |
| location | TEXT | NULLABLE | |
| remote_flag | BOOL | NOT NULL, default false | |
| url | TEXT | NOT NULL | Link to listing |
| apply_url | TEXT | NULLABLE | Direct apply link |
| description | TEXT | NULLABLE | Full JD text |
| salary_min | INT | NULLABLE | Annual USD |
| salary_max | INT | NULLABLE | Annual USD |
| posted_at | TIMESTAMPTZ | NULLABLE | |
| scraped_at | TIMESTAMPTZ | NOT NULL, default now | |
| ats_type | TEXT | NOT NULL, default 'unknown' | `ATSType` enum |
| status | TEXT | NOT NULL, default 'NEW' | `JobStatus` enum |
| score_total | FLOAT | NOT NULL, default 0.0 | |
| score_breakdown_json | JSONB | NULLABLE | `{"title_match": 2, "fintech_keywords": 1.5, ...}` |
| ats_match_score | FLOAT | NOT NULL, default 0.0 | 0–100 ATS keyword match score |
| ats_match_breakdown_json | JSONB | NULLABLE | `{"skills_found": [...], "skills_missing": [...], "suggestions": [...]}` |
| dedup_hash | TEXT | UNIQUE, NOT NULL | `sha256(lower(title) + lower(company_name_raw) + normalize(apply_url or url))` |
| created_at | TIMESTAMPTZ | NOT NULL, default now | |
| updated_at | TIMESTAMPTZ | NOT NULL, default now, on update | |

**Indexes**:
- `jobs(dedup_hash)` UNIQUE
- `jobs(status, scraped_at)` composite
- `jobs(company_id)`
- `jobs(source)`

#### `scrape_runs`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default uuid4 | |
| source | TEXT | NOT NULL | `JobSource` enum |
| started_at | TIMESTAMPTZ | NOT NULL, default now | |
| finished_at | TIMESTAMPTZ | NULLABLE | |
| status | TEXT | NOT NULL, default 'RUNNING' | `ScrapeRunStatus` enum |
| params_json | JSONB | NULLABLE | `{"query": "...", "location": "...", "hours_old": 48}` |
| stats_json | JSONB | NULLABLE | `{"fetched": 50, "inserted": 32, "duplicates": 18, "errors": 0}` |
| error_text | TEXT | NULLABLE | |
| created_at | TIMESTAMPTZ | NOT NULL, default now | |

#### `applications`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default uuid4 | |
| job_id | UUID | FK → jobs.id, NOT NULL | |
| started_at | TIMESTAMPTZ | NOT NULL, default now | |
| finished_at | TIMESTAMPTZ | NULLABLE | |
| status | TEXT | NOT NULL, default 'STARTED' | `ApplicationStatus` enum |
| method | TEXT | NOT NULL, default 'playwright' | `ApplyMethod` enum |
| error_text | TEXT | NULLABLE | |
| fields_json | JSONB | NULLABLE | What we submitted |
| external_app_id | TEXT | NULLABLE | If detectable from confirmation page |
| created_at | TIMESTAMPTZ | NOT NULL, default now | |

**Indexes**: `applications(job_id, started_at)`

#### `artifacts`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default uuid4 | |
| job_id | UUID | FK → jobs.id, NULLABLE | |
| application_id | UUID | FK → applications.id, NULLABLE | |
| kind | TEXT | NOT NULL | `ArtifactKind` enum |
| filename | TEXT | NOT NULL | Original filename |
| path | TEXT | NOT NULL | Relative to ARTIFACT_DIR |
| size_bytes | INT | NULLABLE | |
| created_at | TIMESTAMPTZ | NOT NULL, default now | |
| meta_json | JSONB | NULLABLE | |

#### `interventions`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default uuid4 | |
| job_id | UUID | FK → jobs.id, NOT NULL | |
| application_id | UUID | FK → applications.id, NULLABLE | |
| created_at | TIMESTAMPTZ | NOT NULL, default now | |
| resolved_at | TIMESTAMPTZ | NULLABLE | |
| status | TEXT | NOT NULL, default 'OPEN' | `InterventionStatus` enum |
| reason | TEXT | NOT NULL | `InterventionReason` enum |
| last_url | TEXT | NULLABLE | Where the browser was when blocked |
| screenshot_artifact_id | UUID | FK → artifacts.id, NULLABLE | |
| html_artifact_id | UUID | FK → artifacts.id, NULLABLE | |
| notes | TEXT | NULLABLE | Operator notes |

**Indexes**: `interventions(status, created_at)`

---

## 8. API Specification

### 8.1 Health

```
GET /api/health
→ { "status": "ok", "db": "connected", "redis": "connected" }
```

### 8.2 Jobs

```
GET /api/jobs
  Query params: status, source, q (search title/company), min_score, page, per_page, sort_by, sort_dir
  → { "items": [...], "total": N, "page": 1, "per_page": 25 }

GET /api/jobs/{job_id}
  → Full job object with company, applications, artifacts, interventions

POST /api/jobs/{job_id}/approve
  Transition: SCORED|NEW → APPROVED
  → { "id": "...", "status": "APPROVED" }

POST /api/jobs/{job_id}/reject
  Transition: SCORED|NEW|APPROVED → REJECTED
  → { "id": "...", "status": "REJECTED" }

POST /api/jobs/{job_id}/queue-apply
  Transition: APPROVED → APPLY_QUEUED
  Side effect: enqueues Celery task `apply_job(job_id)`
  → { "id": "...", "status": "APPLY_QUEUED", "task_id": "..." }

POST /api/jobs/run-scrape
  Body (optional): { "query": "...", "location": "...", "hours_old": 48, "results_wanted": 50 }
  Side effect: enqueues Celery task `scrape_jobspy(params)`
  → { "run_id": "...", "status": "RUNNING" }

POST /api/jobs/bulk-approve
  Body: { "job_ids": ["...", "..."] }
  → { "updated": N }

POST /api/jobs/bulk-reject
  Body: { "job_ids": ["...", "..."] }
  → { "updated": N }
```

### 8.3 Applications

```
GET /api/applications
  Query params: job_id, status, page, per_page
  → { "items": [...], "total": N }

GET /api/applications/{application_id}
  → Full application with artifacts
```

### 8.4 Interventions

```
GET /api/interventions
  Query params: status (default: OPEN), page, per_page
  → { "items": [...], "total": N }

GET /api/interventions/{intervention_id}
  → Full intervention with job, application, artifacts

POST /api/interventions/{intervention_id}/resolve
  Body (optional): { "notes": "..." }
  Transition: OPEN → RESOLVED
  → { "id": "...", "status": "RESOLVED" }

POST /api/interventions/{intervention_id}/abort
  Transition: OPEN → ABORTED
  Side effect: sets job.status = APPLY_FAILED
  → { "id": "...", "status": "ABORTED" }

POST /api/interventions/{intervention_id}/retry-apply
  Side effect: creates new application attempt, enqueues `apply_job(job_id)`
  → { "id": "...", "new_application_id": "...", "task_id": "..." }
```

### 8.5 Artifacts

```
GET /api/artifacts/{artifact_id}/download
  → File download (Content-Disposition: attachment)

GET /api/artifacts/{artifact_id}/preview
  → File inline (Content-Disposition: inline) — for screenshots in UI
```

### 8.6 Scrape Runs

```
GET /api/runs
  Query params: source, status, page, per_page
  → { "items": [...], "total": N }

GET /api/runs/{run_id}
  → Full run details with stats
```

### 8.7 WebSocket

```
WS /ws/logs
  Broadcasts worker log lines in real-time.
  Message format: { "timestamp": "...", "level": "INFO", "task": "scrape_jobspy", "message": "..." }
```

### 8.8 API Behavior Rules

- All state transitions MUST be idempotent. Calling `approve` on an already-approved job returns success.
- Invalid transitions return 409 Conflict with current status.
- All list endpoints support pagination: `page` (1-indexed) + `per_page` (default 25, max 100).
- All timestamps are ISO 8601 UTC.
- UUIDs are v4.
- Errors follow: `{ "detail": "message" }` with appropriate HTTP status.

---

## 9. Scraping System

### 9.1 Abstract Interface

Every scraper implements:

```python
class BaseScraper(ABC):
    @abstractmethod
    async def scrape(self, params: ScrapeParams) -> ScrapeResult:
        """Execute scrape and return normalized jobs."""
        ...

@dataclass
class ScrapeParams:
    query: str
    location: str
    hours_old: int = 48
    results_wanted: int = 50

@dataclass
class ScrapeResult:
    jobs: list[NormalizedJob]
    stats: dict  # {"fetched": N, "errors": N}
    error: str | None = None

@dataclass
class NormalizedJob:
    title: str
    company_name: str
    location: str | None
    url: str
    apply_url: str | None
    description: str | None
    salary_min: int | None
    salary_max: int | None
    posted_at: datetime | None
    remote_flag: bool
    source: JobSource
    source_job_id: str | None
```

### 9.2 JobSpy Implementation (V1)

```python
from jobspy import scrape_jobs

# Key parameters:
# - site_name: ["linkedin", "indeed", "glassdoor", "google", "zip_recruiter"]
# - search_term: from DEFAULT_SEARCH_QUERY
# - location: from DEFAULT_LOCATION
# - hours_old: from SCRAPE_HOURS_OLD
# - results_wanted: from SCRAPE_RESULTS_WANTED
# - linkedin_fetch_description: True (slower but gets full JD)
# - country_indeed: "USA"
```

### 9.3 Deduplication

```python
import hashlib

def compute_dedup_hash(title: str, company_name: str, url: str) -> str:
    normalized = (
        title.strip().lower()
        + "|" + company_name.strip().lower()
        + "|" + normalize_url(url).lower()
    )
    return hashlib.sha256(normalized.encode()).hexdigest()

def normalize_url(url: str) -> str:
    """Strip tracking params, fragments, trailing slashes."""
    from urllib.parse import urlparse, urlencode, parse_qs
    parsed = urlparse(url)
    # Keep only path, strip query params that are tracking-only
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    return clean
```

### 9.4 ATS Type Detection (from URL)

```python
ATS_URL_PATTERNS = {
    "greenhouse": ["boards.greenhouse.io", "greenhouse.io/"],
    "lever": ["jobs.lever.co"],
    "ashby": ["jobs.ashbyhq.com", "ashbyhq.com/"],
    "workday": ["myworkdayjobs.com", "wd5.myworkday", "workday.com/"],
    "yc": ["workatastartup.com"],
}

def detect_ats_type(url: str) -> ATSType:
    url_lower = url.lower()
    for ats, patterns in ATS_URL_PATTERNS.items():
        if any(p in url_lower for p in patterns):
            return ATSType(ats)
    return ATSType.UNKNOWN
```

---

## 10. Scoring Engine

### 10.1 Rules (configurable via `core/scoring/rules.py`)

```python
SCORING_RULES = {
    "title_keywords": {
        "positive": {
            "backend": 2.0,
            "software engineer": 2.0,
            "platform": 1.5,
            "fullstack": 1.0,
            "full stack": 1.0,
            "python": 1.5,
            "api": 1.0,
        },
        "negative": {
            "staff": -2.0,
            "principal": -3.0,
            "director": -3.0,
            "vp": -3.0,
            "intern": -5.0,
            "junior": -1.0,
        }
    },
    "description_keywords": {
        "fintech": 2.0,
        "financial": 1.5,
        "payments": 1.5,
        "banking": 1.0,
        "crypto": 1.0,
        "blockchain": 0.5,
        "trading": 1.0,
        "python": 1.0,
        "fastapi": 1.5,
        "django": 0.5,
        "aws": 0.5,
        "startup": 1.0,
        "series a": 1.5,
        "series b": 1.0,
        "seed": 1.0,
    },
    "location": {
        "new york": 2.0,
        "nyc": 2.0,
        "remote": 1.5,
        "hybrid": 1.0,
    },
}
```

### 10.2 Scorer

```python
def score_job(job: Job) -> tuple[float, dict]:
    breakdown = {}
    total = 0.0

    # Title scoring
    title_lower = job.title.lower()
    title_score = 0.0
    for keyword, weight in SCORING_RULES["title_keywords"]["positive"].items():
        if keyword in title_lower:
            title_score += weight
    for keyword, weight in SCORING_RULES["title_keywords"]["negative"].items():
        if keyword in title_lower:
            title_score += weight  # weight is already negative
    breakdown["title_match"] = title_score
    total += title_score

    # Description scoring
    if job.description:
        desc_lower = job.description.lower()
        desc_score = 0.0
        for keyword, weight in SCORING_RULES["description_keywords"].items():
            if keyword in desc_lower:
                desc_score += weight
        breakdown["description_keywords"] = desc_score
        total += desc_score

    # Location scoring
    if job.location:
        loc_lower = job.location.lower()
        loc_score = 0.0
        for keyword, weight in SCORING_RULES["location"].items():
            if keyword in loc_lower:
                loc_score += weight
                break  # Take first match
        breakdown["location"] = loc_score
        total += loc_score

    # Remote bonus
    if job.remote_flag:
        breakdown["remote"] = 1.5
        total += 1.5

    return total, breakdown
```

### 10.3 ATS Resume Matcher

After job scoring, the system automatically computes how well the operator's
resume matches each job posting using ATS-style keyword analysis.

#### Resume Parser

```python
# core/resumes/parser.py
import pdfplumber

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file."""
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)
```

#### Keyword Dictionary

```python
# core/resumes/keywords.py

SYNONYM_MAP = {
    "js": "javascript", "ts": "typescript", "k8s": "kubernetes",
    "postgres": "postgresql", "mongo": "mongodb", "gcp": "google cloud",
    "react.js": "react", "node.js": "nodejs", "vue.js": "vue",
}

TECH_KEYWORDS = {
    "languages": {"python", "javascript", "typescript", "go", "java", "rust", "ruby", "c++", "scala", "kotlin", "swift"},
    "frameworks": {"fastapi", "django", "flask", "react", "nextjs", "express", "spring", "rails", "angular", "vue"},
    "databases": {"postgresql", "mysql", "mongodb", "redis", "elasticsearch", "dynamodb", "cassandra", "sqlite"},
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

#### ATS Match Scorer

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

The `ats_match_score` and `ats_match_breakdown_json` are stored on the `jobs` table
(see §7.2). This data is displayed alongside the job score in the UI and feeds into
the resume tailoring engine.

---

## 11. Resume Manager

### V1: Copy Base Resume + ATS Tailoring

```python
async def prepare_resume(job_id: UUID, base_resume_path: str, artifact_dir: str) -> Artifact:
    """
    Prepare resume for a job application.
    If RESUME_TAILOR_ENABLED and ATS match data exists, produce a tailored resume.
    Otherwise, copy the base resume as-is.
    """
    job_dir = Path(artifact_dir) / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    # Load job from DB for ATS match data
    job = get_job(job_id)
    tailored = False

    if RESUME_TAILOR_ENABLED and job.ats_match_breakdown_json:
        try:
            resume_text = extract_text_from_pdf(base_resume_path)
            master_skills = load_master_skills(MASTER_SKILLS_PATH)
            tailored_text = tailor_resume(
                resume_text=resume_text,
                ats_breakdown=job.ats_match_breakdown_json,
                master_skills=master_skills,
                job_description=job.description or "",
            )
            dest_filename = f"tailored_resume_{timestamp}.pdf"
            dest_path = job_dir / dest_filename
            generate_pdf(tailored_text, dest_path)  # text → PDF
            tailored = True
        except Exception:
            logger.warning("Tailoring failed, falling back to base resume copy")

    if not tailored:
        dest_filename = f"resume_{timestamp}.pdf"
        dest_path = job_dir / dest_filename
        shutil.copy2(base_resume_path, dest_path)

    artifact = Artifact(
        job_id=job_id,
        kind=ArtifactKind.PDF,
        filename=dest_filename,
        path=str(dest_path.relative_to(artifact_dir)),
        size_bytes=dest_path.stat().st_size,
        meta_json={"tailored": tailored, "ats_match_score": job.ats_match_score},
    )
    return artifact
```

### Resume Tailor Engine (V1: Rule-Based)

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
         missing skills the operator actually has (from master_skills).
      3. Experience bullets: reorder within each role to prioritize bullets
         containing JD keywords. No rewriting — just reordering.
      4. Summary line: inject top 3 missing JD keywords if not already present.
      5. Return modified text (caller generates PDF).
    Falls back to original resume_text on any error.
    """
    missing = set(ats_breakdown.get("skills_missing", []))
    addable = missing & {normalize_keyword(s) for s in master_skills}
    # ... section parsing, reordering, keyword injection ...
    return modified_text
```

---

## 12. Browser Automation (Playwright)

### 12.1 Runner Orchestration

```python
async def apply_job(job_id: UUID) -> None:
    """Main entry point for browser-based job application."""
    # 1. Load job from DB
    # 2. Create application record (status=STARTED)
    # 3. Prepare resume artifact
    # 4. Launch Playwright with persistent profile
    # 5. Navigate to apply_url (or url if no apply_url)
    # 6. Detect ATS type from page (confirm/override URL-based detection)
    # 7. Dispatch to ATS handler
    # 8. Handle result:
    #    - Success → application.status=SUBMITTED, job.status=APPLIED, notify success
    #    - Block → create intervention, notify
    #    - Error → application.status=FAILED, job.status=APPLY_FAILED, save error artifact
```

### 12.2 Persistent Profile

```python
with sync_playwright() as p:
    if SIMPLIFY_ENABLED:
        ext_path = Path(SIMPLIFY_EXTENSION_PATH).resolve()
        profile_dir = Path(SIMPLIFY_PROFILE_DIR).resolve()
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chromium",
            headless=not PLAYWRIGHT_HEADFUL,
            slow_mo=PLAYWRIGHT_SLOW_MO_MS,
            args=[
                "--disable-blink-features=AutomationControlled",
                f"--disable-extensions-except={ext_path}",
                f"--load-extension={ext_path}",
            ],
        )
        sw = context.service_workers[0] if context.service_workers else context.wait_for_event(
            "serviceworker", timeout=5000
        )
        extension_id = sw.url.split("/")[2]
    else:
        profile_dir = Path(PROFILE_DIR) / PLAYWRIGHT_PROFILE_NAME
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=not PLAYWRIGHT_HEADFUL,
            slow_mo=PLAYWRIGHT_SLOW_MO_MS,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )

    page = context.new_page()
    page.set_default_timeout(PLAYWRIGHT_TIMEOUT_MS)
```

The extension path and profile path are configured via env vars (`SIMPLIFY_EXTENSION_PATH`, `SIMPLIFY_PROFILE_DIR`), not hardcoded in code.
The apply runner uses the persistent Simplify profile only when `SIMPLIFY_ENABLED=true`.
If extension detection fails, the apply run aborts before any ATS interaction.

### 12.3 CAPTCHA / Block Detectors

```python
DETECTOR_CHECKS = [
    {
        "name": "recaptcha",
        "reason": InterventionReason.CAPTCHA,
        "selectors": [
            'iframe[src*="recaptcha"]',
            'iframe[title*="reCAPTCHA"]',
            '#recaptcha',
            '.g-recaptcha',
        ],
    },
    {
        "name": "hcaptcha",
        "reason": InterventionReason.CAPTCHA,
        "selectors": [
            'iframe[src*="hcaptcha"]',
            '.h-captcha',
        ],
    },
    {
        "name": "cloudflare",
        "reason": InterventionReason.BLOCKED,
        "selectors": [
            '#challenge-running',
            '#challenge-stage',
            'iframe[src*="challenges.cloudflare.com"]',
        ],
        "text_patterns": [
            "checking your browser",
            "verify you are human",
            "just a moment",
        ],
    },
    {
        "name": "login_wall",
        "reason": InterventionReason.LOGIN_REQUIRED,
        "text_patterns": [
            "sign in to continue",
            "log in to apply",
            "create an account",
        ],
    },
]

async def detect_blocks(page: Page) -> DetectionResult | None:
    """Check page for CAPTCHA/MFA/block indicators. Returns first match or None."""
    page_text = (await page.text_content("body") or "").lower()

    for check in DETECTOR_CHECKS:
        # Check selectors
        for selector in check.get("selectors", []):
            if await page.query_selector(selector):
                return DetectionResult(
                    name=check["name"],
                    reason=check["reason"],
                )

        # Check text patterns
        for pattern in check.get("text_patterns", []):
            if pattern.lower() in page_text:
                return DetectionResult(
                    name=check["name"],
                    reason=check["reason"],
                )

    return None
```

### 12.4 Artifact Capture

```python
async def capture_artifacts(
    page: Page, job_id: UUID, application_id: UUID, artifact_dir: str
) -> tuple[Artifact, Artifact]:
    """Capture screenshot + HTML snapshot of current page state."""
    job_dir = Path(artifact_dir) / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    # Screenshot
    ss_filename = f"screenshot_{timestamp}.png"
    ss_path = job_dir / ss_filename
    await page.screenshot(path=str(ss_path), full_page=True)

    # HTML
    html_filename = f"page_{timestamp}.html"
    html_path = job_dir / html_filename
    html_content = await page.content()
    html_path.write_text(html_content, encoding="utf-8")

    # Create artifact records
    ss_artifact = Artifact(job_id=job_id, application_id=application_id,
                           kind=ArtifactKind.SCREENSHOT, filename=ss_filename,
                           path=str(ss_path.relative_to(artifact_dir)),
                           size_bytes=ss_path.stat().st_size)

    html_artifact = Artifact(job_id=job_id, application_id=application_id,
                             kind=ArtifactKind.HTML, filename=html_filename,
                             path=str(html_path.relative_to(artifact_dir)),
                             size_bytes=html_path.stat().st_size)

    return ss_artifact, html_artifact
```

### 12.5 Intervention Creation

When a block is detected:

```python
async def create_intervention(
    job_id: UUID,
    application_id: UUID,
    reason: InterventionReason,
    last_url: str,
    screenshot_artifact_id: UUID,
    html_artifact_id: UUID,
) -> Intervention:
    intervention = Intervention(
        job_id=job_id,
        application_id=application_id,
        status=InterventionStatus.OPEN,
        reason=reason,
        last_url=last_url,
        screenshot_artifact_id=screenshot_artifact_id,
        html_artifact_id=html_artifact_id,
    )
    # Save to DB
    # Update job.status = INTERVENTION_REQUIRED
    # Update application.status = INTERVENTION_REQUIRED
    # Send push notification
    await send_intervention_notification(intervention)
    return intervention
```

---

### 12.6 Simplify Runtime Guardrails

- A profile lock is required before launching Chromium (`one persistent profile, one apply run at a time`).
- Runner milestones must emit screenshot/log artifacts at:
  - browser launched
  - extension detected
  - job page opened
  - apply button clicked
  - resume uploaded
  - autofill completed
  - submission page reached or blocked
- Resume upload remains JobBot-owned: generate tailored resume artifact first, then upload that file directly to ATS file inputs.

---

## 13. Push Notifications

### Pushover Implementation

```python
import httpx

async def send_pushover(title: str, message: str, url: str | None = None) -> bool:
    async with httpx.AsyncClient() as client:
        payload = {
            "token": PUSHOVER_TOKEN,
            "user": PUSHOVER_USER,
            "title": title,
            "message": message,
            "priority": 0,
        }
        if url:
            payload["url"] = url
            payload["url_title"] = "Open in JobBot"

        response = await client.post("https://api.pushover.net/1/messages.json", data=payload)
        return response.status_code == 200
```

### Notification Events

| Event | Title | Message | URL |
|-------|-------|---------|-----|
| Intervention created | "⚠️ Intervention Needed" | `{job.title} at {job.company_name_raw} — {reason}` | `{UI_BASE_URL}/interventions/{id}` |
| Apply success | "✅ Applied Successfully" | `{job.title} at {job.company_name_raw}` | `{UI_BASE_URL}/jobs/{job_id}` |
| Apply failed | "❌ Apply Failed" | `{job.title} — {error_text[:100]}` | `{UI_BASE_URL}/jobs/{job_id}` |
| Scrape complete | "📋 Scrape Complete" | `{source}: {inserted} new jobs, {duplicates} duplicates` | `{UI_BASE_URL}/jobs?status=NEW` |

---

## 14. Celery Tasks

### 14.1 Task Definitions

```python
# apps/worker/tasks/scrape.py
@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def scrape_jobspy(self, query=None, location=None, hours_old=None, results_wanted=None):
    """Scrape JobSpy sources, store jobs, trigger scoring."""

# apps/worker/tasks/score.py
@celery_app.task
def score_jobs(job_ids: list[str] | None = None):
    """Score all NEW jobs or specific job_ids. Update status to SCORED."""

# apps/worker/tasks/ats_match.py
@celery_app.task
def ats_match_resume(job_ids: list[str] | None = None):
    """Compute ATS resume match score for SCORED jobs. Runs after score_jobs.
    Parses base resume once (cached), then compares against each job's description."""

# apps/worker/tasks/apply.py
@celery_app.task(bind=True, max_retries=1, default_retry_delay=120)
def apply_job(self, job_id: str):
    """Prepare resume, launch Playwright, attempt application."""

# apps/worker/tasks/resume.py
@celery_app.task
def prepare_resume(job_id: str):
    """Copy base resume into artifacts. Returns artifact_id."""

# apps/worker/tasks/notify.py
@celery_app.task
def send_notification(title: str, message: str, url: str | None = None):
    """Send push notification via configured provider."""
```

### 14.2 Task Chains

```
Scrape flow:  scrape_jobspy → score_jobs → ats_match_resume → send_notification (scrape summary)
Apply flow:   apply_job → (prepare_resume [+ tailor] → browser apply → handle result → send_notification)
```

---

## 15. UI Requirements

### 15.1 Pages

**Jobs Page (`/ui/jobs`)**
- Table with columns: Title, Company, Source, Score, Status, Scraped At
- Filters: status dropdown, source dropdown, search text, min score slider
- Row actions: Approve, Reject, Queue Apply (contextual by status)
- Bulk actions: Select multiple → Bulk Approve / Bulk Reject
- Click row → navigate to Job Detail

**Job Detail Page (`/ui/jobs/:id`)**
- Full job description (rendered HTML or plain text)
- Score breakdown visualization
- Company info sidebar
- Applications history table
- Artifacts list (downloadable)
- Action buttons (Approve / Reject / Queue Apply)
- Link to intervention if exists

**Applications Page (`/ui/applications`)**
- Table: Job Title, Company, Status, Method, Started At, Finished At
- Filter by status
- Click → shows error details, fields submitted, linked artifacts

**Interventions Page (`/ui/interventions`)**
- Card layout (not table) for better screenshot preview
- Each card shows: Job title, Reason badge, Screenshot thumbnail, Created At
- Actions: Resolve (with optional notes), Abort, Retry Apply
- Filter: OPEN (default), RESOLVED, ABORTED
- Open count badge in navigation

**Scrape Runs Page (`/ui/runs`)**
- Table: Source, Status, Started At, Duration, Stats (fetched/inserted/duplicates)
- "Run Scrape Now" button

**Settings Page (`/ui/settings`)** (V1 minimal)
- View current env config (read-only display)
- Scoring rules viewer

### 15.2 Design Requirements

- **Mobile-responsive**: Must work on phone screen (intervention review use case)
- **Dark mode**: Not required V1
- **Loading states**: Skeleton loaders for all data fetches
- **Error states**: Toast notifications for API errors
- **Real-time**: Intervention count badge updates via polling (every 15s) or WebSocket

---

## 16. Docker Compose

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: jobbot
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

---

## 17. Error Handling Philosophy

1. **Scrapers**: Errors are logged to `scrape_runs.error_text` and the run is marked FAILED. Other scrapers continue. Never crash the worker.
2. **Scoring**: If scoring fails for a job, log it, skip it, continue others.
3. **Browser worker**: All exceptions are caught. On failure: save screenshot + error trace as artifacts, set application to FAILED, set job to APPLY_FAILED, send push.
4. **CAPTCHA/MFA**: Not an error — it's an expected state. Create intervention, notify, stop gracefully.
5. **API**: Return proper HTTP status codes. 400 for bad input, 404 for not found, 409 for invalid state transition, 500 for unexpected errors.
6. **Missing directories**: Auto-create `ARTIFACT_DIR` and `PROFILE_DIR` subdirectories on startup.

---

## 18. Future Extensions (Backlog)

These are explicitly planned but NOT implemented in V1. The architecture MUST NOT block them.

### A) Additional Scrapers
- BuiltInNYC (Python Playwright or Node wrapper)
- Wellfound (API + auth cookies)
- YC Work at a Startup (`ycombinator-scraper` PyPI package)
- Seed-stage boards, Slack job feeds, RSS ingestion
- "Import jobs" endpoint for manual URL submission

### B) Application Automation Coverage
- Robust ATS field mapping per platform
- Canonical applicant profile JSON
- EEO / demographic / work-auth answer pack
- Workday full integration
- YC WorkAtAStartup custom apply flow

### C) Resume Tailoring Engine (V2 — LLM Enhancement)
- LLM-powered bullet rewriting (beyond V1 rule-based reordering)
- DOCX/LaTeX template → PDF generation with rich formatting
- Version tracking + diff view in UI (before/after comparison)
- A/B testing of tailored vs. base resume outcomes

### D) CAPTCHA / Intervention Improvements
- noVNC live browser takeover (VM mode)
- Expanded detector heuristics (Akamai, PerimeterX)
- Buster extension in operator profile
- NopeCHA behind domain allowlist (optional)

### E) Apollo Enrichment
- Company enrichment (domain, headcount, stage, funding)
- Contact discovery (recruiter/HM signals)
- Outreach draft generator
- Gmail API send with approval

### F) Scheduling + Reliability
- Celery Beat for nightly scrapes
- Per-source concurrency limits
- Retry backoff for failed applies
- Daily digest push notification

### G) Security + Deployment
- Basic auth for UI/API
- HTTPS via Caddy/Nginx on VM
- Docker compose for full stack (api + worker + browser + noVNC)
- Tailscale for secure phone access to local dev

### H) Jira-Based Resume Generation
- Import a PDF or Markdown file listing completed Jira stories (story title + description + acceptance criteria)
- Parse stories into structured experience entries (action, tech stack, impact)
- Cross-reference with target job posting's ATS keywords
- Generate role-specific bullet points that reflect actual work done
- Combine with ATS optimization to produce highly targeted, experience-accurate resumes
- Uses the same `core/resumes/tailor.py` infrastructure — Jira stories become an enriched "master experience" source
- New module: `core/resumes/jira_import.py`

### I) OpenClaw Integration
- OpenClaw tool plugin calls same FastAPI endpoints
- Approve/reject/queue via Telegram/WhatsApp DM
- Daily digest via messaging channel
- Cron-triggered scrapes

---

## 19. Development Commands

```bash
# Start infrastructure
docker compose up -d

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Bootstrap Simplify login once (headed).
# Reads Settings() from .env; run from repo root so relative .env loading works.
python scripts/bootstrap_simplify.py

# Start API server
uvicorn apps.api.main:app --reload --port 8000

# Start Celery worker
celery -A apps.worker.celery_app worker -l info -Q default,scrape,apply -c 1

# Start Celery beat (optional, for scheduled tasks)
celery -A apps.worker.celery_app beat -l info

# Start UI dev server
cd ui && npm install && npm run dev

# Trigger a scrape manually
curl -X POST http://localhost:8000/api/jobs/run-scrape

# Or use the script
python scripts/run_scrape_once.py
```
