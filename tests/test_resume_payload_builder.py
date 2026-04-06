"""Focused payload-builder tests for resume-generation v2."""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from pathlib import Path

from core.db.models import Job
from core.resumes.evidence_builder import build_resume_evidence_package
from core.resumes.evidence_types import ResumeEvidenceItem, ResumeEvidenceSupplementalEntry
from core.resumes.v2_pipeline import (
    build_effective_input,
    build_fit_result,
    build_resume_payload,
)
from core.resumes.v2_selection import prioritize_skills

FIXTURES_ROOT = Path(__file__).parent / "fixtures"
EVIDENCE_FIXTURES = FIXTURES_ROOT / "resume_evidence"
PAYLOAD_FIXTURES = FIXTURES_ROOT / "resume_payloads"


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


def _build_payload(
    fixture_name: str,
    *,
    persona: str,
    target_keywords: set[str],
    found_keywords: set[str],
    missing_keywords: set[str],
) -> dict[str, object]:
    fixture_dir = EVIDENCE_FIXTURES / fixture_name
    package = build_resume_evidence_package(
        _make_job("platform reliability terraform python go postgresql"),
        inventory_path=fixture_dir / "experience_inventory.yaml",
        inputs_dir=fixture_dir / "resume_inputs",
    )
    fit_result = build_fit_result(
        package,
        persona=persona,
        target_keywords=target_keywords,
        found_keywords=found_keywords,
        missing_keywords=missing_keywords,
    )
    effective_input = build_effective_input(package, fit_result, template_version="v1")
    payload = build_resume_payload(package, fit_result, effective_input)
    return payload.to_dict()


def _load_golden(name: str) -> dict[str, object]:
    return json.loads((PAYLOAD_FIXTURES / f"{name}.json").read_text())


def test_inventory_only_payload_matches_backend_golden():
    payload = _build_payload(
        "inventory_only",
        persona="BACKEND",
        target_keywords={"python", "go", "postgresql"},
        found_keywords={"python"},
        missing_keywords={"postgresql"},
    )

    assert payload == _load_golden("backend_inventory_only")


def test_richer_evidence_payload_matches_platform_golden():
    payload = _build_payload(
        "full_stack",
        persona="PLATFORM_INFRA",
        target_keywords={"platform", "reliability", "terraform", "python"},
        found_keywords={"platform", "terraform"},
        missing_keywords={"reliability"},
    )

    assert payload == _load_golden("platform_full_stack")


def test_no_payload_bullet_is_emitted_from_jd_only_evidence():
    fixture_dir = EVIDENCE_FIXTURES / "inventory_only"
    package = build_resume_evidence_package(
        _make_job("Need kubernetes reliability leadership"),
        inventory_path=fixture_dir / "experience_inventory.yaml",
        inputs_dir=fixture_dir / "resume_inputs",
    )
    package = replace(
        package,
        items=package.items
        + (
            ResumeEvidenceItem(
                id="jd:0",
                source_type="target_job_description",
                item_type="supplemental_text",
                text="Kubernetes, reliability, leadership",
                tags=("kubernetes", "reliability"),
            ),
        ),
        supplemental_entries=package.supplemental_entries
        + (
            ResumeEvidenceSupplementalEntry(
                id="jd_only",
                source_type="target_job_description",
                heading="JD Only",
                bullet_ids=("jd:0",),
            ),
        ),
    )

    fit_result = build_fit_result(
        package,
        persona="PLATFORM_INFRA",
        target_keywords={"kubernetes", "reliability"},
        found_keywords={"kubernetes"},
        missing_keywords={"reliability"},
    )
    effective_input = build_effective_input(package, fit_result, template_version="v1")
    payload = build_resume_payload(package, fit_result, effective_input)

    emitted_source_types = {
        provenance["source_type"]
        for section in payload.to_dict()["sections"]
        for entry in section["entries"]
        for bullet in entry["bullets"]
        for provenance in bullet["provenance"]
    }
    assert "target_job_description" not in emitted_source_types
    assert "highlights" not in {section["id"] for section in payload.to_dict()["sections"]}


def test_inventory_only_payload_is_valid_without_optional_sources():
    payload = _build_payload(
        "inventory_only",
        persona="BACKEND",
        target_keywords={"python", "go"},
        found_keywords={"python"},
        missing_keywords={"postgresql"},
    )

    assert [section["id"] for section in payload["sections"]] == [
        "summary",
        "skills",
        "experience",
        "projects",
        "education",
    ]
    assert payload["sections"][2]["entries"][0]["bullets"][0]["provenance"]


def test_richer_evidence_changes_payload_selection_deterministically():
    inventory_only_payload = _build_payload(
        "inventory_only",
        persona="PLATFORM_INFRA",
        target_keywords={"platform", "reliability", "terraform", "python"},
        found_keywords={"platform", "terraform"},
        missing_keywords={"reliability"},
    )
    richer_payload = _build_payload(
        "full_stack",
        persona="PLATFORM_INFRA",
        target_keywords={"platform", "reliability", "terraform", "python"},
        found_keywords={"platform", "terraform"},
        missing_keywords={"reliability"},
    )

    assert "highlights" not in {section["id"] for section in inventory_only_payload["sections"]}
    assert "highlights" in {section["id"] for section in richer_payload["sections"]}
    assert richer_payload == _load_golden("platform_full_stack")


def test_effective_input_hash_is_stable_across_fixture_path_forms():
    absolute_fixture_dir = (EVIDENCE_FIXTURES / "full_stack").resolve()
    relative_fixture_dir = Path("tests/fixtures/resume_evidence/full_stack")
    job = _make_job("platform reliability terraform python go postgresql")

    absolute_package = build_resume_evidence_package(
        job,
        inventory_path=absolute_fixture_dir / "experience_inventory.yaml",
        inputs_dir=absolute_fixture_dir / "resume_inputs",
    )
    relative_package = build_resume_evidence_package(
        job,
        inventory_path=relative_fixture_dir / "experience_inventory.yaml",
        inputs_dir=relative_fixture_dir / "resume_inputs",
    )

    absolute_fit = build_fit_result(
        absolute_package,
        persona="PLATFORM_INFRA",
        target_keywords={"platform", "reliability", "terraform", "python"},
        found_keywords={"platform", "terraform"},
        missing_keywords={"reliability"},
    )
    relative_fit = build_fit_result(
        relative_package,
        persona="PLATFORM_INFRA",
        target_keywords={"platform", "reliability", "terraform", "python"},
        found_keywords={"platform", "terraform"},
        missing_keywords={"reliability"},
    )

    absolute_effective_input = build_effective_input(
        absolute_package, absolute_fit, template_version="v1"
    )
    relative_effective_input = build_effective_input(
        relative_package, relative_fit, template_version="v1"
    )

    assert absolute_package.compute_hash() == relative_package.compute_hash()
    assert absolute_effective_input.compute_hash() == relative_effective_input.compute_hash()


def test_payload_builder_respects_skill_limit_while_preserving_keyword_priority():
    fixture_dir = EVIDENCE_FIXTURES / "full_stack"
    package = build_resume_evidence_package(
        _make_job("platform reliability terraform python go postgresql"),
        inventory_path=fixture_dir / "experience_inventory.yaml",
        inputs_dir=fixture_dir / "resume_inputs",
    )
    fit_result = build_fit_result(
        package,
        persona="PLATFORM_INFRA",
        target_keywords={"platform", "reliability", "terraform", "python"},
        found_keywords={"platform", "terraform"},
        missing_keywords={"reliability"},
    )
    effective_input = build_effective_input(package, fit_result, template_version="v1")
    payload = build_resume_payload(package, fit_result, effective_input, max_skills=2).to_dict()

    skills_section = next(section for section in payload["sections"] if section["id"] == "skills")
    assert skills_section["lines"] == ["Python", "Terraform"]


def test_payload_builder_skill_order_comes_from_shared_v2_selection_semantics():
    fixture_dir = EVIDENCE_FIXTURES / "full_stack"
    package = build_resume_evidence_package(
        _make_job("platform reliability terraform python go postgresql"),
        inventory_path=fixture_dir / "experience_inventory.yaml",
        inputs_dir=fixture_dir / "resume_inputs",
    )
    fit_result = build_fit_result(
        package,
        persona="PLATFORM_INFRA",
        target_keywords={"platform", "reliability", "terraform", "python"},
        found_keywords={"platform", "terraform"},
        missing_keywords={"reliability"},
    )
    effective_input = build_effective_input(package, fit_result, template_version="v1")
    payload = build_resume_payload(package, fit_result, effective_input, max_skills=4).to_dict()

    skills_section = next(section for section in payload["sections"] if section["id"] == "skills")
    assert tuple(skills_section["lines"]) == prioritize_skills(
        package.skills,
        fit_result.target_keywords,
        max_skills=4,
    )
