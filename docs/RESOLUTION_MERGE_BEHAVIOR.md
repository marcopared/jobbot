# Discovery-to-Canonical Resolution: Merge Behavior

When a discovery job resolves to a supported canonical ATS source (Greenhouse, Lever, Ashby), the system enriches the existing job in place. No new job is created.

## Behavior

1. **In-place enrichment** — The discovery job record is updated with canonical fields (description, apply_url, title, company, location, ats_type, etc.). Provenance is preserved via the existing JobSourceRecord for the discovery source (e.g. agg1).

2. **Canonical provenance** — A new JobSourceRecord is added for the canonical source (greenhouse/lever/ashby) with `external_id` and raw payload. The job thus has multiple sources: discovery + canonical.

3. **Resolution status** — The job’s `resolution_status` is set to `resolved_canonical`, `resolution_confidence` to 1.0, and `source_confidence` raised to 1.0.

4. **Attempt tracking** — Each resolution attempt is recorded in `job_resolution_attempts` (success or failure, with reason).

5. **Downstream pipeline** — After successful resolution, the job is re-queued through score → classify → ats_match → generation_gate, so it benefits from the enriched content.

Provider-specific clarification:

- whether the discovery record originated from Adzuna, DataForSEO Google Jobs, or another discovery lane, successful resolution still enriches the same job in place; provenance from the originating discovery source is preserved.

## No duplication

- The same job record is reused; canonical data overwrites/merges into it.
- If a canonical job already exists with the same apply URL (from prior ingest), the discovery flow’s dedup logic would have merged at insert time. Resolution operates on discovery jobs that were inserted without an existing canonical match.

## Out-of-scope

- Absorption of a discovery job into a different canonical job (e.g. a `resolved_to_job_id` link) is not implemented.
- The `job_sources` unique constraint on `(source_name, external_id)` is global; if two discovery jobs resolve to the same canonical job, the first resolution inserts the JobSourceRecord; subsequent resolutions still enrich their jobs but skip the duplicate source record insert.
