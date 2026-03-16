# JobBot System Specification and Architecture

**v1 implementation:** Redis + Celery workers, React + Vite UI, deterministic scoring, rules-based persona classifier, grounded inventory-driven resume generation, GCS/local artifact storage. No LLM dependency. Manual review and manual apply only.

## 1. Executive Summary
JobBot is an automated pipeline designed to streamline the job search process for software engineers. Instead of blindly applying to jobs, JobBot focuses on high-quality discovery, evaluation, and preparation. It ingests job listings from various sources, scores them for relevance, classifies them into targeted professional personas, and generates highly tailored resumes optimized for Applicant Tracking Systems (ATS). The user is then presented with a curated list of high-value opportunities and ready-to-use application artifacts, leaving the final manual application step to the user.

## 2. Product Scope
The system is responsible for:
- **Job Ingestion:** Collecting job listings from ATS APIs (Greenhouse, Lever, etc.) and scraping tools.
- **Duplicate Detection:** Identifying and merging duplicate job postings across different sources.
- **Job Scoring:** Evaluating roles based on title, seniority, domain, location, and tech stack relevance.
- **Persona Classification:** Categorizing jobs into predefined professional personas (e.g., Backend Engineer, Platform/Infrastructure Engineer, Hybrid).
- **ATS Resume Matching:** Extracting keywords and evaluating ATS compatibility.
- **Custom Resume Generation:** Producing tailored, downloadable resumes (PDF) emphasizing persona-relevant experience.
- **Review Interface:** Providing a UI for users to review jobs, scores, insights, and download generated artifacts.

## 3. Non-Goals
To maintain clear system boundaries and avoid brittleness, the following are explicitly out of scope:
- **Automated Job Application:** The system will *not* submit applications on behalf of the user.
- **Browser Automation:** Extension-based or headless browser flows for application submission are completely out of scope.
- **Interview Scheduling:** The system does not handle post-application communication or scheduling.

## 4. End-to-End System Flow
1. **Ingestion Cron:** Scheduled workers poll ATS APIs and scrapers to fetch raw job listings.
2. **Normalization & Deduplication:** Raw data is mapped to a canonical `Job` schema. The system checks against existing records to prevent duplicates.
3. **Scoring Pipeline:** The normalized job is passed through a deterministic scoring engine. Jobs below a configurable threshold are persisted for historical analysis and rule tuning, but are marked as `REJECTED` and hidden from the user.
4. **Classification & Analysis:** High-scoring jobs are analyzed to determine the best-fit persona and extract ATS keywords.
5. **Artifact Generation:** An asynchronous worker generates a tailored resume using the user's base experience inventory and the extracted job signals.
6. **Review & Action:** The user logs into the UI, reviews the curated job feed, downloads the tailored resume, and manually applies via the provided URL.

## 5. Core Domain Model
- **Job:** The canonical representation of a job posting (Title, Company, Location, Description, Apply URL).
- **Source:** The origin of the job data (e.g., Greenhouse, Lever, LinkedIn).
- **Persona:** A professional profile (e.g., Backend, Platform) containing specific skills, summaries, and experience highlights.
- **Experience Inventory:** The master database of the user's work history, achievements, and education.
- **JobAnalysis:** The result of the scoring, persona classification, and ATS keyword extraction for a specific job.
- **GeneratedArtifact:** A tailored resume (PDF) linked to a specific Job and Persona.

## 6. Job Lifecycle and State Machine
To prevent semantic confusion, the system explicitly separates system-managed pipeline states from user-managed workflow states.

### System Pipeline States (Managed by Workers)
- `INGESTED`: Raw data fetched and normalized.
- `DEDUPED`: Checked against existing records; duplicates merged.
- `SCORED`: Evaluated against heuristics.
- `REJECTED`: Score fell below the threshold; processing halts. The record is persisted for auditing but hidden from the UI.
- `CLASSIFIED`: Persona match determined.
- `ATS_ANALYZED`: Keywords extracted and gaps identified.
- `RESUME_READY`: Tailored artifact successfully generated.
- `FAILED`: Pipeline encountered an unrecoverable error.

### User Workflow States (Managed by User via UI)
- `NEW`: Job is ready for user review (typically requires `pipeline_status = RESUME_READY`).
- `SAVED`: User bookmarked the job for later.
- `APPLIED`: User manually submitted the application.
- `ARCHIVED`: User dismissed the job.

## 7. Data Model
The relational data model is designed for implementation precision, tracking provenance, model versions, and distinct statuses:

- `jobs`: `id`, `raw_company`, `raw_title`, `raw_location`, `normalized_company`, `normalized_title`, `normalized_location`, `description`, `apply_url`, `dedup_hash`, `pipeline_status` (enum), `user_status` (enum), `created_at`, `updated_at`
  - *Constraints/Indexes:* `UNIQUE INDEX (dedup_hash)`, `INDEX (pipeline_status)`, `INDEX (user_status)`
- `job_sources`: `job_id`, `source_name`, `external_id`, `raw_data`, `provenance_metadata` (JSON: fetch timestamp, source URL, scraper version)
  - *Constraints/Indexes:* `UNIQUE INDEX (source_name, external_id)`
- `job_scores`: `job_id`, `total_score`, `seniority_score`, `tech_stack_score`, `location_score`, `persona_specific_scores` (JSON), `run_id`, `model_version`
- `job_analyses`: `job_id`, `matched_persona`, `missing_keywords`, `ats_compatibility_score`, `run_id`, `model_version`, `prompt_version`
- `personas`: `id`, `name`, `configuration`
- `experience_items`: `id`, `company`, `role`, `bullet_points`, `associated_personas`
- `artifacts`: `id`, `job_id`, `persona_id`, `file_url`, `format`, `version`, `prompt_version`, `template_version`, `created_at`

## 8. Ingestion Architecture
Ingestion is handled by a set of modular **Connectors** written in Python. Each connector implements a standard interface:
- `fetch_jobs()`: Retrieves raw data from the source.
- `normalize(raw_job)`: Maps source-specific fields to the canonical `Job` schema.
Connectors run on a scheduled basis via a task queue. Raw payloads are stored in a JSONB column in PostgreSQL for debugging and replayability before normalization.

## 9. Deduplication Strategy
Deduplication occurs immediately after normalization. The `dedup_hash` serves as the canonical uniqueness mechanism at the database level. The strategy relies on:
1. **Exact URL Matching:** If the apply URL matches an existing job.
2. **Deterministic Hashing (Canonical):** A composite hash of `lowercase(normalized_company) + lowercase(normalized_title) + normalized_location` (stored in the `dedup_hash` column with a unique constraint). This is the primary mechanism preventing duplicate inserts.
3. **Fuzzy Matching (Secondary Assist):** For edge cases, a similarity score using PostgreSQL `pg_trgm` trigram similarity on the company and title is computed. This is not a hard constraint, but a secondary assist used for pre-insert conflict detection or to flag potential duplicates for manual operator review.

## 10. Scoring System Design (v1)
The scoring system uses a deterministic weighted heuristic (five factors, 0–100 each) implemented in Python. All keyword matching uses word-boundary-aware helpers in `core/matching.py` (avoids false positives like "java" in "javascript").
- **Title Relevance (25%):** Matches against target titles (e.g., "Senior Software Engineer").
- **Seniority Match (20%):** Penalizes roles that are too junior or excessively senior.
- **Domain Alignment (20%):** Keyword matching for industry/vertical (fintech, startup, etc.).
- **Location/Remote (20%):** High score for "Remote", lower for incompatible geographic locations.
- **Tech Stack (15%):** Overlap between job description tech keywords and user's `master_skills`.
Jobs scoring below a defined threshold (e.g., 60/100) are marked as `REJECTED` in the pipeline and skip downstream processing.

## 11. Persona Classification System (v1)
The v1 classifier is **rules-based and deterministic** (no LLM). It implements a `PersonaClassifier` interface; an optional LLM provider may be added in the future.
- **Backend Engineer:** Triggered by title signals and keyword matches (API, databases, business logic, backend languages).
- **Platform / Infrastructure Engineer:** Triggered by infra keywords (Kubernetes, CI/CD, AWS/GCP, observability).
- **Hybrid:** Fallback when signals are mixed or ambiguous.
Uses word-boundary-aware matching via `core/matching.py` for title and description keywords. The selected persona dictates which subset of the `Experience Inventory` is prioritized during resume generation.

## 12. Resume Generation Architecture (v1)
v1 has exactly one resume-generation path: experience inventory → grounded selection → deterministic HTML → Playwright PDF → artifact storage. No other path (e.g., base-resume parsing or LLM rewriting) is supported.

1. **Data Assembly:** The system gathers the `JobAnalysis`, the selected `Persona`, and the structured `Experience Inventory` (YAML).
2. **Content Selection:** Grounded selection chooses roles, projects, and bullets from the inventory by keyword overlap and persona-tag matching. No freeform LLM output; all content is from the inventory. v1 uses a conservative/no-op rewrite—bullets are used as-is; no invented experience.
3. **Formatting:** Selected content is injected into a deterministic HTML template.
4. **Rendering:** Playwright (invoked from Python via `playwright.sync_api`) renders the HTML to PDF. v1 outputs PDF only; DOCX is deferred to a future iteration.

## 13. Artifact Storage Strategy (v1)
Generated resumes are stored on the local filesystem by default (`storage/artifacts/` or `ARTIFACT_DIR`).
- Artifacts are keyed by `job_id` and timestamp.
- The database `artifacts` table stores metadata and `path` (storage key). `file_url` is nullable and optional; GCS-backed artifacts do not persist URLs.
- **Local:** Files served directly via `FileResponse`.
- **GCS:** Objects remain private. Preview/download routes generate signed URLs on demand using Application Default Credentials (ADC). Local dev: `gcloud auth application-default login` or `GOOGLE_APPLICATION_CREDENTIALS`; deployed: attached service account.
- No duplicate prefixing: producers pass relative keys; backends apply the configured prefix exactly once.

*Future: CDN links, lifecycle policies for automated cleanup.*

## 14. API Design
The backend exposes a RESTful API built with **FastAPI (Python)** for the frontend:
- `GET /api/jobs`: List jobs with filtering (user_status, score, persona). Excludes REJECTED by default; use `include_rejected=true` for debugging.
- `GET /api/jobs/{id}`: Retrieve full job details, analysis, and scores. Returns 404 for REJECTED jobs unless `include_rejected=true`. Use `debug=true` to include `debug_data` (source_payload_json, dedup_hash) only when `DEBUG_ENDPOINTS_ENABLED=true`; otherwise the flag is ignored and internal fields are omitted.
- `POST /api/jobs/{id}/generate-resume`: Manually trigger or regenerate a resume. Requires `pipeline_status` ATS_ANALYZED or RESUME_READY; returns 409 if not ready.
- `GET /api/jobs/{id}/artifacts`: List available download links for a job.
- `PUT /api/jobs/{id}/status`: Update user workflow status. Only SAVED, APPLIED, ARCHIVED are writable; NEW is the initial state, not client-settable.

## 15. Worker / Pipeline Architecture (v1)
The system uses **Redis + Celery** for asynchronous processing. All scoring, classification, ATS, and resume logic are Python-owned.
- **Queues:** Celery routes tasks to `default`, `scrape`, and `ingestion` queues. Classification and resume tasks run on the default queue.
- **Task flow:** Scrape/ingest → score → classify → ats_match → (manual) generate-resume.

## 16. UI Architecture (v1)
The Review Interface is a Single Page Application (SPA) built with **React** and **Vite**.
- **Dashboard:** A list view of jobs categorized by user status (`New`, `Saved`, `Applied`, `Archived`).
- **Job Detail View:** Displays the original description alongside the JobBot insights (Score breakdown, Persona, Missing ATS Keywords).
- **Action Panel:** Contains the "Download Resume" buttons and a primary "Open Application" button that opens the external ATS link in a new tab, reinforcing that the system does not apply on the user's behalf.

## 17. Observability and Logging (v1)
- **Structured Logging:** Services output structured logs with context (`trace_id`, `job_id`) to track a job's journey through the pipeline.
- **Metrics:** Task-level metrics (histograms, counters) are instrumented for scoring, classification, ATS, and resume generation. Datadog or similar can consume them when configured.

*Future (not v1): Alerting on elevated error rates, DLQ dashboards.*

## 18. Failure Handling (v1)
- **Retries:** Transient errors in worker tasks use exponential backoff (Celery retry).
- **Failure Recording:** Task failures are recorded (e.g., to Redis) for visibility; no formal DLQ in v1.
- **Deterministic pipeline:** Classification and resume content are deterministic; no external LLM or generative service dependencies.

## 19. Testing Strategy (v1)
- **Unit Tests:** Validate deduplication logic, scoring heuristics, connector normalization, rules-based classification, and ATS extraction.
- **Integration Tests:** Ensure worker tasks correctly transition job states in the database.
- **E2E/API Tests:** Simulate the API flow from ingestion/scrape to artifact retrieval.
- **Golden Tests:** Labeled examples validate persona classification accuracy and ATS extraction against fixtures.

## 20. Future Extensions (not v1)
The following are out of scope for v1 but the architecture supports:
- **LLM Persona Classifier:** Optional provider behind the `PersonaClassifier` interface; v1 uses rules-based only.
- **LLM Content Tailoring:** Light rephrasing to front-load ATS keywords while keeping facts intact; v1 uses selection only, no rewrite.
- **DOCX Resume Output:** v1 produces PDF only.
- **Editable Resumes:** Allowing users to tweak the generated markdown/HTML in the UI before final PDF compilation.
- **Multi-User Support:** Isolating `Experience Inventories` and `Personas` by `user_id` for a SaaS offering.
- **Additional ATS Connectors:** Pluggable architecture makes it trivial to add Workday, SmartRecruiters, or custom scrapers.
- **Browser Extension for Discovery:** A lightweight extension to push jobs from LinkedIn directly into the JobBot ingestion queue.
