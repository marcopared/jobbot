"""Typed fit and layout models for resume-generation v2."""

from __future__ import annotations

from dataclasses import dataclass

from core.resumes._serialization import canonical_json_hash


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
    schema_version: str = "resume-fit-v2"

    def __post_init__(self) -> None:
        if not self.target_persona.strip():
            raise ValueError("FitResult.target_persona is required")

    @property
    def selected_evidence_ids(self) -> tuple[str, ...]:
        selected_ids: list[str] = []
        for selection in (*self.role_selections, *self.project_selections):
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
