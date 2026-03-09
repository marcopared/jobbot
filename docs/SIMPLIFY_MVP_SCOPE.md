# Simplify MVP Scope

This document defines the current MVP boundary for Simplify integration in Jobbot.

## MVP Assumptions

The current flow assumes the user already has a valid Simplify account state:

- User is already logged into Simplify in the persistent Chromium profile.
- User already has a resume uploaded in Simplify.
- User profile data in Simplify is already populated (basic details, links, etc.).

## Current Jobbot Scope

For this MVP, Jobbot is responsible for enabling and validating the manual autofill flow:

- Launch Chromium with a persistent profile and the Simplify extension loaded.
- Open the target application page (dummy fixture via `file://` or `http://localhost`).
- Verify the extension is loaded (service worker/extension ID check).
- Pause for manual interaction so Simplify can autofill from stored account/profile state.
- Capture debug artifacts (page screenshot, HTML snapshot, and field summary log).

## Deferred (Out of Scope for MVP)

The following items are intentionally deferred to later milestones:

- Automated resume replacement/upload inside Simplify.
- Per-job tailored resume upload workflows.
- Automated Simplify profile mutation/update flows.

## Practical Test Interpretation

When running MVP smoke tests, success means Simplify can be launched and used to autofill from existing account state. Missing automation for resume/profile mutation is expected at this stage.
