"""Grounded bullet selection for resume generation (EPIC 7).

Selects content from structured inventory based on job score, ATS analysis,
and persona. No freeform LLM output; all content is from inventory.
Uses word-boundary matching for keyword overlap to avoid false positives.
"""

from core.inventory.types import (
    ExperienceInventory,
    RoleBullet,
    Role,
    ProjectBullet,
    Project,
)
from core.matching import keyword_in_text


def _bullet_keyword_overlap(bullet: RoleBullet | ProjectBullet, keywords: set[str]) -> int:
    """Count overlap between bullet text/tags and target keywords (normalized).
    Text uses word-boundary matching; tags use exact set membership."""
    tags_lower = {t.lower() for t in (bullet.tags or [])}
    overlap = 0
    for kw in keywords:
        kw_lower = kw.lower()
        if keyword_in_text(bullet.text, kw_lower):
            overlap += 1
        elif kw_lower in tags_lower:
            overlap += 1
    return overlap


def _persona_tag_match(bullet: RoleBullet | ProjectBullet, persona: str) -> bool:
    """True if bullet has tags aligning with the job's persona."""
    if not bullet.tags:
        return False
    tags_lower = {t.lower() for t in bullet.tags}
    persona_lower = persona.lower()
    if "backend" in persona_lower and ("backend" in tags_lower or "api" in tags_lower):
        return True
    if "platform" in persona_lower or "infra" in persona_lower:
        if any(
            t in tags_lower
            for t in ("platform", "infra", "kubernetes", "k8s", "ci/cd", "aws", "docker")
        ):
            return True
    if "hybrid" in persona_lower:
        return True
    return False


def _score_bullet(
    bullet: RoleBullet | ProjectBullet,
    target_keywords: set[str],
    persona: str,
    prefer_persona: bool = True,
) -> float:
    """Score a bullet for relevance. Higher = better fit."""
    keyword_overlap = _bullet_keyword_overlap(bullet, target_keywords)
    persona_match = 1.0 if _persona_tag_match(bullet, persona) else 0.0
    base = float(keyword_overlap) * 2.0
    if prefer_persona and persona_match:
        base += 5.0
    return base


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
    kw_lower = {k.lower() for k in target_keywords}
    matched = [s for s in all_skills if s.strip().lower() in kw_lower]
    rest = [s for s in all_skills if s.strip().lower() not in kw_lower]
    combined = matched + rest
    return combined[:max_skills]
