"""Legacy status mirror helper.

Canonical source of truth is pipeline_status and user_status.
Legacy Job.status is a compatibility mirror only.
All writers (API, score task, ATS task, scrape task) must use this helper
so status is derived consistently from canonical state.

Precedence (exact order):
1. pipeline_status = REJECTED → REJECTED
2. user_status = APPLIED → APPLIED
3. user_status = ARCHIVED → ARCHIVED
4. pipeline_status = SCORED → SCORED
5. else → NEW
"""


def legacy_status_from_canonical(pipeline_status: str, user_status: str) -> str:
    """Return the value to set for legacy Job.status given canonical fields."""
    if pipeline_status == "REJECTED":
        return "REJECTED"
    if user_status == "APPLIED":
        return "APPLIED"
    if user_status == "ARCHIVED":
        return "ARCHIVED"
    if pipeline_status in ("SCORED", "CLASSIFIED", "ATS_ANALYZED", "RESUME_READY"):
        return "SCORED"
    return "NEW"
