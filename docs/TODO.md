# TODO

Active backlog for the alpha completion push.

**Implementation order:** Finish the discovery and artifact-ready alpha tonight. Documentation in this PR sets the execution order for code PRs that follow.

**Product scope** (unchanged):
- automated job discovery through artifact-ready
- manual application remains the final human step
- no browser automation
- no automated application submission

## Today's alpha completion

1. **Adzuna hardening**
   - Make `AGG-1 = Adzuna` work reliably with real credentials.
   - Keep it page-based, query-driven, rate-limit-aware, and bounded per run.
   - Preserve discovery provenance and downstream compatibility.

2. **DataForSEO SERP1 real implementation**
   - Make `SERP1 = DataForSEO Google Jobs` real for this wave.
   - Keep it lower-confidence, feature-flagged, and restricted to Google Jobs endpoints only.
   - Implement it as a bounded synchronous wrapper over the provider task API for alpha.

3. **Discovery end-to-end verification**
   - Verify both discovery providers flow into score -> classify -> ATS -> generation gate.
   - Confirm at least one discovery-originated job can reach artifact-ready.
   - Confirm provider failures/timeouts degrade cleanly without blocking the rest of the run.

4. **Ready-to-apply operational polish**
   - Ensure the ready-to-apply view is usable once backend discovery is green.
   - Confirm artifact-ready jobs expose a usable manual apply link.
   - Fix only the minimum backend/UI contract issues required for artifact-ready throughput.

5. **UI polish only if backend is green**
   - Limit UI work to presentation and operator clarity.
   - Do not start visual polish until Adzuna, DataForSEO, and discovery E2E verification are passing.

## Deferred after tonight

- full target pipeline states
- target queue split
- generic crawling
- auto-apply
- browser automation

## Done tonight checklist

- [ ] Adzuna working with real credentials
- [ ] DataForSEO working with real credentials
- [ ] both chain into downstream pipeline
- [ ] at least one discovery-originated job reaches artifact-ready
- [ ] ready-to-apply is usable
- [ ] manual apply link works
- [ ] targeted tests pass

## Context to preserve while implementing

- Canonical ATS and supported URL ingest remain the highest-confidence inputs.
- Discovery sources remain non-canonical by default.
- Source-confidence order remains: canonical ATS > Adzuna > DataForSEO.
- UI work is subordinate to backend verification for this wave.

## Explicitly not in scope

- full state-machine rewrite
- queue-model rewrite
- automated application submission
- browser automation for job applications
- generic arbitrary crawling as the main ingestion strategy
- treating SERP/search results as canonical truth by default
