# JobBot System Specification and Architecture

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
3. **Scoring Pipeline:** The normalized job is passed through a scoring engine. Jobs below a configurable threshold are persisted for historical analysis and model tuning, but are marked as `REJECTED` and hidden from the user.
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

## 10. Scoring System Design
The scoring system uses a weighted heuristic model implemented in Python:
- **Title Relevance (30%):** Matches against target titles (e.g., "Senior Software Engineer").
- **Seniority Match (20%):** Penalizes roles that are too junior or excessively senior.
- **Tech Stack Relevance (30%):** Keyword matching between the job description and the user's core competencies (e.g., Python, Go, Kubernetes).
- **Location/Remote (20%):** High score for "Remote", lower for incompatible geographic locations.
Jobs scoring below a defined threshold (e.g., 60/100) are marked as `REJECTED` in the pipeline and skip downstream processing.

## 11. Persona Classification System
An LLM-based classifier evaluates the job description.
- **Backend Engineer:** Triggered by heavy emphasis on API design, databases, business logic, and backend languages (Go, Python, Java).
- **Platform / Infrastructure Engineer:** Triggered by infrastructure-as-code, Kubernetes, CI/CD, AWS/GCP, and observability tools.
- **Hybrid:** Fallback for roles demanding a mix of both.
The selected persona dictates which subset of the `Experience Inventory` is prioritized during resume generation.

## 12. Resume Generation Architecture
1. **Data Assembly:** The system gathers the `JobAnalysis`, the selected `Persona`, and the `Experience Inventory`.
2. **Content Tailoring:** An LLM prompt is constructed to *both select and rewrite* the most relevant bullet points from the structured experience inventory. The LLM ensures ATS keywords are naturally integrated while maintaining factual accuracy.
3. **Formatting:** The tailored content is injected into a deterministic HTML template.
4. **Compilation:** A rendering engine (Playwright invoked via Python) converts the HTML template into a PDF. *(Note: v1 renders PDF only; DOCX generation is deferred to a future iteration to constrain initial scope).*

## 13. Artifact Storage Strategy
Generated resumes are stored in AWS S3.
- Artifacts are keyed by `job_id` and `timestamp` (e.g., `resumes/{job_id}/{timestamp}_resume.pdf`).
- The database `artifacts` table stores the pre-signed URL or CDN link for fast retrieval by the UI.
- A lifecycle policy automatically deletes artifacts for jobs older than 90 days to minimize storage costs.

## 14. API Design
The backend exposes a RESTful API built with **FastAPI (Python)** for the frontend:
- `GET /api/jobs`: List jobs with filtering (user_status, score, persona).
- `GET /api/jobs/{id}`: Retrieve full job details, analysis, and scores.
- `POST /api/jobs/{id}/generate-resume`: Manually trigger or regenerate a resume.
- `GET /api/jobs/{id}/artifacts`: List available download links for a job.
- `PUT /api/jobs/{id}/status`: (Planned) Update user workflow status (e.g., `APPLIED`, `ARCHIVED`).

## 15. Worker / Pipeline Architecture
The system relies heavily on asynchronous processing using a message broker (**Redis + Celery**). The core scoring, ATS, and resume logic are entirely Python-owned.
- **Queues:**
  - `ingestion_queue`: High throughput, fetches data.
  - `scoring_queue`: CPU bound, runs heuristics.
  - `llm_queue`: Rate-limited, handles persona classification and content tailoring.
  - `render_queue`: IO/CPU bound, generates PDFs.
This decoupling ensures that rate limits from LLM providers or ATS APIs do not block the entire pipeline.

## 16. UI Architecture
The Review Interface is a Single Page Application (SPA) built with **React and Vite**.
- **Dashboard:** A list view of jobs categorized by user status (`New`, `Saved`, `Applied`, `Archived`).
- **Job Detail View:** Displays the original description alongside the JobBot insights (Score breakdown, Persona, Missing ATS Keywords).
- **Action Panel:** Contains the "Download Resume" buttons and a primary "Open Application" button that opens the external ATS link in a new tab, reinforcing that the system does not apply on the user's behalf.

## 17. Observability and Logging
- **Structured Logging:** All services output JSON logs including `trace_id` and `job_id` to track a job's journey through the pipeline.
- **Metrics:** Datadog tracks:
  - Ingestion volume per source.
  - Pipeline processing time.
  - LLM API latency and error rates.
  - Resume generation success rates.
- **Alerting:** Alerts trigger on elevated error rates in the `llm_queue` or if ingestion connectors fail consecutively.

## 18. Failure Handling
- **Retries:** Transient errors (network timeouts, rate limits) in worker queues use exponential backoff.
- **Dead Letter Queue (DLQ):** Jobs that fail processing after maximum retries are moved to a DLQ for manual inspection.
- **Graceful Degradation:** If the LLM service is down, jobs are still ingested and scored, but classification and resume generation are paused and queued for later.

## 19. Testing Strategy
- **Unit Tests:** Validate deduplication logic, scoring heuristics, and connector normalization.
- **Integration Tests:** Ensure worker tasks correctly transition job states in the database.
- **E2E Tests:** Simulate the API flow from ingestion webhook to artifact retrieval.
- **Prompt Evaluations:** Automated tests for LLM prompts to ensure persona classification accuracy and formatting stability against a golden dataset of job descriptions.

## 20. Future Extensions
While out of scope for the initial rewrite, the architecture supports:
- **Editable Resumes:** Allowing users to tweak the generated markdown/HTML in the UI before final PDF compilation.
- **Multi-User Support:** Isolating `Experience Inventories` and `Personas` by `user_id` for a SaaS offering.
- **Additional ATS Connectors:** Pluggable architecture makes it trivial to add Workday, SmartRecruiters, or custom scrapers.
- **Browser Extension for Discovery:** A lightweight extension to push jobs from LinkedIn directly into the JobBot ingestion queue.
