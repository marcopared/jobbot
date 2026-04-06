# QUALITY_SCORE.md — Current Quality Assessment

This is a pragmatic quality snapshot for the current repository, based on the codebase, tests, and
the documentation cleanup completed on 2026-03-24.

## Grades

| Area | Grade | Why |
| --- | --- | --- |
| Intake connectors and source-role model | B+ | Canonical ATS, discovery, URL ingest, and manual intake are implemented with clear roles and targeted tests |
| Pipeline durability and contracts | B | Strong invariants exist for run tracking, chain progression, and run-item schema, but full runtime verification is still partly manual |
| Resume generation path | B+ | Grounded generation now persists a deterministic PDF plus payload/diagnostics bundle with explicit fit outcomes and evidence summaries, but it still depends on Playwright and local runtime setup |
| API and operator contracts | B | Core routes are stable and tested, and resume artifact summaries are now explicit, but list/detail schemas still carry some legacy shape decisions |
| Frontend operator flow | B- | The UI covers the operator loop well enough, but it still relies on a few inferred labels and minimal presentation polish |
| Security and product-boundary discipline | B | Manual apply, feature flags, signed URL handling, and debug gating are solid, but security is mostly convention plus small controls rather than a deep policy engine |
| Documentation harness | A- | The repo now has a smaller, code-aligned, Harness-style docs graph instead of many stale historical notes |

## Evidence Behind The Grades

- focused regression suites in [tests/README.md](../tests/README.md)
- connector/provider tests under [tests](../tests)
- durable generation and run tracking through `ScrapeRun` and `GenerationRun`
- resume-v2 artifact metadata surfaced through `GET /api/jobs/{id}` and `GET /api/jobs/{id}/artifacts`
- operator-facing routes and UI pages implemented end to end

## Biggest Quality Risks

1. Real-provider verification is not fully encoded in automated tests.
2. Discovery confidence and eligibility remain heuristic, not strongly validated against live traffic.
3. API/UI list views still hide some backend distinctions, such as `source_role`.

## How To Improve The Score

1. Add a lightweight docs/link linter so the new harness structure stays clean.
2. Surface `source_role` directly in job list responses instead of UI inference.
3. Add generated docs automation for DB schema and route summaries.
4. Increase local runbook coverage for provider-backed verification.
