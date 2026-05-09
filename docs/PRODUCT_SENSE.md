# PRODUCT_SENSE.md — JobBot MVP Product Intent

## One-line product

JobBot helps a local user decide which jobs are worth attention and which existing resume to use, then hands the user the direct job link for manual application.

## Current user promise

The user should not have to open every job site just to answer:

- What is this job asking for?
- Do I meet the years-of-experience requirement?
- Which of my existing resumes is the best fit?
- Where do I apply if I choose to proceed?

## Current product loop

1. JobBot ingests or accepts a job description.
2. JobBot scores and classifies it.
3. JobBot extracts ATS-like signals and years requirements.
4. JobBot recommends one existing resume from `data/resumes.yaml`.
5. JobBot shows the direct job/apply URL.
6. The user manually applies on the job site.

## What matters most now

- clean local architecture
- accurate documentation
- deterministic existing-resume recommendation
- clear years-of-experience fit
- direct job links
- simple ready-to-apply queue

## What is intentionally deferred

- custom resume creation
- generated PDFs
- automatic application submission
- authenticated browser application flows
- cloud-first deployment concerns
- advanced browser/session ingestion

## Product boundary

Manual apply is not a temporary gap; it is the current product boundary. Anything that exists solely to automate application forms or generate custom artifacts belongs in archive/future scope unless explicitly reactivated.
