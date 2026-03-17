# TODO

Active backlog for the next JobBot implementation wave.

**Implementation order:** Stabilization first. No new product scope in docs-only PRs. See `IMPLEMENTATION_PLAN.md` for PR boundaries and merge rules.

**Product scope** (unchanged):
- automated job discovery through artifact-ready
- manual application remains the final human step
- no browser automation
- no automated application submission

## Now

1. **Documentation refresh** (docs-only stabilization)
   - Align docs with the current system (real repo is source of truth).
   - Clearly distinguish implemented, partially implemented, and remaining.
   - Ensure implementation order, do-not-touch, and acceptance-criteria sections exist for agents.

2. **DB and model foundation** — *Implemented* (source_role, resolution_status, generation runs; migration 004).
   - Extend canonical job model for multi-source ingestion.
   - Add source-role and resolution concepts.
   - Add generation-eligibility and generation-run tracking.
   - Add safe, incremental migrations from the current baseline.

3. **Official ATS expansion** — *Implemented* (Lever, Ashby connectors; generalized run-ingestion).
   - Add Lever connector.
   - Add Ashby connector.
   - Generalize canonical ingestion API beyond Greenhouse-only assumptions.
   - Keep Greenhouse, Lever, and Ashby aligned to one canonical normalization contract.

4. **Direct URL ingest** — *Implemented* (POST /api/jobs/ingest-url; url_provider).
   - Add supported ATS URL ingest for Greenhouse, Lever, and Ashby.
   - Add provider detection and clean unsupported-provider errors.
   - Route URL-ingested jobs into the standard downstream pipeline.

## Next

5. **Broad discovery lane** — *Implemented* (AGG-1, SERP1 via run-discovery; feature-flagged).
   - Add AGG-1 as the first structured broad multi-company discovery source.
   - Keep it query-driven and rate-limit-aware.
   - Mark discovery records distinctly from canonical records.

6. **Automated generation funnel** — *Implemented* (generation gate; auto-gen when ENABLE_AUTO_RESUME_GENERATION=true).
   - Add explicit generation gate after ATS analysis.
   - Automatically generate artifacts for eligible jobs.
   - Preserve manual regenerate behavior for override/debug.

7. **Ready-to-apply backend surface** — *Implemented* (GET /api/jobs/ready-to-apply).
   - Add an artifact-ready feed for jobs with usable apply URLs.
   - Add richer filters for source role, confidence, generation eligibility, and resolution status.
   - Expose enough status detail for UI throughput mode.

8. **Worker/pipeline hardening**
   - Make discovery, ingestion, resolution, analysis, and generation states explicit.
   - Improve failure recording and observability by phase.
   - Add stale/apply-link verification.

## Later

9. **Optional SERP lane**
   - Add one SERP-derived provider behind a feature flag.
   - Treat it as lower-confidence discovery only.
   - Keep it disabled by default until the core system is stable.

10. **UI throughput mode**
   - Rework the default UI around a ready-to-apply queue.
   - Add source/provenance visibility.
   - Add URL ingest entry point.
   - Surface generation and resolution status clearly.

11. **Source controls and operations**
   - Add source configs / enable-disable controls.
   - Add per-source quotas or caps where useful.
   - Improve operational dashboards for runs, failures, and generation throughput.

## Later / optional

12. **Additional ATS ecosystems**
   - Revisit Workday or other undocumented/public-but-brittle sources only after the core lanes are stable.
   - Treat partner-feed integrations as a separate business/access problem, not an immediate coding task.

13. **Remote-job supplements**
   - Consider remote-only supplemental APIs if they add meaningful signal beyond AGG-1 plus ATS connectors.

## Explicitly not in scope

- automated application submission
- browser automation for job applications
- interview scheduling
- generic arbitrary crawling as the main ingestion strategy
- treating SERP/search results as canonical truth by default
