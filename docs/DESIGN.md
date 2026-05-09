# DESIGN.md — JobBot MVP System Design

## Design baseline

JobBot is a local-first decision-support tool for job applications. The current MVP automates preparation only enough to answer:

> “Is this job worth looking at, and which of my existing resumes should I use?”

It does not generate custom resumes and it does not apply to jobs.

## Current MVP flow

```text
get job descriptions
  -> normalize + deduplicate
  -> score/classify/analyze job description
  -> match against existing resumes, especially years of experience
  -> recommend the best existing resume
  -> show direct job/apply link
  -> user applies manually on the external site
```

## Design principles

1. Local-first by default.
2. Recommend existing user-maintained resumes; do not create custom resumes in the MVP.
3. Years-of-experience fit is a first-class matching signal.
4. The direct apply URL is part of the output, but the apply action is manual.
5. Discovery sources are useful for coverage but are lower confidence than canonical ATS/direct URLs.
6. Browser/session infrastructure is future infrastructure only, not current product logic.
7. Current code and active docs beat old phase plans.

## Active source model

### Canonical ATS

- Greenhouse
- Lever
- Ashby

These are high-confidence sources for job descriptions and apply URLs.

### Direct URL ingest

Supported Greenhouse/Lever/Ashby URLs let the user ingest a specific posting deterministically.

### Manual intake

Manual intake is the fallback when the user already has a posting and wants JobBot to analyze it.

### Discovery

Discovery sources may still exist, but the MVP treats them as coverage lanes. They should feed the same downstream recommendation pipeline and must not own product logic.

Authenticated browser discovery and bb-browser work are not active MVP requirements. They can be revisited later for a Raspberry Pi/local-browser setup.

## Active downstream chain

```text
score -> classify -> ats_match -> recommendation_gate
```

The code currently keeps the compatibility task name `evaluate_generation_gate`, but its active responsibility is existing-resume recommendation. It no longer queues custom resume generation.

## Resume recommendation model

Resume metadata lives in [`data/resumes.yaml`](../data/resumes.yaml). Each resume entry should include:

- `id`
- `label`
- `path`
- `persona`
- `years_experience`
- `skills`
- optional notes

The matcher in [`core/resume_matching.py`](../core/resume_matching.py):

1. extracts explicit years-of-experience requirements from the job description;
2. compares job text against resume skills;
3. boosts resumes whose persona matches the classified job persona;
4. returns a deterministic `resume_suggestion` payload.

The recommendation is stored on `JobAnalysis.persona_specific_scores["resume_suggestion"]` and surfaced in job list/detail responses.

## Operator output

The primary queue is the ready-to-apply/recommendation queue:

- job title/company/location
- score and persona
- recommended existing resume
- rationale including years/skill/persona fit
- direct job/apply URL
- user status controls: saved, applied, archived

`RESUME_READY` currently means “resume recommendation ready.” It does not mean a custom resume artifact exists.

## Explicit non-goals for current MVP

- auto-apply
- browser automation for application forms
- custom resume generation
- PDF rendering, fit planning, payload sidecars, diagnostics bundles
- GCS artifact storage as a product requirement
- broad authenticated browser ingestion
- plans-driven architecture docs (`docs/PLANS.md` is archived)

## Future archive

Old custom-resume generation code and old docs were archived for possible later reuse:

- [`archive/code/2026-05-07-custom-resume-generation`](../archive/code/2026-05-07-custom-resume-generation)
- [`docs/archive/2026-05-07-architecture-cleanup`](archive/2026-05-07-architecture-cleanup)

Treat archived content as historical reference, not active runtime design.
