# JobBot — System Architecture

> **Purpose**: This document describes how all components connect, data flows
> through the system, and where extension points exist. Read this alongside
> `SPEC.md` for the full picture.

---

## 1. High-Level Component Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│  OPERATOR (You)                                                       │
│  • Phone (push notifications + mobile UI)                             │
│  • Laptop (full UI + browser worker visible)                          │
└───────────┬───────────────────────────────────────┬───────────────────┘
            │ HTTP / WS                              │ Push (Pushover/ntfy)
            ▼                                        │
┌───────────────────────────┐                        │
│  FastAPI  (apps/api/)     │◄───────────────────────┘
│                           │
│  REST:  /api/jobs         │
│         /api/applications │
│         /api/interventions│
│         /api/artifacts    │
│         /api/runs         │
│  WS:    /ws/logs          │
│  Static: /ui/* (React)    │
└─────────┬─────────────────┘
          │ DB reads/writes
          ▼
┌───────────────────────────┐
│  PostgreSQL               │
│                           │
│  companies                │
│  jobs                     │
│  scrape_runs              │
│  applications             │
│  artifacts                │
│  interventions            │
└───────────────────────────┘
          ▲
          │ DB reads/writes
┌─────────┴─────────────────┐       ┌───────────────────────────┐
│  Celery Workers           │◄──────│  Redis (broker + backend) │
│  (apps/worker/)           │       └───────────────────────────┘
│                           │
│  Queues:                  │
│   • default (scoring,     │
│     notifications)        │
│   • scrape (scraper tasks)│
│   • apply (browser tasks) │
│                           │
│  Tasks:                   │
│   • scrape_jobspy         │
│   • score_jobs            │
│   • ats_match_resume      │
│   • apply_job             │
│   • prepare_resume        │
│   • (tailor_resume)       │
│   • send_notification     │
└─────────┬─────────────────┘
          │ (apply tasks only)
          ▼
┌───────────────────────────┐
│  Playwright Worker        │
│  (apps/browser/)          │
│                           │
│  Chromium (headful)       │
│  Persistent profile       │
│  ATS handlers:            │
│   • Greenhouse            │
│   • Lever                 │
│   • Ashby                 │
│   • Workday (→ intervene) │
│   • YC (→ intervene)      │
│                           │
│  Detectors:               │
│   • reCAPTCHA             │
│   • hCAPTCHA              │
│   • Cloudflare            │
│   • Login wall            │
└───────────────────────────┘
```

---

## 2. Data Flow: Scrape → Score → Approve → Apply

```
  ┌─────────┐    POST /api/jobs/run-scrape
  │ Operator │──────────────────────────────────┐
  │ (UI)     │                                   │
  └─────────┘                                   ▼
                                        ┌───────────────┐
                                        │ FastAPI        │
                                        │ enqueue task   │
                                        └───────┬───────┘
                                                │
                                                ▼
                                   ┌────────────────────────┐
                                   │ Celery: scrape_jobspy  │
                                   │                        │
                                   │ 1. Create scrape_run   │
                                   │ 2. Call JobSpy         │
                                   │ 3. Normalize results   │
                                   │ 4. Compute dedup_hash  │
                                   │ 5. Upsert companies    │
                                   │ 6. Insert new jobs     │
                                   │ 7. Update scrape_run   │
                                   │ 8. Enqueue score_jobs  │
                                   └────────────┬───────────┘
                                                │
                                                ▼
                                   ┌────────────────────────┐
                                   │ Celery: score_jobs     │
                                   │                        │
                                   │ For each NEW job:      │
                                   │ 1. Apply scoring rules │
                                   │ 2. Set score_total     │
                                   │ 3. Set breakdown JSON  │
                                   │ 4. Status → SCORED     │
                                   │ 5. Notify scrape done  │
                                   └────────────────────────┘
                                                │
                                                ▼
                                   ┌────────────────────────┐
                                   │ Celery: ats_match      │
                                   │                        │
                                   │ For each SCORED job:   │
                                   │ 1. Parse resume PDF    │
                                   │ 2. Extract JD keywords │
                                   │ 3. Compute ATS match   │
                                   │ 4. Set ats_match_score │
                                   │ 5. Store breakdown     │
                                   └────────────────────────┘
                                                │
                                                ▼
                                   ┌────────────────────────┐
                                   │ UI: Jobs Page          │
                                   │                        │
                                   │ Operator reviews jobs  │
                                   │ Approve / Reject       │
                                   └────────────┬───────────┘
                                                │ POST .../approve
                                                │ POST .../queue-apply
                                                ▼
                                   ┌────────────────────────┐
                                   │ Celery: apply_job      │
                                   │                        │
                                   │ 1. Create application  │
                                   │ 2. Prepare resume      │
                                   │ 3. Launch Playwright   │
                                   │ 4. Navigate to URL     │
                                   │ 5. Detect ATS type     │
                                   │ 6. Check for blocks    │
                                   │                        │
                                   │ Branch A: Submit OK    │
                                   │  → SUBMITTED + APPLIED │
                                   │  → Push: success       │
                                   │                        │
                                   │ Branch B: Blocked      │
                                   │  → Screenshot + HTML   │
                                   │  → Intervention OPEN   │
                                   │  → Push: intervene     │
                                   │                        │
                                   │ Branch C: Error        │
                                   │  → FAILED              │
                                   │  → Push: failure       │
                                   └────────────────────────┘
```

---

## 3. State Machine: Job Lifecycle

```
              ┌──────┐
              │ NEW  │ ← Scraped from source
              └──┬───┘
                 │ score_jobs task
                 ▼
              ┌──────────┐
              │ SCORED   │ ← Score computed, awaiting review
              └──┬───┬───┘
                 │   │
     approve     │   │  reject
                 ▼   ▼
         ┌──────────┐ ┌──────────┐
         │ APPROVED │ │ REJECTED │ (terminal)
         └──┬───────┘ └──────────┘
            │ queue-apply
            ▼
    ┌───────────────┐
    │ APPLY_QUEUED  │ ← Celery task enqueued
    └──┬────────┬───┘
       │        │
  success     blocked/error
       │        │
       ▼        ▼
  ┌─────────┐ ┌───────────────────────┐
  │ APPLIED │ │ INTERVENTION_REQUIRED │ ← or APPLY_FAILED
  └─────────┘ └───────────┬───────────┘
               (terminal)  │
                           │ retry-apply
                           ▼
                   ┌───────────────┐
                   │ APPLY_QUEUED  │ (re-enter apply flow)
                   └───────────────┘
```

---

## 4. State Machine: Application Lifecycle

```
  ┌─────────┐
  │ STARTED │ ← Browser worker begins
  └──┬──┬───┘
     │  │
 ok  │  │ blocked
     ▼  ▼
┌───────────┐ ┌───────────────────────┐
│ SUBMITTED │ │ INTERVENTION_REQUIRED │
└───────────┘ └───────────────────────┘
                      │
              ┌───────┐ ┌──────────┐
              │FAILED │ │ SKIPPED  │ ← operator aborted
              └───────┘ └──────────┘
```

---

## 5. State Machine: Intervention Lifecycle

```
  ┌──────┐
  │ OPEN │ ← Block detected
  └──┬───┘
     │
  ┌──┴──────────┐
  │              │
  ▼              ▼
┌──────────┐ ┌─────────┐
│ RESOLVED │ │ ABORTED │
└──────────┘ └─────────┘
```

---

## 6. Celery Queue Architecture

```
Redis Broker
  │
  ├── Queue: "default"
  │   ├── score_jobs
  │   ├── ats_match_resume
  │   └── send_notification
  │
  ├── Queue: "scrape"
  │   └── scrape_jobspy
  │
  └── Queue: "apply"
      ├── apply_job
      └── prepare_resume
```

**Worker startup command**:
```bash
celery -A apps.worker.celery_app worker -l info -Q default,scrape,apply -c 1
```

The apply pipeline is serialized by design:
- one worker process
- one persistent browser profile
- one application run at a time (profile lock)

---

## 7. File Storage Layout

```
storage/
├── artifacts/
│   ├── {job_uuid}/
│   │   ├── resume_20260301_143022.pdf
│   │   ├── screenshot_20260301_143055.png
│   │   └── page_20260301_143055.html
│   └── {another_job_uuid}/
│       └── ...
│
└── profiles/
    └── simplify-profile/           # Simplify persistent Chromium profile
        ├── Default/
        │   ├── Cookies
        │   ├── Local Storage/
        │   └── ...
        └── .profile.lock           # Prevents concurrent apply runs on same profile
```

---

## 8. Notification Flow

```
Event occurs in worker
  │
  ▼
send_notification task enqueued
  │
  ▼
┌─────────────────────────┐
│ Notification dispatcher │
│                         │
│ if PUSH_PROVIDER == "pushover":
│   → POST https://api.pushover.net/1/messages.json
│     body: { token, user, title, message, url }
│                         │
│ elif PUSH_PROVIDER == "ntfy":
│   → POST {NTFY_TOPIC_URL}
│     body: message
│     headers: Title, Click (URL)
│                         │
│ elif PUSH_PROVIDER == "none":
│   → log only            │
└─────────────────────────┘
  │
  ▼
Push arrives on operator's phone
  → Deep link: {UI_BASE_URL}/interventions/{id}
  → Tap → opens mobile UI → see screenshot → take action
```

---

## 9. Intervention Workflow (Detailed)

```
Playwright navigates to apply_url
  │
  ▼
detectors.detect_blocks(page)
  │
  ├── None (no block) → continue ATS handler flow
  │
  └── DetectionResult found
      │
      ▼
  ┌────────────────────────────────────┐
  │ 1. page.screenshot() → artifact   │
  │ 2. page.content() → html artifact │
  │ 3. INSERT intervention (OPEN)     │
  │ 4. UPDATE job status              │
  │ 5. UPDATE application status      │
  │ 6. Enqueue send_notification      │
  │ 7. Close page gracefully          │
  └────────────────────────┬───────────┘
                           │
                           ▼
  ┌────────────────────────────────────┐
  │ Operator receives push             │
  │ Opens /ui/interventions/{id}       │
  │                                    │
  │ Sees:                              │
  │  - Job title + company             │
  │  - Reason badge (CAPTCHA/MFA/etc)  │
  │  - Screenshot preview              │
  │  - Last URL                        │
  │                                    │
  │ Actions:                           │
  │  [Resolve] → status=RESOLVED      │
  │  [Abort]   → status=ABORTED       │
  │             → job=APPLY_FAILED     │
  │  [Retry]   → new application      │
  │             → re-enqueue apply_job │
  └────────────────────────────────────┘
```

---

## 9.1 Simplify Extension Bootstrap + Runtime Check

1. Set Simplify env vars in `.env`: `SIMPLIFY_ENABLED`, `SIMPLIFY_EXTENSION_PATH`, `SIMPLIFY_PROFILE_DIR`.
2. Run `python scripts/bootstrap_simplify.py` once (from repo root). The script reads `Settings()` / `.env` values.
3. Apply runs reuse the same persistent Simplify profile only when `SIMPLIFY_ENABLED=true` (profile lock still enforces one run at a time per profile).
4. Before ATS flow starts, runner must detect the extension service worker; if extension detection fails, abort apply flow and mark application as failed.

The extension path and profile path are environment-configured, not code-configured.

---

## 10. Extension Points (for future work)

### 10.1 Adding a New Scraper

1. Create `core/scraping/new_source.py` implementing `BaseScraper`.
2. Add `NEW_SOURCE_ENABLED=true` to `.env`.
3. Add feature flag check in `apps/worker/tasks/scrape.py`.
4. Add `JobSource.NEW_SOURCE` enum value.
5. No other files need to change.

### 10.2 Adding a New ATS Handler

1. Create `apps/browser/ats/new_ats.py` implementing `BaseATSHandler`.
2. Add URL patterns to `ATS_URL_PATTERNS` in `detectors.py`.
3. Add `ATSType.NEW_ATS` enum value.
4. Register in `runner.py` dispatcher.

### 10.3 Adding OpenClaw Later

OpenClaw tools call the same REST API:
```
OpenClaw Tool: "approve_job"
  → POST /api/jobs/{id}/approve
  → Returns: { status: "APPROVED" }

OpenClaw Tool: "list_pending_jobs"
  → GET /api/jobs?status=SCORED&min_score=3&per_page=10
  → Returns: job list

OpenClaw Tool: "run_scrape"
  → POST /api/jobs/run-scrape
  → Returns: { run_id: "..." }
```

No engine changes required. OpenClaw is a client of the API.

### 10.4 Jira-Based Resume Generation (Future)

1. Operator provides a PDF or Markdown file listing completed Jira stories.
2. New module `core/resumes/jira_import.py` parses stories into structured experience entries.
3. ATS scorer identifies keywords from target job posting.
4. Resume generator combines real Jira-sourced experience with ATS keyword alignment.
5. Produces a resume that is both ATS-optimized and experience-accurate.
6. Integrates with existing `tailor.py` — the Jira stories become an enriched "master experience" source.
7. No changes to pipeline or DB schema needed — uses the same artifact + tailor infrastructure.

### 10.5 Adding noVNC (VM mode)

1. Add `novnc` service to `docker-compose.yml`.
2. Run browser worker inside a container with Xvfb display.
3. Expose noVNC at `/novnc/` behind auth.
4. In intervention UI, add "Open Live Session" button linking to noVNC.
5. No changes to worker logic — the browser just happens to run inside the container.

---

## 11. Security Considerations (V1 Minimal)

- No auth on API/UI in V1. Acceptable for local-only development.
- `.env` file must be in `.gitignore`.
- Browser profile directory contains cookies — do not commit.
- Artifact directory may contain PII from job descriptions — do not commit.
- Push notification tokens are secrets — use `.env` only.
- When moving to VM: add basic auth middleware or Tailscale for network-level auth.

---

## 12. Performance Notes

- JobSpy scrapes are I/O-bound (network). One scrape task at a time is fine.
- Scoring is CPU-bound but trivial (string matching). Batch scoring is milliseconds.
- Browser automation is inherently slow (page loads, form interactions). One apply at a time.
- Postgres can handle thousands of jobs without optimization concerns.
- Redis pub/sub for WebSocket log broadcasting is sufficient for single-user.

---

## 13. Local Development Topology

```
Your Laptop
├── Docker: Postgres (port 5432)
├── Docker: Redis (port 6379)
├── Process: FastAPI (port 8000) — serves API + optional static UI build
├── Process: Celery worker (connects to Redis + Postgres)
├── Process: Vite dev server (port 5173) — React UI with HMR
└── Process: Chromium (launched by Playwright, visible on screen)
```

### VM Deployment Topology (Future)

```
Ubuntu VM
├── Docker: Postgres
├── Docker: Redis
├── Docker: FastAPI + built UI
├── Docker: Celery worker
├── Docker: Chromium + Xvfb + noVNC (port 6080)
├── Docker: Caddy (reverse proxy, TLS)
└── Tailscale (secure phone access)
```

Same `docker-compose.yml`, extended with browser + proxy services.
