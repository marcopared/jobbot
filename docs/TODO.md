# TODO

Active backlog for JobBot v1. Product scope: manual job discovery, scoring, ATS analysis, tailored resume generation. **Auto-apply and Simplify-first workflows are not in scope.**

---

## Now

1. **Scoring quality**
   - Add stronger weighting controls for title, seniority, and domain fit.
   - Validate scoring output against a curated operator-reviewed sample set.

2. **ATS analysis**
   - Improve keyword extraction from noisy job descriptions.
   - Expand synonym handling and normalization for common skill variants.
   - Surface more actionable ATS gap suggestions in the UI.

3. **Resume generation**
   - Improve per-job tailoring from job description + master skills.
   - Add artifact quality checks to catch malformed or low-value resume outputs.

---

## Next

4. **Operator workflow**
   - Add better filters for high-score/high-match jobs.
   - Add clearer manual process checkpoints for job review.

5. **Additional connectors**
   - Add Lever connector (pluggable architecture supports it).
   - Consider Workday, SmartRecruiters, or other ATS connectors as needed.

6. **GCS / GCP operational follow-ups**
   - Document and validate signed URL behavior in production.
   - Lifecycle policies for artifact cleanup; optional CDN links.

---

## Later

7. **Pipeline stability**
   - Stronger end-to-end checks for scrape → score → ATS → resume.
   - Better observability around worker failures and partial pipeline runs.

8. **Jira-derived scoring (optional)**
   - Support structured project/Jira-derived materials for richer experience inputs and scoring signals, if desired.

---

## Archived / not v1

The following are out of scope for v1. Kept for reference only.

- **Auto-apply / browser automation:** System does not submit applications. Users manually apply via job URL.
- **Simplify-first workflow:** No job-description simplification or pre-apply rewrite flow.
- **Legacy schema cleanup:** Migration/cleanup for any remaining legacy apply-related statuses (`APPLY_QUEUED`, `APPLY_FAILED`, `INTERVENTION_REQUIRED`, etc.) in existing data. Operational hygiene; no new apply features.
