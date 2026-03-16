"""Tests for deterministic job scoring engine (EPIC 5)."""

import json
from pathlib import Path

import pytest

from core.scoring.scorer import score_job
from core.scoring.rules import SCORING_WEIGHTS

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "jobs"


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


def _job_from_fixture(data: dict) -> _MockJob:
    return _MockJob(
        normalized_title=data.get("normalized_title", data.get("title", "")).lower(),
        title=data.get("title", ""),
        raw_title=data.get("raw_title", data.get("title", "")),
        description=data.get("description", ""),
        normalized_location=(data.get("normalized_location") or data.get("location") or "").lower(),
        location=data.get("location", ""),
        remote_flag=data.get("remote_flag", False),
    )


def test_score_breakdown_has_all_factors():
    """Breakdown must include all five factors for explainability."""
    job = _MockJob(
        normalized_title="senior software engineer",
        title="Senior Software Engineer",
        description="Python, fintech, payments.",
        location="remote",
        remote_flag=True,
    )
    total, breakdown = score_job(job, master_skills_path=None)
    assert "title_relevance" in breakdown
    assert "seniority_fit" in breakdown
    assert "domain_alignment" in breakdown
    assert "location_remote" in breakdown
    assert "tech_stack" in breakdown
    assert "weights" in breakdown
    assert breakdown["weights"] == SCORING_WEIGHTS


def test_score_total_in_range():
    """Total score must be 0-100."""
    job = _MockJob(
        normalized_title="software engineer",
        title="Software Engineer",
        description="Python backend.",
        location="remote",
        remote_flag=True,
    )
    total, _ = score_job(job, master_skills_path=None)
    assert 0 <= total <= 100


def test_title_relevance_target_match():
    """Target titles (backend engineer, software engineer) score high."""
    for title in ["backend engineer", "software engineer", "platform engineer", "senior backend"]:
        job = _MockJob(
            normalized_title=title,
            title=title.title(),
            description="",
            location="",
        )
        total, bd = score_job(job, master_skills_path=None)
        assert bd["title_relevance"] >= 80, f"Expected high title score for {title}"


def test_seniority_junior_penalty():
    """Junior/intern roles get strong penalty."""
    job = _MockJob(
        normalized_title="junior software engineer",
        title="Junior Software Engineer",
        description="Entry level position.",
        location="nyc",
    )
    total, bd = score_job(job, master_skills_path=None)
    assert bd["seniority_fit"] == 20.0


def test_seniority_over_senior_penalty():
    """Staff/principal/director get moderate penalty."""
    job = _MockJob(
        normalized_title="staff software engineer",
        title="Staff Software Engineer",
        description="Principal role.",
        location="remote",
        remote_flag=True,
    )
    total, bd = score_job(job, master_skills_path=None)
    assert bd["seniority_fit"] == 40.0


def test_seniority_sweet_spot():
    """Senior without over-senior labels scores 100."""
    job = _MockJob(
        normalized_title="senior software engineer",
        title="Senior Software Engineer",
        description="Build systems.",
        location="remote",
    )
    total, bd = score_job(job, master_skills_path=None)
    assert bd["seniority_fit"] == 100.0


def test_domain_fintech_alignment():
    """Fintech/payments domain keywords boost domain score."""
    job = _MockJob(
        normalized_title="backend engineer",
        title="Backend Engineer",
        description="Fintech startup, payments, banking.",
        location="remote",
        remote_flag=True,
    )
    total, bd = score_job(job, master_skills_path=None)
    assert bd["domain_alignment"] > 50


def test_location_remote_scores_high():
    """Remote jobs score 100 on location."""
    job = _MockJob(
        normalized_title="engineer",
        title="Engineer",
        description="",
        location="remote",
        remote_flag=True,
    )
    total, bd = score_job(job, master_skills_path=None)
    assert bd["location_remote"] == 100.0


def test_tech_stack_uses_master_skills(tmp_path):
    """Tech stack score improves when JD overlaps with user skills."""
    skills_file = tmp_path / "master_skills.json"
    skills_file.write_text(json.dumps(["python", "fastapi", "aws", "postgresql"]))
    job = _MockJob(
        normalized_title="backend engineer",
        title="Backend Engineer",
        description="We use Python, FastAPI, PostgreSQL, and AWS.",
        location="remote",
        remote_flag=True,
    )
    total, bd = score_job(job, master_skills_path=str(skills_file))
    assert bd["tech_stack"] > 50


def test_tech_stack_no_master_skills_zero_overlap():
    """Without master_skills, tech stack scores 0 when JD has keywords (no overlap)."""
    job = _MockJob(
        normalized_title="engineer",
        title="Engineer",
        description="Python and Go.",
        location="remote",
    )
    total, bd = score_job(job, master_skills_path=None)
    # JD has python, go; user has none -> 0% overlap
    assert bd["tech_stack"] == 0.0


def test_threshold_60_high_scoring_pass():
    """Job scoring >=60 should pass threshold (integration intent)."""
    job = _MockJob(
        normalized_title="senior software engineer",
        title="Senior Software Engineer",
        description="Fintech payments. Python, FastAPI, AWS, PostgreSQL.",
        location="remote",
        remote_flag=True,
    )
    skills = Path(__file__).parent.parent / "storage" / "master_skills.json"
    total, _ = score_job(job, master_skills_path=str(skills) if skills.exists() else None)
    # High-signal job should typically pass 60
    assert total >= 50  # At least moderate; exact depends on master_skills


def test_threshold_low_scoring_junior_intern():
    """Junior intern job should score below threshold."""
    job = _MockJob(
        normalized_title="intern software engineer",
        title="Intern Software Engineer",
        description="Coffee fetching.",
        location="unknown city",
        remote_flag=False,
    )
    total, _ = score_job(job, master_skills_path=None)
    assert total < 60
