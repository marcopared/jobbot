"""Deterministic ATS keyword extraction from job descriptions (EPIC 5).

No LLM. Extracts tech keywords with synonym mapping and normalization.
Compares against user competencies (master_skills) to produce found/missing.
"""

import json
from pathlib import Path
from typing import NamedTuple

from core.resumes.keywords import SYNONYM_MAP, TECH_KEYWORDS, normalize_keyword


def _extract_jd_keywords(text: str) -> set[str]:
    """
    Extract tech keywords from job description with synonym normalization.

    Checks both canonical keywords and synonym variants in text
    (e.g. "postgres" in text -> add "postgresql").
    """
    if not text or not text.strip():
        return set()
    text_lower = text.lower()
    found: set[str] = set()

    # Direct canonical matches
    for kw in set().union(*TECH_KEYWORDS.values()):
        if kw in text_lower:
            found.add(kw)

    # Synonym-in-text: if "postgres" in text, add canonical "postgresql"
    for synonym, canonical in SYNONYM_MAP.items():
        if synonym in text_lower:
            found.add(canonical)

    return found


def _load_user_skills(path: str | None) -> set[str]:
    """Load user competencies from master_skills.json. Normalized to lowercase."""
    if not path:
        return set()
    p = Path(path)
    if not p.is_file():
        return set()
    try:
        data = json.loads(p.read_text())
        if isinstance(data, list):
            skills = data
        elif isinstance(data, dict) and "skills" in data:
            skills = data["skills"]
        else:
            return set()
        return {normalize_keyword(str(s)) for s in skills}
    except Exception:
        return set()


class ATSExtractionResult(NamedTuple):
    """Result of deterministic ATS extraction."""

    found_keywords: list[str]
    missing_keywords: list[str]
    ats_categories: dict[str, list[str]]  # category -> keywords found in JD
    ats_compatibility_score: float
    total_jd_keywords: int


def extract_ats_signals(
    job_description: str,
    user_skills_path: str | None = None,
    user_skills: set[str] | None = None,
) -> ATSExtractionResult:
    """
    Deterministic ATS extraction from job description.

    - Extract keywords from JD (with synonym mapping)
    - Compare against user skills (from path or explicit set)
    - Return found (user has), missing (user doesn't), categories, score

    Score: percent of JD keywords that user has (0-100).
    """
    jd_keywords = _extract_jd_keywords(job_description or "")
    skills = user_skills if user_skills is not None else _load_user_skills(user_skills_path)
    skills_normalized = {normalize_keyword(s) for s in skills}

    found = sorted(jd_keywords & skills_normalized)
    missing = sorted(jd_keywords - skills_normalized)

    # Group JD keywords by category for inspectability
    categories: dict[str, list[str]] = {}
    for cat, kws in TECH_KEYWORDS.items():
        in_jd = sorted(jd_keywords & kws)
        if in_jd:
            categories[cat] = in_jd

    score = 0.0
    if jd_keywords:
        score = round(len(jd_keywords & skills_normalized) / len(jd_keywords) * 100, 1)

    return ATSExtractionResult(
        found_keywords=found,
        missing_keywords=missing,
        ats_categories=categories,
        ats_compatibility_score=score,
        total_jd_keywords=len(jd_keywords),
    )
