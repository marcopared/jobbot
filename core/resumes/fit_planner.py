"""Deterministic fit planning and compaction for resume-generation v2.

Selection semantics are owned by ``core.resumes.v2_selection`` and applied
through ``core.resumes.v2_pipeline.build_fit_result``. This planner only
compacts the already-authoritative v2 selection output.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from core.resumes.effective_input import ResumeEffectiveInput
from core.resumes.evidence_types import ResumeEvidencePackage
from core.resumes.layout_types import (
    DEFAULT_LAYOUT_LIMITS,
    DEFAULT_PAGE_GEOMETRY,
    FitDiagnostics,
    FitResult,
    LayoutLimits,
    LayoutPlan,
    SectionMeasurement,
)
from core.resumes.payload_types import ResumePayloadV2, ResumeSection, ResumeSectionEntry
from core.resumes.v2_pipeline import (
    build_effective_input,
    build_fit_result,
    build_layout_plan,
    build_resume_payload,
)

_NAME_BLOCK_HEIGHT_PT = 26.0
_CONTACT_BLOCK_HEIGHT_PT = 18.0
_SECTION_TITLE_HEIGHT_PT = 22.0
_SECTION_SPACING_PT = 10.0
_ENTRY_SPACING_PT = 8.0
_ENTRY_HEADER_HEIGHT_PT = 15.0
_BODY_LINE_HEIGHT_PT = 13.5
_BULLET_GAP_PT = 3.0
_FIT_SAFETY_RESERVE_PT = 18.0
_SUMMARY_CHARS_PER_LINE = 92
_SKILLS_CHARS_PER_LINE = 110
_ENTRY_HEADER_CHARS_PER_LINE = 52
_BULLET_CHARS_PER_LINE = 95
_EDUCATION_CHARS_PER_LINE = 84


FIT_COMPACTION_PROFILES: tuple[LayoutLimits, ...] = (
    DEFAULT_LAYOUT_LIMITS,
    LayoutLimits(
        label="projects_bullets_tight",
        max_roles=4,
        max_role_bullets=5,
        max_projects=2,
        max_project_bullets=1,
        max_supplemental_entries=2,
        max_supplemental_bullets=2,
        max_skills=20,
    ),
    LayoutLimits(
        label="projects_trimmed",
        max_roles=4,
        max_role_bullets=5,
        max_projects=1,
        max_project_bullets=1,
        max_supplemental_entries=2,
        max_supplemental_bullets=2,
        max_skills=18,
    ),
    LayoutLimits(
        label="projects_removed",
        max_roles=4,
        max_role_bullets=5,
        max_projects=0,
        max_project_bullets=0,
        max_supplemental_entries=2,
        max_supplemental_bullets=2,
        max_skills=18,
    ),
    LayoutLimits(
        label="supplemental_trimmed",
        max_roles=4,
        max_role_bullets=5,
        max_projects=0,
        max_project_bullets=0,
        max_supplemental_entries=1,
        max_supplemental_bullets=1,
        max_skills=16,
    ),
    LayoutLimits(
        label="supplemental_removed",
        max_roles=4,
        max_role_bullets=5,
        max_projects=0,
        max_project_bullets=0,
        max_supplemental_entries=0,
        max_supplemental_bullets=0,
        max_skills=16,
    ),
    LayoutLimits(
        label="skills_trimmed",
        max_roles=4,
        max_role_bullets=5,
        max_projects=0,
        max_project_bullets=0,
        max_supplemental_entries=0,
        max_supplemental_bullets=0,
        max_skills=12,
    ),
    LayoutLimits(
        label="role_bullets_tight",
        max_roles=4,
        max_role_bullets=4,
        max_projects=0,
        max_project_bullets=0,
        max_supplemental_entries=0,
        max_supplemental_bullets=0,
        max_skills=12,
    ),
    LayoutLimits(
        label="role_bullets_compact",
        max_roles=4,
        max_role_bullets=3,
        max_projects=0,
        max_project_bullets=0,
        max_supplemental_entries=0,
        max_supplemental_bullets=0,
        max_skills=12,
    ),
    LayoutLimits(
        label="role_bullets_min",
        max_roles=4,
        max_role_bullets=2,
        max_projects=0,
        max_project_bullets=0,
        max_supplemental_entries=0,
        max_supplemental_bullets=0,
        max_skills=10,
    ),
    LayoutLimits(
        label="roles_compact",
        max_roles=3,
        max_role_bullets=2,
        max_projects=0,
        max_project_bullets=0,
        max_supplemental_entries=0,
        max_supplemental_bullets=0,
        max_skills=10,
    ),
    LayoutLimits(
        label="roles_min",
        max_roles=2,
        max_role_bullets=2,
        max_projects=0,
        max_project_bullets=0,
        max_supplemental_entries=0,
        max_supplemental_bullets=0,
        max_skills=8,
    ),
)


@dataclass(frozen=True)
class PlannedResumeArtifacts:
    """Structured artifacts selected by the deterministic fit planner."""

    fit_result: FitResult
    effective_input: ResumeEffectiveInput
    payload: ResumePayloadV2
    layout_plan: LayoutPlan
    fit_diagnostics: FitDiagnostics


def _line_count(text: str, chars_per_line: int) -> int:
    normalized = " ".join(text.split())
    if not normalized:
        return 0
    return max(1, ceil(len(normalized) / chars_per_line))


def _estimate_entry_height(entry: ResumeSectionEntry) -> float:
    height = max(
        _ENTRY_HEADER_HEIGHT_PT,
        _line_count(
            " ".join(part for part in (entry.heading, entry.subheading, entry.dates) if part),
            _ENTRY_HEADER_CHARS_PER_LINE,
        )
        * _BODY_LINE_HEIGHT_PT,
    )
    for bullet in entry.bullets:
        height += _line_count(bullet.text, _BULLET_CHARS_PER_LINE) * _BODY_LINE_HEIGHT_PT
        height += _BULLET_GAP_PT
    return height + _ENTRY_SPACING_PT


def _estimate_section_height(section: ResumeSection) -> float:
    height = _SECTION_TITLE_HEIGHT_PT
    if section.kind == "summary":
        height += _line_count(section.body, _SUMMARY_CHARS_PER_LINE) * _BODY_LINE_HEIGHT_PT
    elif section.kind == "skills":
        height += _line_count(", ".join(section.lines), _SKILLS_CHARS_PER_LINE) * _BODY_LINE_HEIGHT_PT
    elif section.kind == "education":
        for line in section.lines:
            height += _line_count(line, _EDUCATION_CHARS_PER_LINE) * _BODY_LINE_HEIGHT_PT
    else:
        for entry in section.entries:
            height += _estimate_entry_height(entry)
    return height + _SECTION_SPACING_PT


def estimate_payload_height(
    payload: ResumePayloadV2,
    layout_plan: LayoutPlan,
) -> tuple[float, tuple[SectionMeasurement, ...]]:
    """Estimate payload height for deterministic pre-render fit planning."""
    total_height = _NAME_BLOCK_HEIGHT_PT + _CONTACT_BLOCK_HEIGHT_PT
    measurements: list[SectionMeasurement] = []
    section_by_id = {section.id: section for section in payload.sections}
    for section_plan in sorted(layout_plan.sections, key=lambda section: section.order):
        section = section_by_id[section_plan.section_id]
        section_height = _estimate_section_height(section)
        measurements.append(
            SectionMeasurement(
                section_id=section.id,
                estimated_height_pt=section_height,
            )
        )
        total_height += section_height
    return total_height, tuple(measurements)


def _compaction_notes(limits: LayoutLimits) -> tuple[str, ...]:
    notes: list[str] = []
    if limits.max_projects < DEFAULT_LAYOUT_LIMITS.max_projects:
        notes.append("projects trimmed before role experience")
    if limits.max_supplemental_entries < DEFAULT_LAYOUT_LIMITS.max_supplemental_entries:
        notes.append("supplemental highlights reduced before role experience")
    if limits.max_skills < DEFAULT_LAYOUT_LIMITS.max_skills:
        notes.append("skill list compacted")
    if limits.max_role_bullets < DEFAULT_LAYOUT_LIMITS.max_role_bullets:
        notes.append("role bullets reduced by score order")
    if limits.max_roles < DEFAULT_LAYOUT_LIMITS.max_roles:
        notes.append("lower-priority roles trimmed last")
    return tuple(notes)


def _build_candidate(
    evidence: ResumeEvidencePackage,
    *,
    persona: str,
    target_keywords: set[str],
    found_keywords: set[str],
    missing_keywords: set[str],
    template_version: str,
    limits: LayoutLimits,
    attempted_labels: tuple[str, ...],
    fallback_enabled: bool,
) -> PlannedResumeArtifacts:
    fit_result = build_fit_result(
        evidence,
        persona=persona,
        target_keywords=target_keywords,
        found_keywords=found_keywords,
        missing_keywords=missing_keywords,
        max_roles=limits.max_roles,
        max_role_bullets=limits.max_role_bullets,
        max_projects=limits.max_projects,
        max_project_bullets=limits.max_project_bullets,
        max_supplemental_entries=limits.max_supplemental_entries,
        max_supplemental_bullets=limits.max_supplemental_bullets,
    )
    effective_input = build_effective_input(
        evidence,
        fit_result,
        template_version=template_version,
    )
    payload = build_resume_payload(
        evidence,
        fit_result,
        effective_input,
        max_skills=limits.max_skills,
    )
    layout_plan = build_layout_plan(payload, template_version=template_version, limits=limits)
    estimated_height_pt, section_measurements = estimate_payload_height(payload, layout_plan)
    estimated_page_count = estimated_height_pt / DEFAULT_PAGE_GEOMETRY.content_height_pt
    diagnostics = FitDiagnostics(
        selected_limits=limits,
        attempted_limit_labels=attempted_labels,
        estimated_total_height_pt=estimated_height_pt,
        estimated_page_count=estimated_page_count,
        planner_fit_passed=(
            estimated_height_pt
            <= (DEFAULT_PAGE_GEOMETRY.content_height_pt - _FIT_SAFETY_RESERVE_PT)
        ),
        fallback_enabled=fallback_enabled,
        section_measurements=section_measurements,
        compaction_notes=_compaction_notes(limits),
    )
    return PlannedResumeArtifacts(
        fit_result=fit_result,
        effective_input=effective_input,
        payload=payload,
        layout_plan=layout_plan,
        fit_diagnostics=diagnostics,
    )


def plan_resume_artifacts(
    evidence: ResumeEvidencePackage,
    *,
    persona: str,
    target_keywords: set[str],
    found_keywords: set[str],
    missing_keywords: set[str],
    template_version: str,
    fallback_enabled: bool,
) -> PlannedResumeArtifacts:
    """Build the first one-page-fit candidate, or the most compact overflow candidate."""
    attempted_labels: list[str] = []
    best_candidate: PlannedResumeArtifacts | None = None

    for limits in FIT_COMPACTION_PROFILES:
        attempted_labels.append(limits.label)
        candidate = _build_candidate(
            evidence,
            persona=persona,
            target_keywords=target_keywords,
            found_keywords=found_keywords,
            missing_keywords=missing_keywords,
            template_version=template_version,
            limits=limits,
            attempted_labels=tuple(attempted_labels),
            fallback_enabled=fallback_enabled,
        )
        if best_candidate is None or (
            candidate.fit_diagnostics.estimated_total_height_pt
            < best_candidate.fit_diagnostics.estimated_total_height_pt
        ):
            best_candidate = candidate
        if candidate.fit_diagnostics.planner_fit_passed:
            return candidate

    if best_candidate is None:
        raise RuntimeError("Failed to build any fit-planner candidate")
    return best_candidate
