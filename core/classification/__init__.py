"""Persona classification (EPIC 6).

Clean interface with pluggable providers. v1 uses rules-based classifier.
Future: LLM-backed provider without refactor.
"""

from core.classification.interface import PersonaClassifier
from core.classification.rules_provider import RulesBasedClassifier
from core.classification.types import ClassificationInput, ClassificationResult, Persona

__all__ = [
    "ClassificationInput",
    "ClassificationResult",
    "Persona",
    "PersonaClassifier",
    "RulesBasedClassifier",
]
