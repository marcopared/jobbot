"""Score computation (SPEC §10.2)."""

from core.scoring.rules import SCORING_RULES


def score_job(job) -> tuple[float, dict]:
    """Compute score for a Job. Returns (total, breakdown)."""
    breakdown = {}
    total = 0.0

    # Title scoring
    title_lower = (job.title or "").lower()
    title_score = 0.0
    for keyword, weight in SCORING_RULES["title_keywords"]["positive"].items():
        if keyword in title_lower:
            title_score += weight
    for keyword, weight in SCORING_RULES["title_keywords"]["negative"].items():
        if keyword in title_lower:
            title_score += weight
    breakdown["title_match"] = title_score
    total += title_score

    # Description scoring
    if job.description:
        desc_lower = job.description.lower()
        desc_score = 0.0
        for keyword, weight in SCORING_RULES["description_keywords"].items():
            if keyword in desc_lower:
                desc_score += weight
        breakdown["description_keywords"] = desc_score
        total += desc_score

    # Location scoring
    if job.location:
        loc_lower = job.location.lower()
        loc_score = 0.0
        for keyword, weight in SCORING_RULES["location"].items():
            if keyword in loc_lower:
                loc_score += weight
                break
        breakdown["location"] = loc_score
        total += loc_score

    # Remote bonus
    if job.remote_flag:
        breakdown["remote"] = 1.5
        total += 1.5

    return total, breakdown
