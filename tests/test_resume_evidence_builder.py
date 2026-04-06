"""Tests for local-first resume evidence assembly."""

from pathlib import Path
import uuid

from core.db.models import Job
from core.resumes.evidence_builder import build_resume_evidence_package
from core.resumes.local_inputs import (
    find_optional_input_file,
    list_supported_input_files,
    load_local_input_document,
)


FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "resume_evidence"


def _make_job(description: str = "Python, Go, PostgreSQL backend role.") -> Job:
    return Job(
        id=uuid.uuid4(),
        source="manual",
        title="Senior Backend Engineer",
        raw_title="Senior Backend Engineer",
        raw_company="Acme",
        company_name_raw="Acme",
        normalized_company="acme",
        normalized_title="senior backend engineer",
        dedup_hash=str(uuid.uuid4()),
        description=description,
        url="https://example.com/job",
        apply_url="https://example.com/job",
    )


def test_load_local_input_document_supports_md_yaml_json_txt():
    full_stack_dir = FIXTURES_ROOT / "full_stack" / "resume_inputs"

    resume_doc = load_local_input_document(full_stack_dir / "current_resume.txt")
    assert resume_doc.format == "txt"
    assert len(resume_doc.records) == 2

    role_doc = load_local_input_document(full_stack_dir / "current_role.yaml")
    assert role_doc.format == "yaml"
    assert len(role_doc.records) == 2
    assert role_doc.records[0].tags == ("backend", "platform")

    achievements_doc = load_local_input_document(full_stack_dir / "achievements.json")
    assert achievements_doc.format == "json"
    assert len(achievements_doc.records) == 2
    assert achievements_doc.records[0].metrics == ("0 Sev1",)

    project_doc = load_local_input_document(full_stack_dir / "projects" / "payments_launch.md")
    assert project_doc.format == "md"
    assert len(project_doc.records) == 3


def test_inventory_only_package_reports_missing_optional_sources():
    fixture_dir = FIXTURES_ROOT / "inventory_only"
    package = build_resume_evidence_package(
        _make_job(),
        inventory_path=fixture_dir / "experience_inventory.yaml",
        inputs_dir=fixture_dir / "resume_inputs",
    )

    assert package.source_kind == "inventory-only"
    assert package.inputs_hash
    assert set(package.missing_optional_sources) == {
        "achievements",
        "current_resume",
        "current_role",
        "project_writeups",
    }
    assert all(source.present for source in package.source_metadata if source.required)
    assert len(package.items) == 2


def test_inventory_plus_resume_package_includes_resume_items():
    fixture_dir = FIXTURES_ROOT / "inventory_plus_resume"
    inputs_dir = fixture_dir / "resume_inputs"

    assert find_optional_input_file(inputs_dir, "current_resume") == inputs_dir / "current_resume.md"

    package = build_resume_evidence_package(
        _make_job(),
        inventory_path=fixture_dir / "experience_inventory.yaml",
        inputs_dir=inputs_dir,
    )

    resume_items = [item for item in package.items if item.source_type == "current_resume"]
    assert package.source_kind == "inventory-plus-local-files"
    assert len(resume_items) == 4
    assert set(package.missing_optional_sources) == {
        "achievements",
        "current_role",
        "project_writeups",
    }


def test_full_stack_package_hash_is_stable_and_reports_loaded_sources():
    fixture_dir = FIXTURES_ROOT / "full_stack"
    inputs_dir = fixture_dir / "resume_inputs"

    project_files = list_supported_input_files(inputs_dir / "projects")
    assert [path.name for path in project_files] == ["ops_notes.txt", "payments_launch.md"]

    first = build_resume_evidence_package(
        _make_job(),
        inventory_path=fixture_dir / "experience_inventory.yaml",
        inputs_dir=inputs_dir,
    )
    second = build_resume_evidence_package(
        _make_job(),
        inventory_path=fixture_dir / "experience_inventory.yaml",
        inputs_dir=inputs_dir,
    )

    assert first.inputs_hash == second.inputs_hash
    assert first.compute_hash() == second.compute_hash()
    assert first.missing_optional_sources == ()
    assert {source.source_name for source in first.source_metadata if source.present} == {
        "inventory",
        "target_job_description",
        "current_resume",
        "current_role",
        "achievements",
        "project_writeups",
    }
    current_resume_source = next(
        source for source in first.source_metadata if source.source_name == "current_resume"
    )
    assert current_resume_source.used_for_facts is False
    assert current_resume_source.used_for_preferences is True
    assert len([item for item in first.items if item.source_type == "project_writeups"]) == 5
