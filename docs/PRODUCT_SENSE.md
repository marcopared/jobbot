# PRODUCT_SENSE.md — JobBot Product Direction

## Product Identity

JobBot is a personal job preparation system, not an autonomous job application bot.

Its value is:

- better coverage across job sources
- stronger confidence in which roles are worth attention
- faster preparation for the jobs that pass the bar
- a clean manual queue for final application

## Core Promise

Discover broadly. Decide carefully. Generate only when justified. Apply manually.

## User Model

The primary user is an operator running their own job search pipeline:

- they want better discovery coverage than one ATS or one board
- they want deterministic ranking and explainability
- they want fast resume preparation for the best jobs
- they do not want the system to auto-submit applications on their behalf

## What the Product Is Not

- not an auto-apply bot
- not a browser automation framework for applications
- not a generic crawler platform
- not a CRM for recruiter follow-up

## Current Product Loop

1. Trigger intake from scrape, discovery, canonical ingest, URL ingest, or manual intake.
2. Let the backend score, classify, and analyze jobs.
3. Review artifact-ready jobs in the ready-to-apply queue.
4. Download a generated artifact if needed.
5. Open the external apply URL and apply manually.
6. Mark status in JobBot after the human action.

## Coverage Direction

JobBot's ingestion architecture is being widened so the product can support broader source coverage
over time without changing what the product is for.

That widening is a behind-the-scenes infrastructure choice, not a new user-facing promise:

- the product still centers on better discovery, better filtering, and faster preparation
- manual apply remains the implemented product boundary today
- Scrapling is the default acquisition backend direction for most standard source capture
- bb-browser is the selective authenticated-session backend direction for a small subset of
  browser-native or auth-bound sources
- those backend choices do not turn JobBot into an auto-apply product or imply that every future
  source is already supported now

## Product Rules That Agents Must Not Erode

1. Canonical ATS and discovery have different trust levels.
2. SERP1 is always lower-confidence than AGG-1 and canonical ATS.
3. Resume generation is selective, not default-for-everything.
4. Human status tracking (`NEW`, `SAVED`, `APPLIED`, `ARCHIVED`) is user workflow, not pipeline state.
5. Historical phase language should not be treated as current product truth.

## Current Strengths

- multiple intake lanes
- room to widen source coverage without changing the product boundary
- deterministic scoring/classification/ATS analysis
- durable run tracking
- grounded resume generation path
- ready-to-apply operational screen

## Current Limits

- provider-backed end-to-end verification still depends on local setup and credentials
- discovery confidence remains heuristic
- frontend polish is secondary to backend correctness and operator clarity
