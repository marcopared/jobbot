# Design Documents — Index

## How To Use This Index

These are the living design documents for JobBot. They are intentionally few. If a question can be
answered by current code, current code wins.

## Active Design Documents

| Document | Status | Verified | Role |
| --- | --- | --- | --- |
| [AGENTS.md](/Users/marcoparedes/dev/jobbot/AGENTS.md) | Active | 2026-03-24 | Agent entry point and map |
| [ARCHITECTURE.md](/Users/marcoparedes/dev/jobbot/ARCHITECTURE.md) | Active | 2026-03-24 | Runtime topology and subsystem boundaries |
| [docs/DESIGN.md](/Users/marcoparedes/dev/jobbot/docs/DESIGN.md) | Active | 2026-03-24 | Design baseline and flow model |
| [docs/PRODUCT_SENSE.md](/Users/marcoparedes/dev/jobbot/docs/PRODUCT_SENSE.md) | Active | 2026-03-24 | Product identity and operating boundary |
| [docs/RELIABILITY.md](/Users/marcoparedes/dev/jobbot/docs/RELIABILITY.md) | Active | 2026-03-24 | Invariants and verification rules |
| [docs/SECURITY.md](/Users/marcoparedes/dev/jobbot/docs/SECURITY.md) | Active | 2026-03-24 | Safety and security boundaries |
| [docs/QUALITY_SCORE.md](/Users/marcoparedes/dev/jobbot/docs/QUALITY_SCORE.md) | Active | 2026-03-24 | Current quality assessment |
| [docs/PLANS.md](/Users/marcoparedes/dev/jobbot/docs/PLANS.md) | Active | 2026-03-24 | Plan index |
| [docs/FRONTEND.md](/Users/marcoparedes/dev/jobbot/docs/FRONTEND.md) | Active | 2026-03-24 | UI/operator surface |
| [docs/design-docs/core-beliefs.md](/Users/marcoparedes/dev/jobbot/docs/design-docs/core-beliefs.md) | Active | 2026-03-24 | Stable design beliefs |

## What Was Removed

The previous documentation set contained many point-in-time phase, PR, audit, and closeout notes.
Those files were deleted during the 2026-03-24 cleanup because they were no longer good agent entry
points and encouraged stale-read behavior.

The repo now prefers:

- fewer living docs
- explicit indexes
- targeted reference summaries
- code-aligned reliability notes instead of proof-style snapshots

## Freshness Rules

1. Re-verify these docs when routes, models, or worker topology change.
2. Do not recreate one-off audit reports in the primary docs path.
3. Prefer updating an indexed living doc or a completed execution plan.
