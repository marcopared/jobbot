"""Deterministic existing-resume recommendation for the local MVP.

The MVP does not create tailored resumes. It reads a small user-maintained
catalog of existing resumes, extracts years-of-experience requirements from the
job description/title, compares skills/persona fit, and returns the best resume
for the user to apply with manually.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from core.matching import keywords_in_text

DEFAULT_RESUME_CATALOG_PATH = "data/resumes.yaml"


@dataclass(frozen=True)
class ResumeSuggestion:
    resume_id: str
    label: str
    path: str | None
    score: float
    rationale: str
    years_required: int | None
    resume_years: int | None
    matched_skills: list[str]
    missing_skills: list[str]
    persona_match: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "resume_id": self.resume_id,
            "label": self.label,
            "path": self.path,
            "score": round(self.score, 4),
            "rationale": self.rationale,
            "years_required": self.years_required,
            "resume_years": self.resume_years,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "persona_match": self.persona_match,
        }


def extract_years_required(text: str | None) -> int | None:
    """Extract the largest explicit years-of-experience requirement from text."""
    if not text:
        return None
    patterns = [
        r"(\d{1,2})\s*\+?\s*(?:years|yrs)\s+(?:of\s+)?(?:professional\s+)?experience",
        r"(?:at\s+least|minimum\s+of|min\.?|minimum)\s*(\d{1,2})\s*\+?\s*(?:years|yrs)",
        r"(\d{1,2})\s*\+?\s*(?:years|yrs)\s+in\b",
    ]
    found: list[int] = []
    for pattern in patterns:
        found.extend(int(match) for match in re.findall(pattern, text, flags=re.IGNORECASE))
    return max(found) if found else None


def load_resume_catalog(path: str | Path = DEFAULT_RESUME_CATALOG_PATH) -> list[dict[str, Any]]:
    catalog_path = Path(path)
    if not catalog_path.exists():
        return []
    data = yaml.safe_load(catalog_path.read_text()) or {}
    resumes = data.get("resumes", [])
    return [r for r in resumes if isinstance(r, dict) and r.get("id") and r.get("label")]


def suggest_resume_for_job(
    *,
    title: str | None,
    description: str | None,
    matched_persona: str | None,
    catalog_path: str | Path = DEFAULT_RESUME_CATALOG_PATH,
) -> ResumeSuggestion | None:
    """Return the best existing resume for a job, or None if no catalog exists."""
    resumes = load_resume_catalog(catalog_path)
    if not resumes:
        return None

    text = "\n".join(part for part in [title or "", description or ""] if part)
    years_required = extract_years_required(text)
    scored: list[ResumeSuggestion] = []
    for resume in resumes:
        skills = {str(skill) for skill in resume.get("skills", []) if str(skill).strip()}
        matched_skills = sorted(keywords_in_text(text, skills), key=str.lower)
        missing_skills = sorted(skills - set(matched_skills), key=str.lower)
        resume_years = _as_int(resume.get("years_experience"))
        persona = str(resume.get("persona") or "")
        persona_match = bool(matched_persona and persona and persona.upper() == matched_persona.upper())

        skill_score = len(matched_skills) / max(len(skills), 1)
        persona_score = 1.0 if persona_match else 0.0
        years_score = _years_fit_score(resume_years, years_required)
        total = (0.50 * skill_score) + (0.30 * persona_score) + (0.20 * years_score)

        rationale_parts = []
        if persona_match:
            rationale_parts.append(f"matches persona {matched_persona}")
        if years_required is not None and resume_years is not None:
            rationale_parts.append(f"covers {years_required}+ years requirement with {resume_years} years")
        elif years_required is None:
            rationale_parts.append("no explicit years requirement found")
        if matched_skills:
            rationale_parts.append("matches skills: " + ", ".join(matched_skills[:8]))
        if not rationale_parts:
            rationale_parts.append("highest deterministic catalog score")

        scored.append(
            ResumeSuggestion(
                resume_id=str(resume["id"]),
                label=str(resume["label"]),
                path=str(resume.get("path")) if resume.get("path") else None,
                score=total,
                rationale="; ".join(rationale_parts),
                years_required=years_required,
                resume_years=resume_years,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                persona_match=persona_match,
            )
        )

    return max(scored, key=lambda item: (item.score, item.persona_match, len(item.matched_skills)))


def _years_fit_score(resume_years: int | None, required_years: int | None) -> float:
    if required_years is None:
        return 0.75
    if resume_years is None:
        return 0.0
    if resume_years >= required_years:
        return 1.0
    return max(0.0, resume_years / max(required_years, 1))


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
