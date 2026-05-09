"""Shared selection semantics for resume-generation v2.

This module owns the deterministic ranking rules used by the v2 execution path.
Legacy inventory-native helpers in ``core.resumes.selection`` delegate here so
keyword/persona/skill ordering rules cannot drift between paths.
"""

from __future__ import annotations

from collections.abc import Iterable

from core.matching import keyword_in_text


def keyword_overlap(text: str, tags: Iterable[str] | None, keywords: set[str]) -> int:
    """Count keyword overlap using word-boundary text matching plus exact tag matches."""
    tags_lower = {tag.lower() for tag in (tags or [])}
    overlap = 0
    for keyword in keywords:
        normalized = keyword.lower()
        if keyword_in_text(text, normalized):
            overlap += 1
        elif normalized in tags_lower:
            overlap += 1
    return overlap


def persona_tag_match(tags: Iterable[str] | None, persona: str) -> bool:
    """Return True when tags align with the requested persona."""
    tags_lower = {tag.lower() for tag in (tags or [])}
    persona_lower = persona.lower()
    if "backend" in persona_lower and ("backend" in tags_lower or "api" in tags_lower):
        return True
    if "platform" in persona_lower or "infra" in persona_lower:
        if any(
            tag in tags_lower
            for tag in ("platform", "infra", "kubernetes", "k8s", "ci/cd", "aws", "docker")
        ):
            return True
    if "hybrid" in persona_lower:
        return True
    return False


def score_text_tags(
    text: str,
    tags: Iterable[str] | None,
    target_keywords: set[str],
    persona: str,
    *,
    prefer_persona: bool = True,
) -> float:
    """Score one evidence text+tag unit for deterministic v2 selection."""
    score = float(keyword_overlap(text, tags, target_keywords)) * 2.0
    if prefer_persona and persona_tag_match(tags, persona):
        score += 5.0
    return score


def prioritize_skills(
    skills: Iterable[str],
    target_keywords: Iterable[str],
    *,
    max_skills: int,
) -> tuple[str, ...]:
    """Front-load exact keyword-matching skills while preserving original stable order."""
    keyword_set = {keyword.lower() for keyword in target_keywords}
    skill_list = list(skills)
    matched = [skill for skill in skill_list if skill.strip().lower() in keyword_set]
    rest = [skill for skill in skill_list if skill.strip().lower() not in keyword_set]
    return tuple((matched + rest)[:max_skills])
