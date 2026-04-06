"""Typed payload models for resume-generation v2."""

from __future__ import annotations

from dataclasses import dataclass

from core.resumes._serialization import canonical_json_hash
from core.resumes.evidence_types import ResumeContact


@dataclass(frozen=True)
class BulletProvenance:
    """Pointer from a payload bullet back to a source evidence item."""

    evidence_id: str
    source_type: str

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("BulletProvenance.evidence_id is required")
        if not self.source_type.strip():
            raise ValueError("BulletProvenance.source_type is required")

    def to_dict(self) -> dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "source_type": self.source_type,
        }


@dataclass(frozen=True)
class ResumeBullet:
    """A rendered bullet plus its evidence provenance."""

    id: str
    text: str
    provenance: tuple[BulletProvenance, ...]

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ResumeBullet.id is required")
        if not self.text.strip():
            raise ValueError("ResumeBullet.text is required")
        if not self.provenance:
            raise ValueError("ResumeBullet.provenance must contain at least one evidence record")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "text": self.text,
            "provenance": [provenance.to_dict() for provenance in self.provenance],
        }


@dataclass(frozen=True)
class ResumeSectionEntry:
    """A structured entry inside a section such as an experience role or project."""

    id: str
    heading: str
    subheading: str = ""
    dates: str = ""
    bullets: tuple[ResumeBullet, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ResumeSectionEntry.id is required")
        if not self.heading.strip():
            raise ValueError("ResumeSectionEntry.heading is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "heading": self.heading,
            "subheading": self.subheading,
            "dates": self.dates,
            "bullets": [bullet.to_dict() for bullet in self.bullets],
        }


@dataclass(frozen=True)
class ResumeSection:
    """A section in the structured payload."""

    id: str
    kind: str
    title: str
    body: str = ""
    lines: tuple[str, ...] = ()
    entries: tuple[ResumeSectionEntry, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ResumeSection.id is required")
        if not self.kind.strip():
            raise ValueError("ResumeSection.kind is required")
        if not self.title.strip():
            raise ValueError("ResumeSection.title is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "body": self.body,
            "lines": list(self.lines),
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class ResumePayloadV2:
    """Structured payload consumed by layout planning and rendering."""

    contact: ResumeContact
    sections: tuple[ResumeSection, ...]
    target_persona: str
    effective_input_hash: str
    inventory_version_hash: str | None = None
    schema_version: str = "resume-payload-v2"

    def __post_init__(self) -> None:
        if not self.target_persona.strip():
            raise ValueError("ResumePayloadV2.target_persona is required")
        if not self.effective_input_hash.strip():
            raise ValueError("ResumePayloadV2.effective_input_hash is required")
        section_ids = {section.id for section in self.sections}
        if len(section_ids) != len(self.sections):
            raise ValueError("ResumePayloadV2 section ids must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "target_persona": self.target_persona,
            "effective_input_hash": self.effective_input_hash,
            "inventory_version_hash": self.inventory_version_hash,
            "contact": self.contact.to_dict(),
            "sections": [section.to_dict() for section in self.sections],
        }

    def compute_hash(self) -> str:
        return canonical_json_hash(self.to_dict())
