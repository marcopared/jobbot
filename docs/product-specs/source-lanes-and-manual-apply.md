# Source Lanes And Manual Apply

## Current Product Rule

JobBot discovers broadly but only prepares selectively, and it currently stops before the actual
application submission.

## Current Implemented Source Lanes

### Canonical ATS

- Greenhouse
- Lever
- Ashby

Use these as the highest-confidence sources for job content and apply entry points.

### Discovery

- JobSpy
- AGG-1 = Adzuna
- SERP1 = DataForSEO Google Jobs

Use these for coverage, filtering, and ranking. Do not treat them as canonical truth by default.

### Direct URL ingest

- supported Greenhouse/Lever/Ashby URLs

This is the fastest route from a known job posting to the normal downstream pipeline.

## Current Trust Model

Trust order:

1. canonical ATS
2. URL ingest into canonical ATS
3. AGG-1
4. SERP1

SERP1 remains lower-confidence and feature-flagged.

## Approved Ingestion Expansion Direction

This section describes approved product direction for source onboarding. It does not claim broader
source support is already shipped.

The architecture target is:

- source adapters for source-specific parsing, field mapping, and provenance handling
- acquisition backends for how content is fetched or captured

Product intent:

- widen coverage over time without blurring the trust distinction between canonical ATS and
  discovery
- add new source categories deliberately instead of turning the system into a generic crawling
  platform
- keep the product centered on discovery quality, ranking, and preparation rather than automated
  application

Approved backend direction:

- Scrapling is the default acquisition backend direction for most non-API and non-auth-heavy
  sources.
- bb-browser is the selective authenticated-session backend direction for a small subset of
  browser-native or auth-bound sources.
- These are backend directions, not user-facing product features or promises of universal current
  support.

## Manual Apply Boundary

The product ends here:

- user downloads or previews the generated resume artifact
- user opens the external apply URL
- user applies outside JobBot
- user optionally marks the result in JobBot

The product does not:

- submit forms automatically
- drive a browser through application workflows
- mark applications as submitted without user action

That boundary does not change under the approved ingestion expansion direction.
