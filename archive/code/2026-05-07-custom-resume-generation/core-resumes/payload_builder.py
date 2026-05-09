"""Structured payload builder for resume-generation v2."""

from __future__ import annotations

from core.resumes.effective_input import ResumeEffectiveInput
from core.resumes.evidence_types import ResumeEvidencePackage
from core.resumes.layout_types import FitResult
from core.resumes.payload_types import (
    BulletProvenance,
    ResumeBullet,
    ResumePayloadV2,
    ResumeSection,
    ResumeSectionEntry,
)
from core.resumes.rewrite import apply_conservative_rewrite
from core.resumes.v2_selection import prioritize_skills

DEFAULT_SKILL_LIMIT = 20


def _select_skills(
    evidence: ResumeEvidencePackage,
    target_keywords: tuple[str, ...],
    *,
    max_skills: int = DEFAULT_SKILL_LIMIT,
) -> tuple[str, ...]:
    return prioritize_skills(evidence.skills, target_keywords, max_skills=max_skills)


def _format_dates(start: str, end: str) -> str:
    if not start and not end:
        return ""
    return f"{start or '?'} – {end or 'present'}"


def _build_payload_bullets(
    bullet_ids: tuple[str, ...],
    evidence: ResumeEvidencePackage,
    missing_keywords: set[str],
) -> tuple[ResumeBullet, ...]:
    bullets: list[ResumeBullet] = []
    for bullet_id in bullet_ids:
        item = evidence.get_item(bullet_id)
        bullets.append(
            ResumeBullet(
                id=f"payload:{bullet_id}",
                text=apply_conservative_rewrite(item.text, missing_keywords),
                provenance=(
                    BulletProvenance(
                        evidence_id=item.id,
                        source_type=item.source_type,
                    ),
                ),
            )
        )
    return tuple(bullets)


def build_resume_payload(
    evidence: ResumeEvidencePackage,
    fit_result: FitResult,
    effective_input: ResumeEffectiveInput,
    *,
    max_skills: int = DEFAULT_SKILL_LIMIT,
) -> ResumePayloadV2:
    """Build the structured v2 payload from evidence and deterministic fit output."""
    role_lookup = {role.id: role for role in evidence.roles}
    project_lookup = {project.id: project for project in evidence.projects}
    supplemental_lookup = {entry.id: entry for entry in evidence.supplemental_entries}
    missing_keywords = set(fit_result.missing_keywords)

    experience_entries = []
    for selection in fit_result.role_selections:
        role = role_lookup[selection.entry_id]
        experience_entries.append(
            ResumeSectionEntry(
                id=role.id,
                heading=role.title,
                subheading=role.company,
                dates=_format_dates(role.start, role.end),
                bullets=_build_payload_bullets(selection.bullet_ids, evidence, missing_keywords),
            )
        )

    highlight_entries = []
    for selection in fit_result.supplemental_selections:
        entry = supplemental_lookup[selection.entry_id]
        highlight_entries.append(
            ResumeSectionEntry(
                id=entry.id,
                heading=entry.heading,
                subheading=entry.subheading,
                dates=entry.dates,
                bullets=_build_payload_bullets(selection.bullet_ids, evidence, missing_keywords),
            )
        )

    project_entries = []
    for selection in fit_result.project_selections:
        project = project_lookup[selection.entry_id]
        project_entries.append(
            ResumeSectionEntry(
                id=project.id,
                heading=project.name,
                subheading="",
                dates="",
                bullets=_build_payload_bullets(selection.bullet_ids, evidence, missing_keywords),
            )
        )

    sections: list[ResumeSection] = [
        ResumeSection(
            id="summary",
            kind="summary",
            title="Summary",
            body=evidence.summary_for_persona(fit_result.target_persona),
        ),
    ]
    if highlight_entries:
        sections.append(
            ResumeSection(
                id="highlights",
                kind="highlights",
                title="Highlights",
                entries=tuple(highlight_entries),
            )
        )
    sections.extend(
        [
            ResumeSection(
                id="skills",
                kind="skills",
                title="Skills",
                lines=_select_skills(
                    evidence,
                    fit_result.target_keywords,
                    max_skills=max_skills,
                ),
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
                lines=tuple(
                    f"{record.degree} — {record.school} ({record.year})"
                    for record in evidence.education
                ),
            ),
        ]
    )

    return ResumePayloadV2(
        contact=evidence.contact,
        sections=tuple(sections),
        target_persona=fit_result.target_persona,
        effective_input_hash=effective_input.compute_hash(),
        inventory_version_hash=evidence.inventory_version_hash,
    )
