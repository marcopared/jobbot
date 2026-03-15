"""Deterministic job scoring engine (SPEC §10, EPIC 5).

No LLM. Five factors, weighted sum 0-100. Explainable via stored breakdown.
"""

import json
from pathlib import Path

from core.resumes.keywords import TECH_KEYWORDS
from core.scoring.rules import (
    DOMAIN_KEYWORDS,
    JUNIOR_SIGNALS,
    LOCATION_SIGNALS,
    OVER_SENIOR_SIGNALS,
    SCORING_WEIGHTS,
    TARGET_TITLES,
)


def _load_master_skills(master_skills_path: str | None) -> set[str]:
    """Load user competencies from master_skills.json. Returns empty set if missing."""
    if not master_skills_path:
        return set()
    path = Path(master_skills_path)
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return {str(s).lower().strip() for s in data}
        if isinstance(data, dict) and "skills" in data:
            return {str(s).lower().strip() for s in data.get("skills", [])}
        return set()
    except Exception:
        return set()


def _score_title_relevance(title: str) -> float:
    """Score 0-100: match against target titles."""
    t = (title or "").lower()
    if not t.strip():
        return 0.0
    best = 0.0
    for target in TARGET_TITLES:
        if target in t:
            # Exact match of full target
            if t == target or t.startswith(target + " ") or f" {target} " in t or t.endswith(" " + target):
                return 100.0
            # Partial match
            best = max(best, 80.0)
    # Fallback: any engineering signal
    if any(x in t for x in ["engineer", "developer", "software"]):
        best = max(best, 50.0)
    return best if best > 0 else 30.0  # Default for unknown titles


def _score_seniority_fit(title: str, description: str) -> float:
    """Score 0-100: penalize junior and over-senior."""
    combined = ((title or "") + " " + (description or "")).lower()
    for sig in JUNIOR_SIGNALS:
        if sig in combined:
            return 20.0  # Strong penalty
    for sig in OVER_SENIOR_SIGNALS:
        if sig in combined:
            return 40.0  # Moderate penalty (user may still qualify)
    return 100.0  # Sweet spot: mid-level / senior without over-senior labels


def _score_domain_alignment(description: str) -> float:
    """Score 0-100: domain keyword match (capped at 100)."""
    if not description:
        return 50.0  # Neutral if no description
    d = description.lower()
    total = 0.0
    for kw, score in DOMAIN_KEYWORDS.items():
        if kw in d:
            total += score
    return min(100.0, total) if total > 0 else 50.0


def _score_location_remote(location: str | None, remote_flag: bool, description: str) -> float:
    """Score 0-100: remote/hybrid/location compatibility."""
    if remote_flag:
        return 100.0
    loc = (location or "").lower()
    desc = (description or "").lower()
    combined = loc + " " + desc
    best = 0.0
    for signal, score in LOCATION_SIGNALS.items():
        if signal in combined:
            best = max(best, score)
            break
    return best if best > 0 else 40.0  # Unknown location: moderate penalty


def _score_tech_stack(description: str, user_skills: set[str]) -> float:
    """Score 0-100: overlap between JD tech keywords and user skills."""
    if not description:
        return 50.0
    d = description.lower()
    jd_keywords: set[str] = set()
    for category_keywords in TECH_KEYWORDS.values():
        for kw in category_keywords:
            if kw in d:
                jd_keywords.add(kw)
    if not jd_keywords:
        return 50.0
    overlap = jd_keywords & user_skills
    pct = len(overlap) / len(jd_keywords) * 100
    return min(100.0, pct)


def score_job(job, master_skills_path: str | None = None) -> tuple[float, dict]:
    """
    Compute deterministic weighted score for a Job.

    Returns (total 0-100, breakdown dict).
    Breakdown keys: title_relevance, seniority_fit, domain_alignment,
    location_remote, tech_stack (each 0-100), plus weights.
    """
    title = job.normalized_title or job.title or job.raw_title or ""
    description = job.description or ""
    location = job.normalized_location or job.location
    remote_flag = getattr(job, "remote_flag", False) or False

    user_skills = _load_master_skills(master_skills_path)

    title_score = _score_title_relevance(title)
    seniority_score = _score_seniority_fit(title, description)
    domain_score = _score_domain_alignment(description)
    location_score = _score_location_remote(location, remote_flag, description)
    tech_score = _score_tech_stack(description, user_skills)

    breakdown = {
        "title_relevance": round(title_score, 1),
        "seniority_fit": round(seniority_score, 1),
        "domain_alignment": round(domain_score, 1),
        "location_remote": round(location_score, 1),
        "tech_stack": round(tech_score, 1),
        "weights": SCORING_WEIGHTS,
    }

    total = (
        title_score * SCORING_WEIGHTS["title_relevance"]
        + seniority_score * SCORING_WEIGHTS["seniority_fit"]
        + domain_score * SCORING_WEIGHTS["domain_alignment"]
        + location_score * SCORING_WEIGHTS["location_remote"]
        + tech_score * SCORING_WEIGHTS["tech_stack"]
    )  # Weights sum to 1, each factor 0-100, so total 0-100

    total = round(min(100.0, max(0.0, total)), 1)
    return total, breakdown
