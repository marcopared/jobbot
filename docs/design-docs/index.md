# Design Documents — Index

## How To Use This Index

These are the living design documents for JobBot. They are intentionally few. If a question can be
answered by current code, current code wins.
If surrounding repo context contains older pasted snapshots or duplicate doc copies, these current
checked-in indexed docs are the source of truth.

Read them in this order:

1. [AGENTS.md](../../AGENTS.md) for repo boundaries and verification
   minimums.
2. [ARCHITECTURE.md](../../ARCHITECTURE.md) for current implemented
   runtime topology and contracts.
3. [docs/DESIGN.md](../DESIGN.md) for the design baseline:
   current implemented design plus explicitly labeled approved ingestion-v2 direction.
4. [docs/PRODUCT_SENSE.md](../PRODUCT_SENSE.md) and
   [docs/RELIABILITY.md](../RELIABILITY.md) for product boundary
   and invariant guidance.

## Active Design Documents

| Document | Status | Verified | Role |
| --- | --- | --- | --- |
| [AGENTS.md](../../AGENTS.md) | Active | 2026-03-24 | Agent entry point and map |
| [ARCHITECTURE.md](../../ARCHITECTURE.md) | Active | 2026-04-06 | Runtime topology and subsystem boundaries |
| [docs/DESIGN.md](../DESIGN.md) | Active | 2026-04-06 | Design baseline: current implementation plus explicitly labeled approved direction |
| [docs/PRODUCT_SENSE.md](../PRODUCT_SENSE.md) | Active | 2026-04-02 | Product identity and operating boundary |
| [docs/RELIABILITY.md](../RELIABILITY.md) | Active | 2026-04-06 | Invariants and verification rules |
| [docs/SECURITY.md](../SECURITY.md) | Active | 2026-04-02 | Safety and security boundaries |
| [docs/QUALITY_SCORE.md](../QUALITY_SCORE.md) | Active | 2026-04-06 | Current quality assessment |
| [docs/PLANS.md](../PLANS.md) | Active | 2026-04-02 | Plan index |
| [docs/FRONTEND.md](../FRONTEND.md) | Active | 2026-04-06 | UI/operator surface |
| [docs/design-docs/resume-generation-v2.md](resume-generation-v2.md) | Active | 2026-04-06 | Concise implemented contract note for resume-generation v2 |
| [docs/design-docs/core-beliefs.md](core-beliefs.md) | Active | 2026-04-02 | Stable design beliefs and doc-reading rules |

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
2. Future-facing architecture notes must be explicitly labeled as approved direction, planned
   direction, or architecture target.
3. Do not let approved direction text read like implemented runtime truth.
4. Do not recreate one-off audit reports in the primary docs path.
5. Prefer updating an indexed living doc or a completed execution plan.
