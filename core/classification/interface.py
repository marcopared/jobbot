"""Persona classifier interface (EPIC 6).

Abstract interface. v1 uses rules-based provider; future can add LLM-backed provider
without changing callers.
"""

from abc import ABC, abstractmethod

from core.classification.types import ClassificationInput, ClassificationResult


class PersonaClassifier(ABC):
    """Abstract classifier. Implementations: RulesBasedClassifier, future LLMClassifier."""

    @abstractmethod
    def classify(self, inputs: ClassificationInput) -> ClassificationResult:
        """Classify job into BACKEND, PLATFORM_INFRA, or HYBRID."""
        ...
