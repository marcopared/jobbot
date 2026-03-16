"""Tests for deterministic ATS keyword extraction (EPIC 5)."""

import json
from pathlib import Path

import pytest

from core.ats.extraction import extract_ats_signals


def test_extract_found_and_missing_keywords():
    """Extraction returns found (user has) and missing (user doesn't)."""
    jd = "We use Python, Go, Kubernetes, and Rust."
    user_skills = {"python", "kubernetes"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "python" in result.found_keywords
    assert "kubernetes" in result.found_keywords
    assert "go" in result.missing_keywords
    assert "rust" in result.missing_keywords


def test_synonym_mapping_postgres_to_postgresql():
    """Synonym 'postgres' in JD maps to canonical 'postgresql'."""
    jd = "Our stack includes Postgres and Redis."
    user_skills = {"postgresql", "redis"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "postgresql" in result.found_keywords
    assert "redis" in result.found_keywords
    assert "postgres" not in result.found_keywords  # Canonical form stored


def test_synonym_k8s_to_kubernetes():
    """Synonym 'k8s' in JD maps to canonical 'kubernetes'."""
    jd = "Experience with k8s and Docker."
    user_skills = {"kubernetes", "docker"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "kubernetes" in result.found_keywords
    assert "docker" in result.found_keywords


def test_ats_compatibility_score_percent():
    """ATS score is percent of JD keywords user has (0-100)."""
    jd = "Python, Go, AWS."
    user_skills = {"python", "aws"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    # 2/3 = 66.7%
    assert 66 <= result.ats_compatibility_score <= 67


def test_ats_categories_grouped():
    """ats_categories groups JD keywords by category."""
    jd = "Python, FastAPI, PostgreSQL, AWS, Docker."
    result = extract_ats_signals(jd, user_skills=set())
    assert "languages" in result.ats_categories
    assert "python" in result.ats_categories["languages"]
    assert "frameworks" in result.ats_categories
    assert "fastapi" in result.ats_categories["frameworks"]
    assert "databases" in result.ats_categories
    assert "postgresql" in result.ats_categories["databases"]


def test_empty_jd_zero_keywords():
    """Empty or no description yields empty extraction."""
    result = extract_ats_signals("", user_skills={"python"})
    assert result.found_keywords == []
    assert result.missing_keywords == []
    assert result.ats_compatibility_score == 0.0


def test_all_matched_100_score():
    """When user has all JD keywords, score is 100."""
    jd = "Python, AWS, Docker."
    user_skills = {"python", "aws", "docker"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert result.ats_compatibility_score == 100.0
    assert len(result.missing_keywords) == 0


def test_master_skills_path(tmp_path):
    """User skills can be loaded from master_skills.json path."""
    skills_file = tmp_path / "master_skills.json"
    skills_file.write_text(json.dumps(["python", "fastapi"]))
    jd = "We need Python and FastAPI expertise."
    result = extract_ats_signals(jd, user_skills_path=str(skills_file))
    assert "python" in result.found_keywords
    assert "fastapi" in result.found_keywords


def test_output_stable_and_sorted():
    """Found and missing keywords are sorted for stable output."""
    jd = "Rust, Python, Go, Java."
    user_skills = {"python"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert result.found_keywords == sorted(result.found_keywords)
    assert result.missing_keywords == sorted(result.missing_keywords)


def test_no_llm_purely_deterministic():
    """Same input always produces same output (no randomness)."""
    jd = "Python, AWS, Kubernetes."
    user_skills = {"python", "aws"}
    r1 = extract_ats_signals(jd, user_skills=user_skills)
    r2 = extract_ats_signals(jd, user_skills=user_skills)
    assert r1.found_keywords == r2.found_keywords
    assert r1.missing_keywords == r2.missing_keywords
    assert r1.ats_compatibility_score == r2.ats_compatibility_score


def test_word_boundary_java_not_in_javascript():
    """Word-boundary: 'java' must not match substring in 'javascript'."""
    jd = "We use JavaScript and TypeScript for frontend."
    user_skills = {"java"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "java" not in result.found_keywords
    assert "java" not in result.missing_keywords


def test_go_not_matched_in_mango_or_argo():
    """Word-boundary: 'go' must not match in 'mango', 'argo', 'golang' without word boundary."""
    jd = "Experience with mangoDB, ArgoCD, and golang."
    user_skills = {"go"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    # "go" as standalone word not in JD; golang contains "go" but \bgo\b won't match "golang"
    assert "go" not in result.found_keywords


def test_java_not_matched_in_javascript():
    """Word-boundary: 'java' does not match inside 'javascript'."""
    jd = "We use JavaScript and TypeScript for frontend."
    result = extract_ats_signals(jd, user_skills=set())
    assert "java" not in result.found_keywords
    assert "java" not in result.missing_keywords
    assert "javascript" in result.found_keywords or "javascript" in result.missing_keywords


def test_go_not_matched_in_mango_or_argo():
    """Word-boundary: 'go' does not match inside 'mango' or 'argo'."""
    jd = "Experience with Argo CD and mango database."
    result = extract_ats_signals(jd, user_skills=set())
    assert "go" not in result.found_keywords
    assert "go" not in result.missing_keywords


def test_go_matched_as_standalone():
    """Word-boundary: 'go' matches when used as a word."""
    jd = "We use Go and Python for backend services."
    result = extract_ats_signals(jd, user_skills={"go"})
    assert "go" in result.found_keywords


def test_java_not_matched_in_javascript():
    """Word-boundary: 'java' does not match inside 'javascript' (false positive avoidance)."""
    jd = "We use JavaScript and TypeScript."
    user_skills = {"java", "javascript"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "javascript" in result.found_keywords
    assert "java" not in result.found_keywords
    assert "java" not in result.missing_keywords  # not in JD at all


def test_go_not_matched_in_argo_or_mango():
    """Word-boundary: 'go' does not match inside 'argo' or 'mango'."""
    jd = "Experience with Argo CD and MangoDB optional."
    user_skills = {"go"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "go" not in result.found_keywords
    assert "go" not in result.missing_keywords  # not as whole word in JD


def test_go_matched_as_whole_word():
    """Word-boundary: 'go' is matched when it appears as a whole word."""
    jd = "We use Go, Python, and Kubernetes."
    user_skills = {"go", "python"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "go" in result.found_keywords
    assert "python" in result.found_keywords


def test_java_not_matched_in_javascript():
    """'java' must not match as substring inside 'javascript' (word boundaries)."""
    jd = "We use JavaScript and TypeScript for frontend."
    result = extract_ats_signals(jd, user_skills=set())
    assert "java" not in result.found_keywords
    assert "java" not in result.missing_keywords
    assert "javascript" in result.found_keywords or "javascript" in result.missing_keywords


def test_go_not_matched_in_mango_or_argo():
    """'go' must not match as substring in 'mango' or 'argo' (word boundaries)."""
    jd = "Experience with mango exports and argo workflows."
    result = extract_ats_signals(jd, user_skills=set())
    assert "go" not in result.found_keywords
    assert "go" not in result.missing_keywords


def test_java_not_matched_in_javascript():
    """Word-boundary: 'java' does not match inside 'javascript'."""
    jd = "We need JavaScript and TypeScript expertise."
    result = extract_ats_signals(jd, user_skills=set())
    assert "java" not in result.found_keywords
    assert "java" not in result.missing_keywords
    assert "javascript" in result.found_keywords or "javascript" in result.missing_keywords


def test_go_not_matched_in_argo_or_mango():
    """Word-boundary: 'go' does not match inside 'argo' or 'mango'."""
    jd = "Experience with Argo CD and MangoDB."
    result = extract_ats_signals(jd, user_skills=set())
    assert "go" not in result.found_keywords
    assert "go" not in result.missing_keywords


def test_go_matched_as_standalone():
    """Word-boundary: 'go' is matched when standalone."""
    jd = "We use Go and Python."
    result = extract_ats_signals(jd, user_skills=set())
    assert "go" in result.found_keywords or "go" in result.missing_keywords


def test_java_not_matched_in_javascript():
    """'java' does not match as substring in 'javascript' (word-boundary)."""
    jd = "We need JavaScript and TypeScript expertise."
    user_skills = {"java"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "java" not in result.found_keywords
    assert "java" not in result.missing_keywords


def test_go_not_matched_in_argo_or_mango():
    """'go' does not match as substring in 'argo' or 'mango' (word-boundary)."""
    jd = "Experience with Argo CD and MangoDB is a plus."
    user_skills = {"go"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "go" not in result.found_keywords
    assert "go" not in result.missing_keywords


def test_go_matched_as_whole_word():
    """'go' matches when used as whole word."""
    jd = "We use Go and Python for backend services."
    user_skills = {"go", "python"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "go" in result.found_keywords


def test_java_not_matched_in_javascript():
    """'java' should not match as substring inside 'javascript' (word-boundary)."""
    jd = "We build with JavaScript, TypeScript, and modern frontend tooling."
    result = extract_ats_signals(jd, user_skills=set())
    assert "java" not in result.found_keywords
    assert "java" not in result.missing_keywords
    assert "javascript" in result.found_keywords or "javascript" in result.missing_keywords


def test_go_not_matched_in_mango_argo():
    """'go' should not match as substring in 'mango', 'argo', 'ago'."""
    jd = "Experience with mango databases, Argo CD workflows, and agile processes."
    result = extract_ats_signals(jd, user_skills=set())
    assert "go" not in result.found_keywords
    assert "go" not in result.missing_keywords


def test_go_matched_as_standalone():
    """'go' as standalone word (Go language) should match."""
    jd = "We use Go for backend services and Kubernetes for orchestration."
    result = extract_ats_signals(jd, user_skills=set())
    assert "go" in result.found_keywords or "go" in result.missing_keywords


def test_java_not_matched_in_javascript():
    """'java' as substring in 'javascript' should NOT match (word-boundary)."""
    jd = "We use JavaScript and TypeScript for frontend."
    user_skills = {"java", "javascript"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "javascript" in result.found_keywords
    assert "java" not in result.found_keywords
    assert "java" not in result.missing_keywords


def test_go_not_matched_in_mango_or_argo():
    """'go' as substring in 'mango' or 'argo' should NOT match (word-boundary)."""
    jd = "We process data with Argo workflows and Mango DB."
    user_skills = {"go"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "go" not in result.found_keywords
    assert "go" not in result.missing_keywords


def test_go_matched_as_standalone():
    """'go' as standalone word should match."""
    jd = "Backend in Go, distributed systems."
    user_skills = {"go"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "go" in result.found_keywords


def test_java_not_extracted_from_javascript():
    """Word-boundary: 'java' is not incorrectly extracted from 'javascript'."""
    jd = "We need strong JavaScript and TypeScript skills."
    result = extract_ats_signals(jd, user_skills=set())
    assert "java" not in result.found_keywords
    assert "java" not in result.missing_keywords  # java not incorrectly extracted
    assert "javascript" in result.missing_keywords  # JD has javascript
    assert "typescript" in result.missing_keywords  # JD has typescript


def test_go_not_matched_in_argo_or_mango():
    """Word-boundary: 'go' does not match inside 'argo', 'mango', 'golang'."""
    jd = "We use Argo CD, MongoDB, and Golang."
    result = extract_ats_signals(jd, user_skills=set())
    assert "go" not in result.found_keywords
    assert "go" not in result.missing_keywords


def test_go_matched_as_standalone():
    """Word-boundary: 'go' matches when used as a standalone word."""
    jd = "We use Go, Python, and Rust."
    result = extract_ats_signals(jd, user_skills=set())
    assert "go" in result.found_keywords or "go" in result.missing_keywords


def test_java_not_in_javascript():
    """'java' does not match substring in 'javascript' (word-boundary)."""
    jd = "We use JavaScript and TypeScript for the frontend."
    result = extract_ats_signals(jd, user_skills=set())
    assert "java" not in result.found_keywords
    assert "java" not in result.missing_keywords


def test_go_not_in_argo_or_mango():
    """'go' does not match substring in 'argo' or 'mango' (word-boundary)."""
    jd = "Experience with Argo CD and mango databases."
    result = extract_ats_signals(jd, user_skills=set())
    assert "go" not in result.found_keywords
    assert "go" not in result.missing_keywords


def test_go_matches_standalone():
    """'go' matches when used as standalone word."""
    jd = "We need Go (golang) experience."
    result = extract_ats_signals(jd, user_skills=set())
    assert "go" in result.found_keywords or "go" in result.missing_keywords


def test_word_boundary_java_not_in_javascript():
    """'java' must not match inside 'javascript' (word-boundary prevents false positive)."""
    jd = "We need JavaScript and TypeScript expertise."
    user_skills = {"java", "javascript"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "javascript" in result.found_keywords
    assert "java" not in result.found_keywords
    assert "java" not in result.missing_keywords


def test_word_boundary_go_not_in_argo_or_mango():
    """'go' must not match inside 'argo', 'mango', 'golang' etc."""
    jd = "Experience with Argo CD, MangoDB, and Golang."
    user_skills = {"go"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "go" not in result.found_keywords
    assert "go" not in result.missing_keywords


def test_word_boundary_go_matches_standalone():
    """'go' must match when it appears as a standalone word."""
    jd = "We use Go and Python for our backend."
    user_skills = {"go", "python"}
    result = extract_ats_signals(jd, user_skills=user_skills)
    assert "go" in result.found_keywords
    assert "python" in result.found_keywords
