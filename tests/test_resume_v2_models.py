"""Focused tests for the resume-generation v2 domain model."""

import pytest

from core.inventory.types import (
    Contact,
    ExperienceInventory,
    Project,
    ProjectBullet,
    Role,
    RoleBullet,
)
from core.resumes.effective_input import ResumeEffectiveInput
from core.resumes.payload_types import ResumeBullet
from core.resumes.v2_pipeline import (
    build_effective_input,
    build_fit_result,
    build_inventory_evidence_package,
    build_layout_plan,
    build_resume_payload,
)


def _make_inventory() -> ExperienceInventory:
    return ExperienceInventory(
        version=1,
        contact=Contact(name="Jane Doe", email="jane@example.com", location="Chicago, IL"),
        summary_variants={
            "BACKEND": "Backend summary",
            "HYBRID": "Hybrid summary",
        },
        skills=["Python", "Go", "PostgreSQL", "Terraform"],
        roles=[
            Role(
                company="Acme",
                title="Senior Engineer",
                start="2020-01",
                end="present",
                tags=["backend"],
                bullets=[
                    RoleBullet(
                        text="Built Python APIs backed by PostgreSQL.",
                        tags=["backend", "python", "postgresql"],
                        metrics=[],
                    ),
                    RoleBullet(
                        text="Improved CI/CD workflows with Terraform.",
                        tags=["platform", "terraform"],
                        metrics=[],
                    ),
                ],
            )
        ],
        projects=[
            Project(
                name="Deploy CLI",
                bullets=[
                    ProjectBullet(
                        text="Built a Go CLI for internal deployments.",
                        tags=["go", "platform"],
                        metrics=[],
                    )
                ],
            )
        ],
        education=[{"school": "MIT", "degree": "BS CS", "year": "2015"}],
    )


def test_inventory_only_evidence_package_construction():
    inventory = _make_inventory()
    package = build_inventory_evidence_package(inventory, "invhash1234abcd")

    assert package.source_kind == "inventory-only"
    assert package.inventory_version_hash == "invhash1234abcd"
    assert package.roles[0].bullet_ids == ("role:0:bullet:0", "role:0:bullet:1")
    assert package.projects[0].bullet_ids == ("project:0:bullet:0",)
    assert package.get_item("role:0:bullet:0").text == "Built Python APIs backed by PostgreSQL."


def test_resume_bullet_requires_provenance():
    with pytest.raises(ValueError, match="provenance"):
        ResumeBullet(id="bullet-1", text="Grounded bullet", provenance=())


def test_effective_input_hash_is_deterministic():
    inventory = _make_inventory()
    package = build_inventory_evidence_package(inventory, "invhash1234abcd")
    fit_result = build_fit_result(
        package,
        persona="BACKEND",
        target_keywords={"python", "postgresql", "go"},
        found_keywords={"python"},
        missing_keywords={"postgresql"},
    )

    first = build_effective_input(package, fit_result, template_version="v1")
    second = build_effective_input(package, fit_result, template_version="v1")

    assert first.compute_hash() == second.compute_hash()

    changed = ResumeEffectiveInput(
        evidence_hash=first.evidence_hash,
        fit_hash=first.fit_hash,
        target_persona=first.target_persona,
        target_keywords=first.target_keywords + ("terraform",),
        selected_evidence_ids=first.selected_evidence_ids,
        template_version=first.template_version,
    )
    assert changed.compute_hash() != first.compute_hash()


def test_payload_bullets_point_back_to_evidence_records():
    inventory = _make_inventory()
    package = build_inventory_evidence_package(inventory, "invhash1234abcd")
    fit_result = build_fit_result(
        package,
        persona="BACKEND",
        target_keywords={"python", "postgresql", "go"},
        found_keywords={"python"},
        missing_keywords={"postgresql"},
    )
    effective_input = build_effective_input(package, fit_result, template_version="v1")
    payload = build_resume_payload(package, fit_result, effective_input)
    layout = build_layout_plan(payload, template_version="v1")

    assert payload.effective_input_hash == effective_input.compute_hash()
    assert layout.effective_input_hash == payload.effective_input_hash

    evidence_ids = {item.id for item in package.items}
    for section in payload.sections:
        for entry in section.entries:
            for bullet in entry.bullets:
                assert bullet.provenance
                assert bullet.provenance[0].source_type == "inventory"
                assert bullet.provenance[0].evidence_id in evidence_ids
