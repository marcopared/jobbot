"""Tests for shared word-boundary keyword matching (EPIC 5 hardening)."""

import pytest

from core.matching import keyword_in_text, keywords_in_text, score_keywords_in_text


def test_java_not_in_javascript():
    """'java' must not match substring in 'javascript'."""
    assert not keyword_in_text("We use JavaScript and TypeScript.", "java")
    assert keyword_in_text("We use JavaScript and TypeScript.", "javascript")


def test_go_not_in_going_or_argo():
    """'go' must not match substring in 'going', 'argo', 'mango'."""
    assert not keyword_in_text("We are going to use Argo CD.", "go")
    assert not keyword_in_text("Experience with Argo and mango.", "go")
    assert keyword_in_text("We use Go and Python.", "go")


def test_sql_not_in_postgresql_or_nosql():
    """'sql' (if ever used) must not match inside 'postgresql' or 'nosql'."""
    # sql is not in TECH_KEYWORDS but test the matching behavior
    assert not keyword_in_text("We use PostgreSQL and NoSQL.", "sql")


def test_multi_word_google_cloud():
    """Multi-word phrase 'google cloud' matches with flexible whitespace."""
    assert keyword_in_text("We use Google Cloud Platform.", "google cloud")
    assert keyword_in_text("Deploy on Google  Cloud.", "google cloud")
    assert not keyword_in_text("We use Google CloudPlatform.", "google cloud")


def test_business_logic_phrase():
    """Multi-word phrase 'business logic' matches correctly."""
    assert keyword_in_text("Implement business logic and APIs.", "business logic")
    assert not keyword_in_text("Businesslogic layer.", "business logic")


def test_keywords_in_text_returns_matched_only():
    """keywords_in_text returns only keywords that match as whole words."""
    text = "Python, JavaScript, and PostgreSQL. We are going to production."
    keywords = {"python", "java", "javascript", "go", "postgresql"}
    found = keywords_in_text(text, keywords)
    # "going" does not match "go"; "javascript" does not match "java"
    assert found == {"python", "javascript", "postgresql"}
    assert "java" not in found
    assert "go" not in found


def test_score_keywords_in_text_weights():
    """score_keywords_in_text sums weights for matched keywords only."""
    text = "JavaScript and Python for web development."
    kw_weights = {"javascript": 2.0, "java": 1.0, "python": 1.0}
    score = score_keywords_in_text(text, kw_weights)
    # javascript + python; java not in text as whole word
    assert score == 3.0
    assert score != 4.0


def test_empty_text_returns_nothing():
    """Empty or whitespace-only text returns no matches."""
    assert not keyword_in_text("", "python")
    assert not keyword_in_text("   ", "python")
    assert keywords_in_text("", {"python", "go"}) == set()
    assert score_keywords_in_text("", {"python": 1.0}) == 0.0


def test_case_insensitive():
    """Matching is case-insensitive."""
    assert keyword_in_text("PYTHON and Go", "python")
    assert keyword_in_text("PYTHON and Go", "go")
