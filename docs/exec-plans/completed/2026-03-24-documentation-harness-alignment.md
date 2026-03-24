# Documentation Harness Alignment — Completed 2026-03-24

## Goal

Replace the previous documentation sprawl with a Harness-style structure that is easier for agents
to navigate and harder to misread.

## What Changed

### Added

- root architecture entry point
- indexed design docs
- indexed product specs
- reliability, security, quality, frontend, and plan docs
- agent-friendly reference summaries
- generated schema summary

### Removed

- historical acceptance and closeout reports
- PR-specific follow-up notes
- implementation-phase status/plan docs that no longer matched the way the repo is read today
- the old duplicate docs-level AGENTS/README/SPEC/ARCHITECTURE set

## Why

The removed files were optimized for a specific implementation wave, not for long-term agent
legibility. They forced readers to separate living truth from obsolete history on every task.

## Outcome

The documentation graph now follows the same pattern used in the Harness-style reference repo:

- short root map
- root architecture file
- structured `docs/` tree
- living docs instead of proof-style status notes

## Follow-Ups

Tracked in
[docs/exec-plans/tech-debt-tracker.md](/Users/marcoparedes/dev/jobbot/docs/exec-plans/tech-debt-tracker.md).
