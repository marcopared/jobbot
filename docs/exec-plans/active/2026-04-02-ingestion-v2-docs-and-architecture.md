# Ingestion-V2 Docs And Architecture

## Goal

Align the living docs to the approved ingestion-v2 direction before implementation work, while
preserving current runtime and product truth.

## Scope

- rewrite design, product, safety, reliability, frontend, and planning docs as needed for the
  ingestion-v2 docs pass
- clarify current implemented behavior versus approved ingestion direction
- document Scrapling as the default backend direction for most non-API and non-auth-heavy sources
- document bb-browser as the selective authenticated-session backend direction for a small subset
  of browser-native or auth-bound sources
- preserve the current manual-apply truth

## Non-Goals

- no code changes in this pass
- no auto-apply implementation
- no frontend redesign

## Target Docs

- [docs/DESIGN.md](/Users/marcoparedes/dev/jobbot/docs/DESIGN.md)
- [docs/design-docs/core-beliefs.md](/Users/marcoparedes/dev/jobbot/docs/design-docs/core-beliefs.md)
- [docs/design-docs/index.md](/Users/marcoparedes/dev/jobbot/docs/design-docs/index.md)
- [docs/PRODUCT_SENSE.md](/Users/marcoparedes/dev/jobbot/docs/PRODUCT_SENSE.md)
- [docs/product-specs/source-lanes-and-manual-apply.md](/Users/marcoparedes/dev/jobbot/docs/product-specs/source-lanes-and-manual-apply.md)
- [docs/SECURITY.md](/Users/marcoparedes/dev/jobbot/docs/SECURITY.md)
- [docs/RELIABILITY.md](/Users/marcoparedes/dev/jobbot/docs/RELIABILITY.md)
- [docs/FRONTEND.md](/Users/marcoparedes/dev/jobbot/docs/FRONTEND.md)
- [docs/PLANS.md](/Users/marcoparedes/dev/jobbot/docs/PLANS.md)
- [docs/exec-plans/active/README.md](/Users/marcoparedes/dev/jobbot/docs/exec-plans/active/README.md)

## Acceptance Criteria

- docs distinguish current implemented truth from approved ingestion-v2 direction
- docs preserve that JobBot still ends at manual apply today
- docs describe source adapters plus acquisition backends as the ingestion architecture target
- docs describe Scrapling and bb-browser as backend directions, not current shipped product features
- runtime docs do not claim new routes, queues, states, or workflows

## Execution Order

1. Update foundational design docs.
2. Update product-facing source-lane docs.
3. Add small guardrails to safety, reliability, and frontend docs.
4. Refresh planning indexes to point at this active plan.
