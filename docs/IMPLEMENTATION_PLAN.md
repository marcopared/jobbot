# JobBot Implementation Plan

## Purpose

This document translates the product spec and architecture into reviewable engineering delivery boundaries.

It is intentionally written to support small PRs and coding-agent delegation.

## 1. Current execution order

The immediate goal is to finish the alpha tonight with real discovery providers and artifact-ready verification.

The stale documentation-refresh step is complete. The implementation execution order now starts here:

1. **Adzuna hardening**
2. **DataForSEO real implementation**
3. **discovery E2E verification**
4. **optional UI polish**

The real repository remains the source of truth for current behavior until code lands.

## 2. Alpha discovery provider implementation wave

This wave brings the two named discovery providers into scope now:

- `AGG-1 = Adzuna`
- `SERP1 = DataForSEO Google Jobs`

Execution rules for this wave:
- SERP is now in scope for this implementation wave.
- Implement exactly one real SERP provider: DataForSEO Google Jobs.
- Keep SERP1 lower-confidence than Adzuna and feature-flagged.
- Finish provider work before any optional UI polish.

## 3. Story order for tonight

### Story 1 — Adzuna hardening

Scope:
- real Adzuna credential path
- bounded page-based fetching
- query/filter normalization needed for alpha
- clean provider errors and provenance preservation

Acceptance criteria:
- `AGG-1 = Adzuna` runs successfully with real credentials
- page-based search is bounded by explicit per-run limits
- discovered jobs normalize into the existing downstream pipeline
- provider failures are recorded cleanly without fabricating jobs
- targeted provider tests pass

Out of scope:
- queue-model changes
- generic crawler work
- UI polish beyond what is required for verification

### Story 2 — DataForSEO real implementation

Scope:
- `SERP1 = DataForSEO Google Jobs`
- Google Jobs endpoints only
- basic auth credential handling
- bounded synchronous wrapper over task post -> readiness poll -> advanced get
- lower-confidence discovery normalization and feature-flag enforcement

Acceptance criteria:
- `SERP1 = DataForSEO Google Jobs` runs successfully with real credentials
- implementation uses Google Jobs endpoints only
- implementation uses basic auth
- polling is bounded by attempts and/or wall-clock timeout
- normalized jobs enter the existing downstream pipeline as lower-confidence discovery records
- targeted provider tests pass

Out of scope:
- generic web SERP support
- postback/pingback infrastructure
- HTML endpoint integration
- canonical treatment of SERP jobs

### Story 3 — Discovery E2E verification

Scope:
- end-to-end verification for Adzuna and DataForSEO through the current pipeline
- targeted fixes required for artifact-ready throughput
- ready-to-apply and manual apply verification for discovery-originated jobs

Acceptance criteria:
- both providers chain into `score -> classify -> ATS -> generation gate`
- at least one discovery-originated job reaches artifact-ready
- `GET /api/jobs/ready-to-apply` is usable for the verified jobs
- manual apply link works for the verified jobs
- targeted E2E or integration tests pass

Out of scope:
- full state-machine redesign
- broad UI redesign
- speculative new provider abstractions beyond what the two providers need

### Story 4 — Optional UI polish

Scope:
- minimal UX polish after backend verification is green
- presentation or operator-flow tweaks for ready-to-apply throughput

Acceptance criteria:
- backend verification from Stories 1-3 is already green
- UI changes are limited to ready-to-apply usability and operator clarity
- no UI change alters the product boundary that manual apply is the final step

Out of scope:
- starting UI work before backend is green
- major navigation/layout redesign
- any UI claim that Adzuna/DataForSEO are fully implemented before backend verification passes

## 4. Delivery philosophy

Constraints:
- do not implement the whole roadmap in one PR
- do not treat discovery and canonical sources as equivalent
- do not enable high-risk lanes without a feature flag
- do not start with UI

Working principle for tonight:
- harden Adzuna first
- implement DataForSEO second
- verify discovery end to end third
- polish UI last, only if backend is green

## 5. PR order and boundaries

### PR 1 — documentation refresh (docs-only, completed before implementation PRs)

Scope:
- `docs/TODO.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/CODING_AGENT_GUIDE.md`
- optional small note in root `README.md`

Outcome:
- tonight's implementation order is explicit
- stop conditions are explicit
- provider-specific guardrails are explicit
- no status/history docs are changed in this PR

### PR 2 — Story 1: Adzuna hardening

Scope:
- Adzuna connector/runtime hardening only
- bounded page-based retrieval and normalization fixes
- tests directly related to Adzuna behavior

Boundary:
- one provider only
- no DataForSEO work in this PR

### PR 3 — Story 2: DataForSEO real implementation

Scope:
- DataForSEO Google Jobs only
- bounded synchronous task wrapper
- tests directly related to DataForSEO behavior

Boundary:
- one provider only
- no Adzuna refactors beyond shared code strictly required for correctness

### PR 4 — Story 3: discovery E2E verification

Scope:
- provider-to-pipeline verification
- targeted fixes required for artifact-ready discovery flow
- targeted tests and runbook-level verification notes if needed

Boundary:
- no broad schema redesign
- no queue-model redesign

### PR 5 — Story 4: optional UI polish

Scope:
- only after backend is green
- limited ready-to-apply polish

Boundary:
- no backend feature expansion disguised as UI work

## 6. Stop conditions

Do not expand tonight's wave into these items:
- no full state-machine rewrite
- no queue-model rewrite
- no generic crawler work
- no auto-apply
- no browser automation

## 7. Feature flags and runtime verification

Verify these before runtime sign-off:

- **Env vars required for Adzuna:** `ENABLE_AGG1_DISCOVERY=true`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, and `ADZUNA_COUNTRY`.
- **Env vars required for DataForSEO:** `ENABLE_SERP1_DISCOVERY=true` plus the DataForSEO login/password or equivalent basic-auth credentials used by the implementation.
- **Auto-generation flag:** `ENABLE_AUTO_RESUME_GENERATION` must be intentionally set based on whether discovery jobs should auto-generate during verification.
- **Worker queues:** keep the current queue model unless code changes later. Current expectation remains `default`, `scrape`, and `ingestion`.
- **Feature flags:** AGG-1, SERP1, and auto-generation remain independently controllable.
- **Playwright:** `playwright install chromium` remains required for PDF generation.

## 8. Runtime verification expectations

The wave is operationally verified only when:
- Adzuna works with real credentials
- DataForSEO works with real credentials
- both providers flow through the current worker topology without requiring a queue rewrite
- feature flags can independently enable or disable `AGG-1`, `SERP1`, and auto-generation behavior
- at least one discovery-originated job reaches artifact-ready and appears in ready-to-apply
- the manual apply link is usable for the verified job

## 9. Explicit anti-patterns

Do not do these:
- one mega-PR mixing both providers, E2E fixes, and UI polish
- treating SERP as canonical truth
- introducing a generic crawler while implementing DataForSEO
- rewriting queue topology or pipeline states as part of tonight's wave
- touching auto-apply or browser automation

## 10. Done criteria for tonight

Tonight's implementation wave is done when:
- Story 1 acceptance criteria pass
- Story 2 acceptance criteria pass
- Story 3 acceptance criteria pass
- Story 4 is either completed safely or intentionally skipped because backend consumed the available time
- manual apply remains the final step
