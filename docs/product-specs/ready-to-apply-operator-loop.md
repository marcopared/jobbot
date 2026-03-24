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

## Operator Actions

From this loop, the user should be able to:

1. inspect the job detail
2. preview or download the artifact
3. open the job detail and then the external apply URL
4. mark the job as saved, archived, or applied

## Non-Goals

- no hidden apply automation
- no bypass of the job detail or artifact review step
- no claim that ready-to-apply means “already applied”

## Why This Surface Matters

This queue is the product’s operational output. Everything upstream exists to make this queue more
useful, more trustworthy, and easier to work through.
