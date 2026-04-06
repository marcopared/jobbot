"""Typed evidence models for resume-generation v2."""

from __future__ import annotations

from dataclasses import dataclass

from core.resumes._serialization import canonical_json_hash


@dataclass(frozen=True)
class ResumeContact:
    """Contact information carried into the payload/render stages."""

    name: str
    email: str
    location: str
    linkedin_url: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "email": self.email,
            "location": self.location,
            "linkedin_url": self.linkedin_url,
        }


@dataclass(frozen=True)
class ResumeEducationRecord:
    """Education line carried through the payload/render stages."""

    school: str
    degree: str
    year: str

    def to_dict(self) -> dict[str, str]:
        return {
            "school": self.school,
            "degree": self.degree,
            "year": self.year,
        }


@dataclass(frozen=True)
class ResumeEvidenceItem:
    """A single evidence record with a stable id for provenance."""

    id: str
    source_type: str
    item_type: str
    text: str
    tags: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    parent_id: str | None = None
    attributes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ResumeEvidenceItem.id is required")
        if not self.source_type.strip():
            raise ValueError("ResumeEvidenceItem.source_type is required")
        if not self.item_type.strip():
            raise ValueError("ResumeEvidenceItem.item_type is required")
        if not self.text.strip():
            raise ValueError("ResumeEvidenceItem.text is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "item_type": self.item_type,
            "text": self.text,
            "tags": list(self.tags),
            "metrics": list(self.metrics),
            "parent_id": self.parent_id,
            "attributes": {key: value for key, value in self.attributes},
        }


@dataclass(frozen=True)
class ResumeEvidenceRole:
    """Structured experience entry backed by evidence items."""

    id: str
    company: str
    title: str
    location: str = ""
    start: str = ""
    end: str = "present"
    tags: tuple[str, ...] = ()
    bullet_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ResumeEvidenceRole.id is required")
        if not self.company.strip():
            raise ValueError("ResumeEvidenceRole.company is required")
        if not self.title.strip():
            raise ValueError("ResumeEvidenceRole.title is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "start": self.start,
            "end": self.end,
            "tags": list(self.tags),
            "bullet_ids": list(self.bullet_ids),
        }


@dataclass(frozen=True)
class ResumeEvidenceProject:
    """Structured project entry backed by evidence items."""

    id: str
    name: str
    description: str = ""
    url: str | None = None
    bullet_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ResumeEvidenceProject.id is required")
        if not self.name.strip():
            raise ValueError("ResumeEvidenceProject.name is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "bullet_ids": list(self.bullet_ids),
        }


@dataclass(frozen=True)
class ResumeEvidencePackage:
    """Aggregated evidence set for deterministic payload generation."""

    contact: ResumeContact
    summary_variants: tuple[tuple[str, str], ...]
    skills: tuple[str, ...]
    education: tuple[ResumeEducationRecord, ...]
    roles: tuple[ResumeEvidenceRole, ...]
    projects: tuple[ResumeEvidenceProject, ...]
    items: tuple[ResumeEvidenceItem, ...]
    inventory_version_hash: str | None = None
    schema_version: str = "resume-evidence-package-v2"
    source_kind: str = "inventory-only"

    def __post_init__(self) -> None:
        item_ids = {item.id for item in self.items}
        if len(item_ids) != len(self.items):
            raise ValueError("ResumeEvidencePackage item ids must be unique")
        if not self.source_kind.strip():
            raise ValueError("ResumeEvidencePackage.source_kind is required")
        for role in self.roles:
            missing = [bullet_id for bullet_id in role.bullet_ids if bullet_id not in item_ids]
            if missing:
                raise ValueError(
                    f"ResumeEvidenceRole {role.id} references unknown evidence ids: {missing}"
                )
        for project in self.projects:
            missing = [bullet_id for bullet_id in project.bullet_ids if bullet_id not in item_ids]
            if missing:
                raise ValueError(
                    f"ResumeEvidenceProject {project.id} references unknown evidence ids: {missing}"
                )

    def summary_for_persona(self, persona: str) -> str:
        normalized = persona.strip().upper()
        summaries = dict(self.summary_variants)
        return summaries.get(normalized) or summaries.get("HYBRID") or ""

    def get_item(self, evidence_id: str) -> ResumeEvidenceItem:
        for item in self.items:
            if item.id == evidence_id:
                return item
        raise KeyError(f"Unknown evidence id: {evidence_id}")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source_kind": self.source_kind,
            "inventory_version_hash": self.inventory_version_hash,
            "contact": self.contact.to_dict(),
            "summary_variants": dict(self.summary_variants),
            "skills": list(self.skills),
            "education": [record.to_dict() for record in self.education],
            "roles": [role.to_dict() for role in self.roles],
            "projects": [project.to_dict() for project in self.projects],
            "items": [item.to_dict() for item in self.items],
        }

    def compute_hash(self) -> str:
        return canonical_json_hash(self.to_dict())
