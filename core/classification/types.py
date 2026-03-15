"""Persona classification types (EPIC 6)."""

from enum import Enum
from typing import NamedTuple


class Persona(str, Enum):
    """Canonical persona labels for job classification."""

    BACKEND = "BACKEND"
    PLATFORM_INFRA = "PLATFORM_INFRA"
    HYBRID = "HYBRID"


class ClassificationInput(NamedTuple):
    """Inputs for persona classification. All optional; classifier uses what's available."""

    normalized_title: str = ""
    description: str = ""
    found_keywords: list[str] | None = None
    ats_categories: dict[str, list[str]] | None = None
    score_breakdown: dict | None = None


class ClassificationResult(NamedTuple):
    """Output of persona classification."""

    persona: Persona
    confidence: float  # 0.0–1.0
    rationale: str
    matched_signals: dict  # For debug: signals that drove the decision
