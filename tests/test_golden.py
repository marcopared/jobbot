"""Golden evaluation tests for scoring, ATS extraction, classification, resume selection (EPIC 10).

Regression tests: changes to core logic must not break expected outputs.
"""

import json
from pathlib import Path

import pytest

from core.ats.extraction import extract_ats_signals
from core.classification import RulesBasedClassifier
from core.classification.types import ClassificationInput
from core.scoring.scorer import score_job

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"


class _MockJob:
    """Minimal job-like object for scoring."""

    def __init__(self, **kwargs):
        self.normalized_title = kwargs.get("normalized_title", "")
        self.title = kwargs.get("title", "")
        self.raw_title = kwargs.get("raw_title", "")
        self.description = kwargs.get("description", "")
        self.normalized_location = kwargs.get("normalized_location") or kwargs.get("location")
        self.location = kwargs.get("location", "")
        self.remote_flag = kwargs.get("remote_flag", False)


def _load_golden(name: str) -> list[dict]:
    path = GOLDEN_DIR / f"{name}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def test_golden_scoring(tmp_path):
    """Golden scoring: expected totals and factor scores must match."""
    samples = _load_golden("scoring_golden")
    if not samples:
        pytest.skip("No scoring_golden.json")
    skills_file = tmp_path / "master_skills.json"
    skills_file.write_text(json.dumps(["python", "fastapi", "aws", "postgresql", "go", "redis"]))
    for ex in samples:
        job = _MockJob(
            normalized_title=ex.get("normalized_title", ex.get("title", "")).lower(),
            title=ex.get("title", ""),
            raw_title=ex.get("raw_title", ex.get("title", "")),
            description=ex.get("description", ""),
            normalized_location=(ex.get("normalized_location") or ex.get("location") or "").lower(),
            location=ex.get("location", ""),
            remote_flag=ex.get("remote_flag", False),
        )
        total, breakdown = score_job(job, master_skills_path=str(skills_file))
        if "expected_min_total" in ex:
            assert total >= ex["expected_min_total"], (
                f"{ex['id']}: expected min {ex['expected_min_total']}, got {total}"
            )
        if "expected_max_total" in ex:
            assert total <= ex["expected_max_total"], (
                f"{ex['id']}: expected max {ex['expected_max_total']}, got {total}"
            )
        if "expected_passes_threshold" in ex:
            passes = total >= 60.0
            assert passes == ex["expected_passes_threshold"], (
                f"{ex['id']}: expected passes_threshold={ex['expected_passes_threshold']}, "
                f"got passes={passes} (total={total})"
            )
        if "expected_seniority_fit" in ex:
            assert breakdown.get("seniority_fit") == ex["expected_seniority_fit"], (
                f"{ex['id']}: expected seniority_fit {ex['expected_seniority_fit']}, "
                f"got {breakdown.get('seniority_fit')}"
            )
        if "expected_location_remote" in ex:
            assert breakdown.get("location_remote") == ex["expected_location_remote"], (
                f"{ex['id']}: expected location_remote {ex['expected_location_remote']}, "
                f"got {breakdown.get('location_remote')}"
            )


def test_golden_ats_extraction():
    """Golden ATS extraction: found/missing keywords and score must match."""
    samples = _load_golden("ats_golden")
    if not samples:
        pytest.skip("No ats_golden.json")
    for ex in samples:
        desc = ex.get("description", "")
        skills = set((ex.get("user_skills") or []))
        result = extract_ats_signals(desc, user_skills=skills)
        if "expected_found_subset" in ex:
            for kw in ex["expected_found_subset"]:
                assert kw in result.found_keywords, (
                    f"{ex['id']}: expected found {kw}, got {result.found_keywords}"
                )
        if "expected_missing_subset" in ex:
            for kw in ex["expected_missing_subset"]:
                assert kw in result.missing_keywords, (
                    f"{ex['id']}: expected missing {kw}, got {result.missing_keywords}"
                )
        if "expected_score_min" in ex:
            assert result.ats_compatibility_score >= ex["expected_score_min"], (
                f"{ex['id']}: expected score >= {ex['expected_score_min']}, got {result.ats_compatibility_score}"
            )
        if "expected_score_max" in ex:
            assert result.ats_compatibility_score <= ex["expected_score_max"], (
                f"{ex['id']}: expected score <= {ex['expected_score_max']}, got {result.ats_compatibility_score}"
            )
        if "expected_score" in ex:
            assert result.ats_compatibility_score == ex["expected_score"], (
                f"{ex['id']}: expected score {ex['expected_score']}, got {result.ats_compatibility_score}"
            )
        if "expected_found_count" in ex:
            assert len(result.found_keywords) == ex["expected_found_count"], (
                f"{ex['id']}: expected found_count {ex['expected_found_count']}, "
                f"got {len(result.found_keywords)}"
            )
        if "expected_missing_count" in ex:
            assert len(result.missing_keywords) == ex["expected_missing_count"], (
                f"{ex['id']}: expected missing_count {ex['expected_missing_count']}, "
                f"got {len(result.missing_keywords)}"
            )
        if ex.get("expected_synonym_postgres_mapped"):
            assert "postgresql" in result.found_keywords or "postgresql" in (
                k for cat in (result.ats_categories or {}).values() for k in cat
            ), f"{ex['id']}: expected postgres synonym mapped to postgresql"


def test_golden_classification():
    """Golden classification: persona must match labeled examples."""
    path = Path(__file__).parent / "fixtures" / "classification" / "labeled_examples.json"
    if not path.exists():
        pytest.skip("No labeled_examples.json")
    examples = json.loads(path.read_text())
    classifier = RulesBasedClassifier()
    for ex in examples:
        inputs = ClassificationInput(
            normalized_title=ex.get("normalized_title", ""),
            description=ex.get("description", ""),
        )
        result = classifier.classify(inputs)
        assert result.persona.value == ex["expected_persona"], (
            f"Example {ex['id']}: expected {ex['expected_persona']}, got {result.persona.value}"
        )
