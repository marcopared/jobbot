"""Deterministic builders for the resume-generation v2 domain model."""

from __future__ import annotations

from core.inventory.types import ExperienceInventory
from core.matching import keyword_in_text
from core.resumes.effective_input import ResumeEffectiveInput
from core.resumes.evidence_types import (
    ResumeContact,
    ResumeEducationRecord,
    ResumeEvidenceItem,
    ResumeEvidencePackage,
    ResumeEvidenceProject,
    ResumeEvidenceRole,
)
from core.resumes.layout_types import (
    FitResult,
    FitSelection,
    LayoutPlan,
    LayoutSectionPlan,
)
from core.resumes.payload_types import (
    BulletProvenance,
    ResumeBullet,
    ResumePayloadV2,
    ResumeSection,
    ResumeSectionEntry,
)
from core.resumes.rewrite import apply_conservative_rewrite

DEFAULT_ROLE_LIMIT = 4
DEFAULT_ROLE_BULLET_LIMIT = 5
DEFAULT_PROJECT_LIMIT = 2
DEFAULT_PROJECT_BULLET_LIMIT = 3
DEFAULT_SKILL_LIMIT = 20


def build_inventory_evidence_package(
    inventory: ExperienceInventory,
    inventory_hash: str,
) -> ResumeEvidencePackage:
    """Convert inventory-only content into the v2 evidence package."""
    items: list[ResumeEvidenceItem] = []
    roles: list[ResumeEvidenceRole] = []
    projects: list[ResumeEvidenceProject] = []

    for role_index, role in enumerate(inventory.roles or []):
        role_id = f"role:{role_index}"
        bullet_ids: list[str] = []
        for bullet_index, bullet in enumerate(role.bullets or []):
            bullet_id = f"{role_id}:bullet:{bullet_index}"
            bullet_ids.append(bullet_id)
            items.append(
                ResumeEvidenceItem(
                    id=bullet_id,
                    source_type="inventory",
                    item_type="role_bullet",
                    text=bullet.text,
                    tags=tuple(bullet.tags or []),
                    metrics=tuple(bullet.metrics or []),
                    parent_id=role_id,
                    attributes=(
                        ("company", role.company),
                        ("title", role.title),
                        ("location", role.location),
                        ("start", role.start),
                        ("end", role.end),
                    ),
                )
            )
        roles.append(
            ResumeEvidenceRole(
                id=role_id,
                company=role.company,
                title=role.title,
                location=role.location,
                start=role.start,
                end=role.end,
                tags=tuple(role.tags or []),
                bullet_ids=tuple(bullet_ids),
            )
        )

    for project_index, project in enumerate(inventory.projects or []):
        project_id = f"project:{project_index}"
        bullet_ids: list[str] = []
        for bullet_index, bullet in enumerate(project.bullets or []):
            bullet_id = f"{project_id}:bullet:{bullet_index}"
            bullet_ids.append(bullet_id)
            items.append(
                ResumeEvidenceItem(
                    id=bullet_id,
                    source_type="inventory",
                    item_type="project_bullet",
                    text=bullet.text,
                    tags=tuple(bullet.tags or []),
                    metrics=tuple(bullet.metrics or []),
                    parent_id=project_id,
                    attributes=(
                        ("name", project.name),
                        ("description", project.description),
                    ),
                )
            )
        projects.append(
            ResumeEvidenceProject(
                id=project_id,
                name=project.name,
                description=project.description,
                url=project.url,
                bullet_ids=tuple(bullet_ids),
            )
        )

    return ResumeEvidencePackage(
        contact=ResumeContact(
            name=inventory.contact.name,
            email=inventory.contact.email,
            location=inventory.contact.location,
            linkedin_url=inventory.contact.linkedin_url,
        ),
        summary_variants=tuple(sorted((inventory.summary_variants or {}).items())),
        skills=tuple(inventory.skills or []),
        education=tuple(
            ResumeEducationRecord(
                school=str(record.get("school", "")),
                degree=str(record.get("degree", "")),
                year=str(record.get("year", "")),
            )
            for record in (inventory.education or [])
        ),
        roles=tuple(roles),
        projects=tuple(projects),
        items=tuple(items),
        inventory_version_hash=inventory_hash,
        source_kind="inventory-only",
    )


def _persona_tag_match(tags: tuple[str, ...], persona: str) -> bool:
    tags_lower = {tag.lower() for tag in tags}
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


def _keyword_overlap(item: ResumeEvidenceItem, keywords: set[str]) -> int:
    tags_lower = {tag.lower() for tag in item.tags}
    overlap = 0
    for keyword in keywords:
        normalized = keyword.lower()
        if keyword_in_text(item.text, normalized):
            overlap += 1
        elif normalized in tags_lower:
            overlap += 1
    return overlap


def _score_item(item: ResumeEvidenceItem, target_keywords: set[str], persona: str) -> float:
    score = float(_keyword_overlap(item, target_keywords)) * 2.0
    if _persona_tag_match(item.tags, persona):
        score += 5.0
    return score


def _select_group(
    entry_id: str,
    bullet_ids: tuple[str, ...],
    item_lookup: dict[str, ResumeEvidenceItem],
    target_keywords: set[str],
    persona: str,
    max_bullets: int,
) -> tuple[tuple[str, ...], float]:
    scored_bullets = [
        (bullet_id, _score_item(item_lookup[bullet_id], target_keywords, persona), index)
        for index, bullet_id in enumerate(bullet_ids)
    ]
    scored_bullets.sort(key=lambda item: (-item[1], item[2]))
    selected_ids = tuple(bullet_id for bullet_id, _, _ in scored_bullets[:max_bullets])
    total_score = sum(score for _, score, _ in scored_bullets)
    return selected_ids, total_score


def build_fit_result(
    evidence: ResumeEvidencePackage,
    *,
    persona: str,
    target_keywords: set[str],
    found_keywords: set[str] | None = None,
    missing_keywords: set[str] | None = None,
    max_roles: int = DEFAULT_ROLE_LIMIT,
    max_role_bullets: int = DEFAULT_ROLE_BULLET_LIMIT,
    max_projects: int = DEFAULT_PROJECT_LIMIT,
    max_project_bullets: int = DEFAULT_PROJECT_BULLET_LIMIT,
) -> FitResult:
    """Score evidence items and select deterministic experience/project content."""
    item_lookup = {item.id: item for item in evidence.items}

    role_candidates: list[tuple[FitSelection, int]] = []
    for index, role in enumerate(evidence.roles):
        selected_ids, total_score = _select_group(
            role.id,
            role.bullet_ids,
            item_lookup,
            target_keywords,
            persona,
            max_role_bullets,
        )
        if _persona_tag_match(role.tags, persona):
            total_score += 3.0
        if selected_ids:
            role_candidates.append(
                (
                    FitSelection(
                        entry_id=role.id,
                        bullet_ids=selected_ids,
                        score=total_score,
                    ),
                    index,
                )
            )
    role_candidates.sort(key=lambda candidate: (-candidate[0].score, candidate[1]))

    project_candidates: list[tuple[FitSelection, int]] = []
    for index, project in enumerate(evidence.projects):
        selected_ids, total_score = _select_group(
            project.id,
            project.bullet_ids,
            item_lookup,
            target_keywords,
            persona,
            max_project_bullets,
        )
        if selected_ids:
            project_candidates.append(
                (
                    FitSelection(
                        entry_id=project.id,
                        bullet_ids=selected_ids,
                        score=total_score,
                    ),
                    index,
                )
            )
    project_candidates.sort(key=lambda candidate: (-candidate[0].score, candidate[1]))

    return FitResult(
        target_persona=persona,
        target_keywords=tuple(sorted(keyword.lower() for keyword in target_keywords)),
        found_keywords=tuple(sorted(keyword.lower() for keyword in (found_keywords or set()))),
        missing_keywords=tuple(
            sorted(keyword.lower() for keyword in (missing_keywords or set()))
        ),
        role_selections=tuple(selection for selection, _ in role_candidates[:max_roles]),
        project_selections=tuple(selection for selection, _ in project_candidates[:max_projects]),
    )


def build_effective_input(
    evidence: ResumeEvidencePackage,
    fit_result: FitResult,
    *,
    template_version: str,
) -> ResumeEffectiveInput:
    """Build the deterministic effective-input fingerprint for generation."""
    return ResumeEffectiveInput(
        evidence_hash=evidence.compute_hash(),
        fit_hash=fit_result.compute_hash(),
        target_persona=fit_result.target_persona,
        target_keywords=fit_result.target_keywords,
        selected_evidence_ids=fit_result.selected_evidence_ids,
        template_version=template_version,
    )


def _select_skills(
    evidence: ResumeEvidencePackage,
    target_keywords: tuple[str, ...],
    *,
    max_skills: int = DEFAULT_SKILL_LIMIT,
) -> tuple[str, ...]:
    keyword_set = {keyword.lower() for keyword in target_keywords}
    matched = [skill for skill in evidence.skills if skill.strip().lower() in keyword_set]
    rest = [skill for skill in evidence.skills if skill.strip().lower() not in keyword_set]
    return tuple((matched + rest)[:max_skills])


def _format_dates(start: str, end: str) -> str:
    if not start and not end:
        return ""
    return f"{start or '?'} – {end or 'present'}"


def build_resume_payload(
    evidence: ResumeEvidencePackage,
    fit_result: FitResult,
    effective_input: ResumeEffectiveInput,
) -> ResumePayloadV2:
    """Build the structured v2 payload from evidence and fit selections."""
    role_lookup = {role.id: role for role in evidence.roles}
    project_lookup = {project.id: project for project in evidence.projects}
    item_lookup = {item.id: item for item in evidence.items}
    missing_keywords = set(fit_result.missing_keywords)

    experience_entries = []
    for selection in fit_result.role_selections:
        role = role_lookup[selection.entry_id]
        bullets = tuple(
            ResumeBullet(
                id=f"payload:{bullet_id}",
                text=apply_conservative_rewrite(item_lookup[bullet_id].text, missing_keywords),
                provenance=(
                    BulletProvenance(
                        evidence_id=bullet_id,
                        source_type=item_lookup[bullet_id].source_type,
                    ),
                ),
            )
            for bullet_id in selection.bullet_ids
        )
        experience_entries.append(
            ResumeSectionEntry(
                id=role.id,
                heading=role.title,
                subheading=role.company,
                dates=_format_dates(role.start, role.end),
                bullets=bullets,
            )
        )

    project_entries = []
    for selection in fit_result.project_selections:
        project = project_lookup[selection.entry_id]
        bullets = tuple(
            ResumeBullet(
                id=f"payload:{bullet_id}",
                text=apply_conservative_rewrite(item_lookup[bullet_id].text, missing_keywords),
                provenance=(
                    BulletProvenance(
                        evidence_id=bullet_id,
                        source_type=item_lookup[bullet_id].source_type,
                    ),
                ),
            )
            for bullet_id in selection.bullet_ids
        )
        project_entries.append(
            ResumeSectionEntry(
                id=project.id,
                heading=project.name,
                subheading="",
                dates="",
                bullets=bullets,
            )
        )

    education_lines = tuple(
        f"{record.degree} — {record.school} ({record.year})"
        for record in evidence.education
    )

    sections = (
        ResumeSection(
            id="summary",
            kind="summary",
            title="Summary",
            body=evidence.summary_for_persona(fit_result.target_persona),
        ),
        ResumeSection(
            id="skills",
            kind="skills",
            title="Skills",
            lines=_select_skills(evidence, fit_result.target_keywords),
        ),
        ResumeSection(
            id="experience",
            kind="experience",
            title="Experience",
            entries=tuple(experience_entries),
        ),
        ResumeSection(
            id="projects",
            kind="projects",
            title="Projects",
            entries=tuple(project_entries),
        ),
        ResumeSection(
            id="education",
            kind="education",
            title="Education",
            lines=education_lines,
        ),
    )

    return ResumePayloadV2(
        contact=evidence.contact,
        sections=sections,
        target_persona=fit_result.target_persona,
        effective_input_hash=effective_input.compute_hash(),
        inventory_version_hash=evidence.inventory_version_hash,
    )


def build_layout_plan(
    payload: ResumePayloadV2,
    *,
    template_version: str,
) -> LayoutPlan:
    """Build the static render-time layout plan for the current template."""
    return LayoutPlan(
        effective_input_hash=payload.effective_input_hash,
        template_version=template_version,
        sections=(
            LayoutSectionPlan(section_id="summary", order=1, title="Summary"),
            LayoutSectionPlan(section_id="skills", order=2, title="Skills"),
            LayoutSectionPlan(
                section_id="experience",
                order=3,
                title="Experience",
                max_entries=DEFAULT_ROLE_LIMIT,
                max_bullets_per_entry=DEFAULT_ROLE_BULLET_LIMIT,
            ),
            LayoutSectionPlan(
                section_id="projects",
                order=4,
                title="Projects",
                max_entries=DEFAULT_PROJECT_LIMIT,
                max_bullets_per_entry=DEFAULT_PROJECT_BULLET_LIMIT,
            ),
            LayoutSectionPlan(section_id="education", order=5, title="Education"),
        ),
    )
