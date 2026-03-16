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
