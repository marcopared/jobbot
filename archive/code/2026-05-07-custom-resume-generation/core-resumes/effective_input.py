"""Deterministic effective-input model for resume generation."""

from __future__ import annotations

from dataclasses import dataclass

from core.resumes._serialization import canonical_json_hash


@dataclass(frozen=True)
class ResumeEffectiveInput:
    """Stable fingerprint inputs for deterministic resume generation."""

    evidence_hash: str
    fit_hash: str
    target_persona: str
    target_keywords: tuple[str, ...]
    selected_evidence_ids: tuple[str, ...]
    template_version: str
    layout_strategy: str = "grounded-v2-default"
    schema_version: str = "resume-effective-input-v2"

    def __post_init__(self) -> None:
        if not self.evidence_hash.strip():
            raise ValueError("ResumeEffectiveInput.evidence_hash is required")
        if not self.fit_hash.strip():
            raise ValueError("ResumeEffectiveInput.fit_hash is required")
        if not self.target_persona.strip():
            raise ValueError("ResumeEffectiveInput.target_persona is required")
        if not self.template_version.strip():
            raise ValueError("ResumeEffectiveInput.template_version is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "evidence_hash": self.evidence_hash,
            "fit_hash": self.fit_hash,
            "target_persona": self.target_persona,
            "target_keywords": list(self.target_keywords),
            "selected_evidence_ids": list(self.selected_evidence_ids),
            "template_version": self.template_version,
            "layout_strategy": self.layout_strategy,
        }

    def compute_hash(self) -> str:
        return canonical_json_hash(self.to_dict())
