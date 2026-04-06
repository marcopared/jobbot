"""Typed fit and layout models for resume-generation v2."""

from __future__ import annotations

from dataclasses import dataclass

from core.resumes._serialization import canonical_json_hash


FIT_OUTCOME_SUCCESS_ONE_PAGE = "fit_success_one_page"
FIT_OUTCOME_FAILED_OVERFLOW = "fit_failed_overflow"
FIT_OUTCOME_SUCCESS_MULTI_PAGE_FALLBACK = "fit_success_multi_page_fallback"


@dataclass(frozen=True)
class PageGeometry:
    """Shared page geometry for HTML and PDF rendering."""

    page_size: str = "Letter"
    width_in: float = 8.5
    height_in: float = 11.0
    margin_top_in: float = 0.5
    margin_right_in: float = 0.5
    margin_bottom_in: float = 0.5
    margin_left_in: float = 0.5

    @property
    def content_width_pt(self) -> float:
        return (self.width_in - self.margin_left_in - self.margin_right_in) * 72.0

    @property
    def content_height_pt(self) -> float:
        return (self.height_in - self.margin_top_in - self.margin_bottom_in) * 72.0

    @property
    def css_page_size(self) -> str:
        return self.page_size.lower()

    def playwright_margin(self) -> dict[str, str]:
        return {
            "top": f"{self.margin_top_in}in",
            "right": f"{self.margin_right_in}in",
            "bottom": f"{self.margin_bottom_in}in",
            "left": f"{self.margin_left_in}in",
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "page_size": self.page_size,
            "width_in": self.width_in,
            "height_in": self.height_in,
            "margin_top_in": self.margin_top_in,
            "margin_right_in": self.margin_right_in,
            "margin_bottom_in": self.margin_bottom_in,
            "margin_left_in": self.margin_left_in,
        }


DEFAULT_PAGE_GEOMETRY = PageGeometry()


@dataclass(frozen=True)
class LayoutLimits:
    """Deterministic section limits used by the fit planner."""

    label: str
    max_roles: int
    max_role_bullets: int
    max_projects: int
    max_project_bullets: int
    max_supplemental_entries: int
    max_supplemental_bullets: int
    max_skills: int

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("LayoutLimits.label is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "max_roles": self.max_roles,
            "max_role_bullets": self.max_role_bullets,
            "max_projects": self.max_projects,
            "max_project_bullets": self.max_project_bullets,
            "max_supplemental_entries": self.max_supplemental_entries,
            "max_supplemental_bullets": self.max_supplemental_bullets,
            "max_skills": self.max_skills,
        }


DEFAULT_LAYOUT_LIMITS = LayoutLimits(
    label="base",
    max_roles=4,
    max_role_bullets=5,
    max_projects=2,
    max_project_bullets=3,
    max_supplemental_entries=2,
    max_supplemental_bullets=3,
    max_skills=20,
)


@dataclass(frozen=True)
class FitSelection:
    """Selected entry plus ordered bullet evidence ids for payload generation."""

    entry_id: str
    bullet_ids: tuple[str, ...]
    score: float

    def __post_init__(self) -> None:
        if not self.entry_id.strip():
            raise ValueError("FitSelection.entry_id is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "entry_id": self.entry_id,
            "bullet_ids": list(self.bullet_ids),
            "score": self.score,
        }


@dataclass(frozen=True)
class FitResult:
    """Deterministic content-fit result used to build the payload."""

    target_persona: str
    target_keywords: tuple[str, ...]
    found_keywords: tuple[str, ...]
    missing_keywords: tuple[str, ...]
    role_selections: tuple[FitSelection, ...]
    project_selections: tuple[FitSelection, ...]
    supplemental_selections: tuple[FitSelection, ...] = ()
    schema_version: str = "resume-fit-v2"

    def __post_init__(self) -> None:
        if not self.target_persona.strip():
            raise ValueError("FitResult.target_persona is required")

    @property
    def selected_evidence_ids(self) -> tuple[str, ...]:
        selected_ids: list[str] = []
        for selection in (
            *self.role_selections,
            *self.project_selections,
            *self.supplemental_selections,
        ):
            selected_ids.append(selection.entry_id)
            selected_ids.extend(selection.bullet_ids)
        return tuple(selected_ids)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "target_persona": self.target_persona,
            "target_keywords": list(self.target_keywords),
            "found_keywords": list(self.found_keywords),
            "missing_keywords": list(self.missing_keywords),
            "role_selections": [selection.to_dict() for selection in self.role_selections],
            "project_selections": [selection.to_dict() for selection in self.project_selections],
            "supplemental_selections": [
                selection.to_dict() for selection in self.supplemental_selections
            ],
        }

    def compute_hash(self) -> str:
        return canonical_json_hash(self.to_dict())


@dataclass(frozen=True)
class LayoutSectionPlan:
    """Per-section layout limits and render order."""

    section_id: str
    order: int
    title: str
    max_entries: int | None = None
    max_bullets_per_entry: int | None = None

    def __post_init__(self) -> None:
        if not self.section_id.strip():
            raise ValueError("LayoutSectionPlan.section_id is required")
        if not self.title.strip():
            raise ValueError("LayoutSectionPlan.title is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "order": self.order,
            "title": self.title,
            "max_entries": self.max_entries,
            "max_bullets_per_entry": self.max_bullets_per_entry,
        }


@dataclass(frozen=True)
class LayoutPlan:
    """Render-time layout plan for the structured payload."""

    sections: tuple[LayoutSectionPlan, ...]
    effective_input_hash: str
    template_version: str
    schema_version: str = "resume-layout-v2"

    def __post_init__(self) -> None:
        if not self.effective_input_hash.strip():
            raise ValueError("LayoutPlan.effective_input_hash is required")
        if not self.template_version.strip():
            raise ValueError("LayoutPlan.template_version is required")
        section_ids = {section.section_id for section in self.sections}
        if len(section_ids) != len(self.sections):
            raise ValueError("LayoutPlan section ids must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "effective_input_hash": self.effective_input_hash,
            "template_version": self.template_version,
            "sections": [section.to_dict() for section in self.sections],
        }

    def compute_hash(self) -> str:
        return canonical_json_hash(self.to_dict())


@dataclass(frozen=True)
class SectionMeasurement:
    """Estimated section footprint for deterministic fit planning."""

    section_id: str
    estimated_height_pt: float

    def __post_init__(self) -> None:
        if not self.section_id.strip():
            raise ValueError("SectionMeasurement.section_id is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "estimated_height_pt": self.estimated_height_pt,
        }


@dataclass(frozen=True)
class FitDiagnostics:
    """Planner and render diagnostics carried with resume artifacts/results."""

    selected_limits: LayoutLimits
    attempted_limit_labels: tuple[str, ...]
    estimated_total_height_pt: float
    estimated_page_count: float
    planner_fit_passed: bool
    fallback_enabled: bool
    actual_page_count: int | None = None
    section_measurements: tuple[SectionMeasurement, ...] = ()
    compaction_notes: tuple[str, ...] = ()
    page_geometry: PageGeometry = DEFAULT_PAGE_GEOMETRY
    schema_version: str = "resume-fit-diagnostics-v2"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "selected_limits": self.selected_limits.to_dict(),
            "attempted_limit_labels": list(self.attempted_limit_labels),
            "estimated_total_height_pt": self.estimated_total_height_pt,
            "estimated_page_count": self.estimated_page_count,
            "planner_fit_passed": self.planner_fit_passed,
            "fallback_enabled": self.fallback_enabled,
            "actual_page_count": self.actual_page_count,
            "page_geometry": self.page_geometry.to_dict(),
            "section_measurements": [
                measurement.to_dict() for measurement in self.section_measurements
            ],
            "compaction_notes": list(self.compaction_notes),
        }
