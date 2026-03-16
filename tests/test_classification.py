"""Tests for persona classification (EPIC 6).

Deterministic rules-based classifier. Covers backend/platform/hybrid edge cases.
"""

import json
from pathlib import Path

import pytest

from core.classification import RulesBasedClassifier
from core.classification.types import ClassificationInput, Persona


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "classification"


@pytest.fixture
def classifier():
    return RulesBasedClassifier()


def _load_labeled_examples():
    with open(FIXTURES_DIR / "labeled_examples.json") as f:
        return json.load(f)


def test_classifier_interface_exists(classifier):
    """Classifier implements abstract interface."""
    result = classifier.classify(
        ClassificationInput(normalized_title="backend engineer", description="Python APIs")
    )
    assert result.persona in (Persona.BACKEND, Persona.PLATFORM_INFRA, Persona.HYBRID)
    assert 0.0 <= result.confidence <= 1.0
    assert result.rationale
    assert isinstance(result.matched_signals, dict)


def test_backend_clear_signals(classifier):
    """Strong backend signals -> BACKEND."""
    inputs = ClassificationInput(
        normalized_title="senior backend engineer",
        description="Build REST APIs and microservices. Python, FastAPI, PostgreSQL. Business logic.",
    )
    result = classifier.classify(inputs)
    assert result.persona == Persona.BACKEND
    assert result.confidence >= 0.6


def test_platform_clear_signals(classifier):
    """Strong platform/infra signals -> PLATFORM_INFRA."""
    inputs = ClassificationInput(
        normalized_title="platform engineer",
        description="Kubernetes, Terraform, AWS. CI/CD, observability, Prometheus, Grafana.",
    )
    result = classifier.classify(inputs)
    assert result.persona == Persona.PLATFORM_INFRA
    assert result.confidence >= 0.6


def test_hybrid_fullstack(classifier):
    """Full stack title -> HYBRID."""
    inputs = ClassificationInput(
        normalized_title="full stack engineer",
        description="React and Python. Docker.",
    )
    result = classifier.classify(inputs)
    assert result.persona == Persona.HYBRID


def test_ambiguous_mixed_fallback_hybrid(classifier):
    """Mixed/ambiguous signals -> HYBRID fallback."""
    inputs = ClassificationInput(
        normalized_title="software engineer",
        description="General role. Python, Docker, PostgreSQL, AWS.",  # Both backend and platform
    )
    result = classifier.classify(inputs)
    assert result.persona == Persona.HYBRID


def test_backend_api_engineer(classifier):
    """API engineer title -> BACKEND."""
    inputs = ClassificationInput(
        normalized_title="api engineer",
        description="REST, GraphQL, PostgreSQL, Go.",
    )
    result = classifier.classify(inputs)
    assert result.persona == Persona.BACKEND


def test_platform_sre(classifier):
    """SRE title + infra keywords -> PLATFORM_INFRA."""
    inputs = ClassificationInput(
        normalized_title="sre",
        description="Terraform, Ansible, Datadog. On-call.",
    )
    result = classifier.classify(inputs)
    assert result.persona == Persona.PLATFORM_INFRA


def test_deterministic_same_input_same_output(classifier):
    """Same input produces same output (deterministic)."""
    inputs = ClassificationInput(
        normalized_title="backend engineer",
        description="Python, FastAPI, PostgreSQL.",
    )
    r1 = classifier.classify(inputs)
    r2 = classifier.classify(inputs)
    assert r1.persona == r2.persona
    assert r1.confidence == r2.confidence
    assert r1.rationale == r2.rationale


def test_output_has_confidence_and_rationale(classifier):
    """Output contains confidence and rationale."""
    result = classifier.classify(
        ClassificationInput(normalized_title="platform engineer", description="K8s, Terraform.")
    )
    assert hasattr(result, "confidence")
    assert hasattr(result, "rationale")
    assert "Persona=" in result.rationale or result.persona.value in result.rationale


def test_matched_signals_inspectable(classifier):
    """matched_signals helps debug classification."""
    result = classifier.classify(
        ClassificationInput(
            normalized_title="backend engineer",
            description="Python, PostgreSQL, Redis.",
        )
    )
    assert "backend_total" in result.matched_signals
    assert "platform_total" in result.matched_signals


def test_labeled_examples_match(classifier):
    """Evaluation fixtures: classifier matches expected labels."""
    examples = _load_labeled_examples()
    for ex in examples:
        inputs = ClassificationInput(
            normalized_title=ex["normalized_title"],
            description=ex["description"],
        )
        result = classifier.classify(inputs)
        assert result.persona.value == ex["expected_persona"], (
            f"Example {ex['id']}: expected {ex['expected_persona']}, got {result.persona.value}"
        )
