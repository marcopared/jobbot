# Ready To Apply Operator Loop

## Purpose

The ready-to-apply queue is the default operational view of JobBot.

## Entry Conditions

A job appears in the queue when:

- `pipeline_status = RESUME_READY`
- `artifact_ready_at` is set
- `user_status = NEW`

Current implementation:
- route: `GET /api/jobs/ready-to-apply`
- UI page: `/ready`
- default sort: `artifact_ready_at desc`

## Operator Actions

From this loop, the user should be able to:

1. inspect the job detail
2. move from the queue into Job Detail via the Apply action
3. preview or download the primary PDF artifact from Job Detail
4. optionally inspect the payload/diagnostics JSON sidecars
5. open the external apply URL and apply manually
6. mark the job as saved, archived, or applied

## Non-Goals

- no hidden apply automation
- no hidden submission from the queue itself
- no bypass of the job detail and artifact review step
- no claim that ready-to-apply means “already applied”

## Why This Surface Matters

This queue is the product’s operational output. Everything upstream exists to make this queue more
useful, more trustworthy, and easier to work through.
