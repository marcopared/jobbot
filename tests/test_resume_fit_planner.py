"""Focused deterministic fit-planner tests for resume-generation v2."""

from __future__ import annotations

import uuid
from pathlib import Path

from core.db.models import Job
from core.resumes.evidence_builder import build_resume_evidence_package
from core.resumes.fit_planner import plan_resume_artifacts
from core.resumes.html_template import TEMPLATE_VERSION

FIXTURES_ROOT = Path(__file__).parent / "fixtures"
FIT_FIXTURES = FIXTURES_ROOT / "resume_fit"
EVIDENCE_FIXTURES = FIXTURES_ROOT / "resume_evidence"


def _make_job(description: str) -> Job:
    return Job(
        id=uuid.uuid4(),
        source="manual",
        title="Role",
        raw_title="Role",
        raw_company="Acme",
        company_name_raw="Acme",
        normalized_company="acme",
        normalized_title="role",
        dedup_hash=str(uuid.uuid4()),
        description=description,
        url="https://example.com/job",
        apply_url="https://example.com/job",
    )


def _plan_fixture(
    fixture_dir: Path,
    *,
    persona: str = "BACKEND",
    target_keywords: set[str] | None = None,
    found_keywords: set[str] | None = None,
    missing_keywords: set[str] | None = None,
):
    inputs_dir = fixture_dir / "resume_inputs"
    package = build_resume_evidence_package(
        _make_job("backend python platform postgresql terraform observability"),
        inventory_path=fixture_dir / "experience_inventory.yaml",
        inputs_dir=inputs_dir if inputs_dir.exists() else None,
    )
    return plan_resume_artifacts(
        package,
        persona=persona,
        target_keywords=target_keywords
        or {"python", "postgresql", "platform", "terraform", "observability"},
        found_keywords=found_keywords or {"python", "platform"},
        missing_keywords=missing_keywords or {"postgresql", "terraform"},
        template_version=TEMPLATE_VERSION,
        fallback_enabled=False,
    )


def test_content_that_fits_immediately_uses_base_limits():
    planned = _plan_fixture(EVIDENCE_FIXTURES / "inventory_only")

    assert planned.fit_diagnostics.planner_fit_passed is True
    assert planned.fit_diagnostics.selected_limits.label == "base"
    assert planned.fit_diagnostics.attempted_limit_labels == ("base",)


def test_content_that_fits_after_compaction_uses_deterministic_reduction():
    planned = _plan_fixture(FIT_FIXTURES / "compaction_fit")

    assert planned.fit_diagnostics.planner_fit_passed is True
    assert planned.fit_diagnostics.selected_limits.label != "base"
    assert planned.fit_diagnostics.attempted_limit_labels[0] == "base"
    assert "projects trimmed before role experience" in planned.fit_diagnostics.compaction_notes


def test_overflow_fixture_reaches_minimum_compaction_policy():
    planned = _plan_fixture(FIT_FIXTURES / "overflow_inventory")

    assert planned.fit_diagnostics.selected_limits.label == "role_bullets_min"
    assert planned.fit_diagnostics.attempted_limit_labels[-1] == "role_bullets_min"
    assert "role bullets reduced by score order" in planned.fit_diagnostics.compaction_notes


def test_planner_is_deterministic_across_repeated_runs():
    first = _plan_fixture(FIT_FIXTURES / "compaction_fit")
    second = _plan_fixture(FIT_FIXTURES / "compaction_fit")

    assert first.fit_result.compute_hash() == second.fit_result.compute_hash()
    assert first.effective_input.compute_hash() == second.effective_input.compute_hash()
    assert first.payload.compute_hash() == second.payload.compute_hash()
    assert first.fit_diagnostics.to_dict() == second.fit_diagnostics.to_dict()
