"""Legacy inventory-native selection helpers.

This module is not the authoritative resume-v2 execution path. Resume-v2
selection semantics are owned by ``core.resumes.v2_selection`` and are applied
at runtime via ``core.resumes.v2_pipeline.build_fit_result``. The helpers here
remain as inventory-native adapters for legacy callers and focused unit tests,
but they delegate their scoring/ordering rules to the shared v2 semantics.
"""

from core.inventory.types import (
    ExperienceInventory,
    RoleBullet,
    Role,
    ProjectBullet,
    Project,
)
from core.resumes.v2_selection import persona_tag_match, prioritize_skills, score_text_tags


def _bullet_keyword_overlap(bullet: RoleBullet | ProjectBullet, keywords: set[str]) -> int:
    """Count overlap between bullet text/tags and target keywords (normalized).
    Text uses word-boundary matching; tags use exact set membership."""
    from core.resumes.v2_selection import keyword_overlap

    return keyword_overlap(bullet.text, bullet.tags or [], keywords)


def _persona_tag_match(bullet: RoleBullet | ProjectBullet, persona: str) -> bool:
    """True if bullet has tags aligning with the job's persona."""
    return persona_tag_match(bullet.tags or [], persona)


def _score_bullet(
    bullet: RoleBullet | ProjectBullet,
    target_keywords: set[str],
    persona: str,
    prefer_persona: bool = True,
) -> float:
    """Score a bullet for relevance. Higher = better fit."""
    return score_text_tags(
        bullet.text,
        bullet.tags or [],
        target_keywords,
        persona,
        prefer_persona=prefer_persona,
    )


def select_role_bullets(
    role: Role,
    target_keywords: set[str],
    persona: str,
    max_bullets: int = 5,
) -> list[str]:
    """
    Select and order role bullets for resume.
    Returns list of bullet text strings (grounded in inventory).
    """
    if not role.bullets:
        return []
    scored = [
        (b, _score_bullet(b, target_keywords, persona))
        for b in role.bullets
    ]
    scored.sort(key=lambda x: -x[1])
    return [b.text for b, _ in scored[:max_bullets]]


def select_project_bullets(
    project: Project,
    target_keywords: set[str],
    persona: str,
    max_bullets: int = 3,
) -> list[str]:
    """Select project bullets; returns list of bullet text strings."""
    if not project.bullets:
        return []
    scored = [
        (b, _score_bullet(b, target_keywords, persona))
        for b in project.bullets
    ]
    scored.sort(key=lambda x: -x[1])
    return [b.text for b, _ in scored[:max_bullets]]


def select_roles(
    inventory: ExperienceInventory,
    target_keywords: set[str],
    persona: str,
    max_roles: int = 4,
) -> list[tuple[Role, list[str]]]:
    """
    Select roles and their bullets for the resume.
    Returns list of (role, selected_bullets).
    """
    if not inventory.roles:
        return []
    role_scores: list[tuple[Role, float]] = []
    for role in inventory.roles:
        total = sum(
            _score_bullet(b, target_keywords, persona)
            for b in (role.bullets or [])
        )
        role_tags = getattr(role, "tags", None) or []
        if role_tags:
            if _persona_tag_match(RoleBullet(text="", tags=list(role_tags)), persona):
                total += 3.0
        role_scores.append((role, total))
    role_scores.sort(key=lambda x: -x[1])
    result: list[tuple[Role, list[str]]] = []
    for role, _ in role_scores[:max_roles]:
        bullets = select_role_bullets(role, target_keywords, persona)
        if bullets:
            result.append((role, bullets))
    return result


def select_projects(
    inventory: ExperienceInventory,
    target_keywords: set[str],
    persona: str,
    max_projects: int = 2,
) -> list[tuple[Project, list[str]]]:
    """Select projects and their bullets for the resume."""
    if not inventory.projects:
        return []
    proj_scores: list[tuple[Project, float]] = []
    for proj in inventory.projects:
        total = sum(
            _score_bullet(b, target_keywords, persona)
            for b in (proj.bullets or [])
        )
        proj_scores.append((proj, total))
    proj_scores.sort(key=lambda x: -x[1])
    result: list[tuple[Project, list[str]]] = []
    for proj, _ in proj_scores[:max_projects]:
        bullets = select_project_bullets(proj, target_keywords, persona)
        if bullets:
            result.append((proj, bullets))
    return result


def select_skills(
    inventory: ExperienceInventory,
    target_keywords: set[str],
    max_skills: int = 20,
) -> list[str]:
    """
    Select and order skills for resume.
    Front-loads skills that match target keywords (ATS).
    """
    all_skills = inventory.skills or []
    if not all_skills:
        return []
    return list(prioritize_skills(all_skills, target_keywords, max_skills=max_skills))
