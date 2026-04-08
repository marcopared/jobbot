# Core Beliefs — JobBot Documentation And Design

These are the stable beliefs behind the cleaned-up docs set. Agents should treat them as operating
rules, not optional style preferences.

## Belief 1: The Repository Is The System Of Record

If an agent cannot find it in the repo, it should not rely on it. Durable instructions belong in
tracked files, not in stale PR notes or remembered conversation history.

## Belief 2: Give The Agent A Map, Not A Dump

The repo should have a short entry point plus a few high-signal living docs. Big piles of phase
documents and audit snapshots create ambiguity, not clarity.

## Belief 3: Current Code Beats Aspirational Docs

When documentation and implementation diverge, the code is the truth source. The right fix is to
update or delete the doc, not to pretend the implementation already matches the plan.

## Belief 4: Discovery And Canonical Sources Are Different Kinds Of Truth

Discovery improves coverage. Canonical ATS improves trust. Conflating those roles damages scoring,
resolution, and generation behavior. Acquisition infrastructure can evolve, but it should remain
separate from scoring, persistence policy, and other product logic.

## Belief 5: Manual Apply Is The Current Implemented Product Boundary

JobBot prepares the user to apply. It does not apply for them today. Documentation should preserve
that current scope while clearly separating it from future-compatible infrastructure decisions.

## Belief 6: Durable Run Records Are Part Of The Product

`ScrapeRun` and `GenerationRun` are not just debugging details. They are core evidence that the
system behaved correctly.

## Belief 7: Resume Generation Must Stay Grounded

The resume path should stay tied to user-side evidence and explicit selection logic: required
inventory, optional local supplemental files, and a targeting-only job description. Freeform
generation would reduce trust and debuggability.

## Belief 8: Reliability Lives In Invariants, Not In Victory Notes

Regression suites and durable contracts matter more than historical audit prose that once declared
something “done.”

## Belief 9: Docs Should Collapse History Into Current Guidance

When historical documents stop helping agents make correct decisions, they should be deleted or
reduced into a smaller living document.

## Belief 10: References Should Be Agent-Legible

Raw swagger and OpenAPI files can stay in the repo, but agents benefit from short repo-authored
reference summaries that explain what matters for current implementation work.
