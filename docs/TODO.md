# TODO

## Priority Work

1. Improve job scoring quality
   - Add stronger weighting controls for title, seniority, and domain fit.
   - Validate scoring output against a curated operator-reviewed sample set.

2. Strengthen ATS analysis
   - Improve keyword extraction quality from noisy job descriptions.
   - Expand synonym handling and normalization for common skill variants.
   - Surface more actionable ATS gap suggestions in UI.

3. Expand custom resume generation
   - Improve per-job resume tailoring from job description + master skills.
   - Support richer experience source inputs (for example, structured project/Jira-derived materials).
   - Add artifact quality checks to catch malformed or low-value resume outputs.

4. Improve operator workflow ergonomics
   - Add better review filters for high-score/high-match jobs.
   - Add clearer manual process checkpoints for job review and intervention handling.

## Stability / Ops

1. Add stronger end-to-end checks for scrape -> score -> ATS -> resume pipeline.
2. Tighten local observability around worker failures and partial pipeline runs.
3. Document migration/cleanup plan for any remaining legacy apply-related statuses.
