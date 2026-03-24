# Tech Debt Tracker

## Open Items

| ID | Priority | Item | Why it exists |
| --- | --- | --- | --- |
| DOC-001 | Medium | Add a lightweight docs/link checker | Prevents the new harness-style docs set from drifting |
| DOC-002 | Medium | Automate `docs/generated/db-schema.md` generation | The current file is curated from models/migrations, not generated in CI |
| API-001 | Medium | Expose `source_role` in job list responses | The UI currently infers provenance labels from `source` |
| DISC-001 | Low | Remove stale inline comment in `apps/worker/tasks/discovery.py` that says there is no auto-generation in the PR | Code already chains through the generation gate |
| REF-001 | Low | Consider adding a generated route summary under `docs/generated/` | Would make API changes easier to verify during doc updates |

## Closed Items

| ID | Closed | Item | Outcome |
| --- | --- | --- | --- |
| DOC-000 | 2026-03-24 | Replace stale phase/audit docs with a Harness-style living docs set | Completed in the documentation harness alignment cleanup |
