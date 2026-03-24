# Source Lanes And Manual Apply

## Product Rule

JobBot discovers broadly but only prepares selectively, and it always stops before the actual
application submission.

## Supported Source Lanes

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

## Confidence Model

Trust order:

1. canonical ATS
2. URL ingest into canonical ATS
3. AGG-1
4. SERP1

SERP1 remains lower-confidence and feature-flagged.

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
